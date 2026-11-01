#!/usr/bin/env python3
"""Reversible HDMI-preserving startup/wake and stock-Home routing. Leaves CEC configured."""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import select
import shlex
import signal
import subprocess
import sys
import time

APP = 'com.local.hdmihome'
STOCK = 'com.webos.app.home'
ROOT = Path('/var/lib/lg-hdmi-home-router')
SCRIPT = ROOT / 'home-router.py'
HOOK = Path('/var/lib/webosbrew/init.d/85-lg-hdmi-home')
ENABLED = ROOT / 'enabled'
ORIGINAL = ROOT / 'original-state.json'
STATUS = ROOT / 'status.json'
BYPASS = Path('/tmp/lg-hdmi-home-bypass.json')
MARKER = '# Managed by lg-hdmi-home-router'
RUNNING = True


def write(path, value):
    path = Path(path)
    data = value if isinstance(value, str) else json.dumps(value) + '\n'
    temp = path.with_name(path.name + '.tmp-' + str(os.getpid()))
    with temp.open('w', encoding='utf-8', newline='') as out:
        os.chmod(str(temp), 0o600)
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    os.replace(str(temp), str(path))


def request(service, method, payload):
    result = subprocess.run(['luna-send', '-w', '3000', '-n', '1',
                             'luna://' + service + '/' + method, json.dumps(payload)],
                            capture_output=True, text=True, timeout=6)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    data = json.loads(result.stdout)
    if data.get('returnValue') is not True:
        raise RuntimeError(json.dumps(data))
    return data


def home_setting(value=None):
    payload = {'category': 'general'}
    if value is None:
        payload['keys'] = ['homeAutoLaunch']
        return request('com.webos.settingsservice', 'getSystemSettings', payload)['settings']['homeAutoLaunch']
    payload['settings'] = {'homeAutoLaunch': value}
    request('com.webos.settingsservice', 'setSystemSettings', payload)
    if home_setting() != value:
        raise RuntimeError('Home Auto Launch setting did not read back correctly')


def foreground():
    data = request('com.webos.applicationManager', 'getForegroundAppInfo', {})
    if not isinstance(data.get('appId'), str):
        raise RuntimeError('Unrecognized foreground reply: ' + json.dumps(data))
    return data['appId']


def check_tv():
    info = request('com.webos.service.tv.systemproperty', 'getSystemInfo',
                   {'keys': ['modelName', 'firmwareVersion', 'sdkVersion']})
    if (info.get('modelName'), info.get('firmwareVersion'), info.get('sdkVersion')) != (
            'OLED48C24LA', '33.31.68', '10.3.1'):
        raise RuntimeError('Unreviewed TV/firmware; routing not started: ' + json.dumps(info))
    return info


def check_app():
    info = json.loads(Path('/media/developer/apps/usr/palm/applications/' + APP + '/appinfo.json').read_text())
    version = tuple(int(part) for part in info['version'].split('.'))
    if info.get('id') != APP or version < (1, 0, 3):
        raise RuntimeError('Install HDMI Home 1.0.3 or later before enabling routing')


def should_redirect(appid, power, bypass, enabled):
    # HDMI, including CEC startup/wake, must never be redirected.
    return enabled and appid == STOCK and power not in ('suspend', 'active standby', 'screen off') and not bypass


def parse_messages(buffer):
    decoder = json.JSONDecoder()
    messages = []
    while buffer.strip():
        buffer = buffer.lstrip()
        try:
            data, end = decoder.raw_decode(buffer)
        except json.JSONDecodeError:
            break
        messages.append(data)
        buffer = buffer[end:]
    if len(buffer) > 65536:
        raise RuntimeError('Luna subscription buffer exceeded limit')
    return messages, buffer


def stop_child(proc):
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
    if proc is not None and proc.stdout:
        proc.stdout.close()


class Subscription:
    def __init__(self, name, uri):
        self.name, self.uri = name, uri
        self.proc, self.buffer = None, ''
        self.retry_at, self.delay = 0, 1

    def connect(self):
        self.proc = subprocess.Popen(['luna-send', '-i', self.uri, '{"subscribe":true}'],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.buffer = ''

    def failed(self):
        stop_child(self.proc)
        self.proc = None
        self.retry_at = time.monotonic() + self.delay
        self.delay = min(30, self.delay * 2)

    def read(self):
        chunk = os.read(self.proc.stdout.fileno(), 16384)
        if not chunk:
            raise RuntimeError(self.name + ' subscription ended')
        messages, self.buffer = parse_messages(self.buffer + chunk.decode('utf-8', errors='replace'))
        for data in messages:
            if data.get('returnValue') is False:
                raise RuntimeError(self.name + ': ' + json.dumps(data))
        if messages:
            self.delay = 1
        return messages


def read_bypass():
    try:
        value = json.loads(BYPASS.read_text())
        if value.get('until', 0) > time.time():
            return value
    except (OSError, ValueError):
        pass
    return None


def clear_bypass():
    try:
        BYPASS.unlink()
    except FileNotFoundError:
        pass


def live_pid():
    try:
        pid = int(json.loads(STATUS.read_text())['pid'])
        args = Path('/proc/' + str(pid) + '/cmdline').read_bytes().split(b'\0')
        if str(SCRIPT).encode() in args and b'run' in args:
            return pid
    except (OSError, ValueError, KeyError):
        pass
    return None


@contextmanager
def control_lock(blocking=True):
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (ROOT / 'control.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        yield


def run():
    global RUNNING
    with (ROOT / 'daemon.lock').open('a') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Router is already running.', flush=True)
            return
        ready_deadline = time.monotonic() + 30
        while True:
            try:
                check_tv()
                check_app()
                break
            except Exception as error:
                if str(error).startswith('Unreviewed TV/firmware') or time.monotonic() >= ready_deadline:
                    raise
                print('Waiting for startup services:', str(error), flush=True)
                time.sleep(2)
        def halt(_sig, _frame):
            global RUNNING
            RUNNING = False
        signal.signal(signal.SIGTERM, halt)
        signal.signal(signal.SIGINT, halt)
        streams = [Subscription('foreground', 'luna://com.webos.applicationManager/getForegroundAppInfo'),
                   Subscription('power', 'luna://com.webos.service.tvpower/power/getPowerState')]
        current, power, due, last_launch, heartbeat = '', '', None, -100, 0
        redirects, last_error = 0, ''
        clear_bypass()
        print('Home router started; HDMI startup/wake stays on the source.', flush=True)
        # Initial subscription snapshots are not guaranteed on every firmware.
        try:
            current = foreground()
            power = request('com.webos.service.tvpower', 'power/getPowerState', {})['state'].lower()
        except Exception as error:
            last_error = str(error)
            print('Initial snapshot unavailable; waiting for subscriptions:', last_error, flush=True)
        try:
            while RUNNING and ENABLED.is_file():
                now = time.monotonic()
                for stream in streams:
                    if stream.proc is None and now >= stream.retry_at:
                        try:
                            stream.connect()
                        except OSError as error:
                            last_error = str(error)
                            stream.failed()
                active = {stream.proc.stdout: stream for stream in streams if stream.proc is not None}
                ready, _, _ = select.select(list(active), [], [], 0.2) if active else ([], [], [])
                if not active:
                    time.sleep(0.2)
                for pipe in ready:
                    stream = active[pipe]
                    try:
                        for data in stream.read():
                            if stream.name == 'power':
                                state = data.get('state')
                                if isinstance(state, str):
                                    power = state.lower()
                                    if power != 'active':
                                        clear_bypass()
                                        due = None
                                    elif current == STOCK and due is None:
                                        due = time.monotonic() + 0.3
                            elif isinstance(data.get('appId'), str):
                                current = data['appId']
                                bypass = read_bypass()
                                if current == STOCK and bypass:
                                    bypass['active'] = True
                                    write(BYPASS, bypass)
                                elif bypass and bypass.get('active') and current != STOCK:
                                    clear_bypass()
                                due = time.monotonic() + 0.3 if should_redirect(current, power, bool(read_bypass()), ENABLED.is_file()) else None
                    except (OSError, ValueError, RuntimeError) as error:
                        last_error = str(error)
                        print(last_error, flush=True)
                        stream.failed()
                        if stream.name == 'foreground':
                            current, due = '', None
                now = time.monotonic()
                if due is not None and now >= due:
                    due = None
                    try:
                        with control_lock(blocking=False):
                            # Recheck at the last moment: a CEC switch wins over a queued Home event.
                            actual = foreground()
                            if should_redirect(actual, power, bool(read_bypass()), ENABLED.is_file()) and now-last_launch >= 2:
                                request('com.webos.applicationManager', 'launch', {'id': APP})
                                last_launch = now
                                redirects += 1
                                print('Redirected LG Home to HDMI Home.', flush=True)
                    except BlockingIOError:
                        due = time.monotonic() + 0.3 if ENABLED.is_file() else None
                    except Exception as error:
                        last_error = str(error)
                        print('Redirect skipped:', last_error, flush=True)
                if now >= heartbeat:
                    write(STATUS, {'pid': os.getpid(), 'time': time.time(), 'foreground': current,
                                   'power': power, 'redirects': redirects, 'lastError': last_error,
                                   'subscriptions': {stream.name: stream.proc is not None for stream in streams}})
                    heartbeat = now + 10
        finally:
            for stream in streams:
                stop_child(stream.proc)
            print('Home router stopped.', flush=True)


def start():
    if not ENABLED.is_file():
        print('Home routing is disabled.')
        return
    if live_pid():
        print('Home router is already running.')
        return
    logpath = ROOT / 'router.log'
    with logpath.open('w' if logpath.exists() and logpath.stat().st_size > 131072 else 'a') as log:
        os.chmod(str(logpath), 0o600)
        subprocess.Popen([sys.executable, str(SCRIPT), 'run'], stdin=subprocess.DEVNULL,
                         stdout=log, stderr=log, close_fds=True, start_new_session=True)


def stop():
    try:
        ENABLED.unlink()
    except FileNotFoundError:
        pass
    pid = live_pid()
    if pid:
        os.kill(pid, signal.SIGTERM)
        for _ in range(80):
            if not live_pid():
                break
            time.sleep(0.1)
    clear_bypass()


def install():
    check_tv()
    check_app()
    print('Preflight foreground:', foreground())
    power = request('com.webos.service.tvpower', 'power/getPowerState', {})
    if not isinstance(power.get('state'), str):
        raise RuntimeError('Unrecognized power-state reply; installation not started')
    value = home_setting()
    if value not in ('on', 'off'):
        raise RuntimeError('Unrecognized Home Auto Launch value')
    if HOOK.exists() and MARKER not in HOOK.read_text():
        raise RuntimeError('Unknown startup hook; refusing to overwrite')
    if ORIGINAL.exists():
        original = json.loads(ORIGINAL.read_text())
        if original.get('homeAutoLaunch') not in ('on', 'off'):
            raise RuntimeError('Invalid original-state backup')
    else:
        write(ORIGINAL, {'homeAutoLaunch': value})
    stop()
    if live_pid():
        raise RuntimeError('Previous router has not stopped; installation halted')
    write(SCRIPT, Path(__file__).read_text())
    os.chmod(str(SCRIPT), 0o700)
    HOOK.parent.mkdir(parents=True, exist_ok=True)
    try:
        home_setting('off')
        write(ENABLED, 'enabled\n')
        write(HOOK, '#!/bin/sh\n' + MARKER + '\nexec ' + shlex.quote(sys.executable) + ' ' + shlex.quote(str(SCRIPT)) + ' start\n')
        os.chmod(str(HOOK), 0o700)
        start()
        time.sleep(2)
        if not live_pid():
            raise RuntimeError('Router did not start; inspect router.log')
    except Exception:
        stop()
        if HOOK.is_file() and MARKER in HOOK.read_text():
            HOOK.unlink()
        home_setting(value)
        raise
    print('Enabled HDMI-preserving Home routing. Original setting backed up to', ORIGINAL)
    print('Home Auto Launch is off. CEC and all HDMI settings are unchanged.')
    print('HDMI startup/wake stays on the source, including No Signal. No startup dashboard launch is scheduled.')
    print('LG Home may flash briefly; Input Hook can remap the physical Home button directly.')


def uninstall():
    if HOOK.exists() and MARKER not in HOOK.read_text():
        raise RuntimeError('Unknown startup hook; no removal performed')
    if ORIGINAL.exists():
        original = json.loads(ORIGINAL.read_text())
        if original.get('homeAutoLaunch') not in ('on', 'off'):
            raise RuntimeError('Invalid original setting; stop and inspect backup')
    else:
        raise RuntimeError('Original setting backup missing; use disable to stop routing')
    stop()
    if HOOK.exists():
        HOOK.unlink()
    home_setting(original['homeAutoLaunch'])
    print('Routing removed; original Home Auto Launch setting restored. Backup retained.')


def self_test():
    import unittest
    check = unittest.TestCase()
    check.assertTrue(should_redirect(STOCK, 'active', False, True))
    for app in ['com.webos.app.hdmi1', 'com.webos.app.hdmi2', 'com.webos.app.hdmi3', 'com.webos.app.hdmi4', APP, 'com.palm.app.settings']:
        check.assertFalse(should_redirect(app, 'active', False, True))
    for state in ['suspend', 'active standby', 'screen off']:
        check.assertFalse(should_redirect(STOCK, state, False, True))
    check.assertFalse(should_redirect(STOCK, 'active', True, True))
    check.assertFalse(should_redirect(STOCK, 'active', False, False))
    # A later CEC transition replaces the pending Home state before recheck.
    check.assertFalse(should_redirect('com.webos.app.hdmi2', 'active', False, True))
    messages, rest = parse_messages('{"appId":"com.webos.app.home"}\n{"state":"Active"}\n{"partial":')
    check.assertEqual(len(messages), 2)
    check.assertEqual(rest, '{"partial":')
    with check.assertRaises(RuntimeError):
        parse_messages('x' * 65537)
    # Every HDMI source must survive all power transitions without dashboard routing.
    for port in range(1, 5):
        for power in ['', 'active', 'suspend', 'active standby', 'screen off']:
            for bypass in [False, True]:
                check.assertFalse(should_redirect('com.webos.app.hdmi' + str(port), power, bypass, True))
    print('Router regression checks passed: HDMI startup/wake preservation, Home routing, bypass/power/disable guards, streaming replies.')



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'start', 'run', 'status', 'disable', 'uninstall', 'stock-home', 'self-test'])
    action = parser.parse_args().action
    if action == 'self-test':
        self_test()
        return
    if os.geteuid() != 0:
        raise RuntimeError('Run as root on the TV')
    if action == 'run':
        run()
    elif action == 'start':
        with control_lock():
            start()
    elif action == 'status':
        print('Enabled:', ENABLED.is_file(), 'Process:', live_pid(), 'Startup hook:', HOOK.is_file())
        print('Home Auto Launch:', home_setting())
        print('Current foreground reply:', json.dumps(request(
            'com.webos.applicationManager', 'getForegroundAppInfo', {})))
        print('Current power reply:', json.dumps(request(
            'com.webos.service.tvpower', 'power/getPowerState', {})))
        print('Uptime:', Path('/proc/uptime').read_text().strip())
        print('Temporary stock-Home bypass:', json.dumps(read_bypass()))
        if HOOK.is_file():
            print('Installed startup hook:\n' + HOOK.read_text())
        if STATUS.exists():
            value = json.loads(STATUS.read_text())
            print('Heartbeat age (seconds):', round(time.time() - value.get('time', 0), 1))
            print(STATUS.read_text())
        if (ROOT / 'router.log').exists():
            print('Recent router log:\n' + (ROOT / 'router.log').read_text()[-4000:])
    else:
        with control_lock():
            if action == 'install':
                install()
            elif action == 'disable':
                stop()
                print('Routing disabled. Startup hook remains inert; use uninstall to restore original settings.')
            elif action == 'uninstall':
                uninstall()
            elif action == 'stock-home':
                write(BYPASS, {'until': time.time() + 120, 'active': False})
                request('com.webos.applicationManager', 'launch', {'id': STOCK})
                print('Opened LG Home with a temporary routing bypass.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('STOP:', error, file=sys.stderr)
        sys.exit(1)
