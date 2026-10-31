#!/usr/bin/env python3
"""Reviewed runtime-only debloat for one LG TV. SDX is never a target."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import fcntl

ROOT = Path('/var/lib/lg-reviewed-debloat')
STATE = ROOT / 'original-state.json'
SCRIPT = ROOT / 'debloat-tv.py'
REVIEW = ROOT / 'reviewed-units.json'
HOOK = Path('/var/lib/webosbrew/init.d/88-lg-reviewed-debloat')
MARKER = '# Managed by lg-reviewed-debloat'
MASKDIR = Path('/run/systemd/transient')
UNITS = '''com.webos.service.mycar.service com.webos.service.camera.service
com.webos.service.familycare.service com.webos.service.buddyconnector.service
contentminer.service dmost.service rdxd.service remotediag.service
remotelogger.service service-logger.service uploadd.service
voiceconductor.service voiceinput.service'''.split()
# Exact paths observed on this TV, including LS2-launched programs outside systemd.
BINARIES = ['/usr/sbin/' + name for name in '''com.webos.service.mycar
com.webos.service.camera2 contentminer dmost rdxd remotediag remotelogger
service-logger uploadd voiceconductor voiceinput voiceinput_network
voiceinput_sound voiceinput_preprocessor voiceinput_hidraw voiceclick
trigger_alexa sportsalarm nlpmanager iconnectivity'''.split()] + [
    '/usr/sbin/performer',
    '/usr/palm/services/com.webos.service.buddyconnector/com.webos.service.buddyconnector']
PROTECTED = {'sdx', 'sam', 'surface-manager', 'surface-manager-daemon', 'webapp-mgr',
             'ls-hubd', 'connman', 'audiod', 'audiooutputd', 'videooutputd',
             'panelcontroller', 'pqcontroller', 'bootd', 'tvpower', 'micomservice',
             'lginput2', 'devmode', 'alwaysready', 'tvdataexchanger', 'pacrunner', 'nudge'}
# Historical targets are accepted only to REMOVE overrides left by older trials.
RESTORE_UNITS = set(UNITS) | {'nudge.service'}
RESTORE_BINARIES = set(BINARIES) | {'/usr/sbin/nudge'}
CORE = ['sam.service', 'surface-manager.service', 'webapp-mgr.service',
        'connman.service', 'audiod.service', 'audiooutputd.service',
        'videooutputd.service', 'panelcontroller.service', 'devmode.service',
        'alwaysready.service', 'tvdataexchanger.service', 'lginput2.service']


def run(args, check=True):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, timeout=30)
    if check and result.returncode:
        raise RuntimeError(' '.join(args[:3]) + ': ' + result.stderr.strip())
    return result.stdout


def props(unit):
    text = run(['systemctl', 'show', unit, '--no-pager',
        '--property=Id,LoadState,ActiveState,RequiredBy,BoundBy,ConsistsOf,MainPID'])
    return dict(line.split('=', 1) for line in text.splitlines() if '=' in line)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value, mode=0o600):
    data = value if isinstance(value, bytes) else (json.dumps(value, indent=2) + '\n').encode()
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('wb') as out:
        os.chmod(str(tmp), mode)
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    os.replace(str(tmp), str(path))


def safe_catalog():
    names = {unit[:-8] if unit.endswith('.service') else unit for unit in UNITS}
    names.update(Path(path).name for path in BINARIES)
    if names & PROTECTED or any('sdx' in name.lower() for name in names):
        raise RuntimeError('Protected service in catalog')
    if len(UNITS) != len(set(UNITS)) or len(BINARIES) != len(set(BINARIES)):
        raise RuntimeError('Duplicate target')


def identity():
    data = json.loads(run(['luna-send', '-w', '3000', '-n', '1',
        'luna://com.webos.service.tv.systemproperty/getSystemInfo',
        '{"keys":["modelName","firmwareVersion","sdkVersion"]}']))
    if data.get('returnValue') is not True or [data.get(k) for k in (
        'modelName', 'firmwareVersion', 'sdkVersion')] != ['OLED48C24LA', '33.31.68', '10.3.1']:
        raise RuntimeError('Unreviewed TV/firmware: ' + str(data))


def processes():
    result = []
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit():
            continue
        try:
            exe = os.readlink(str(directory / 'exe'))
            result.append((int(directory.name), exe))
        except OSError:
            pass
    return result


def target_process(exe):
    # Jailed copies have an additional prefix but retain this exact suffix.
    return any(exe == path or exe.startswith('/var/palm/jail/') and exe.endswith(path)
               for path in BINARIES)


def mounts(path):
    return [line for line in Path('/proc/self/mountinfo').read_text().splitlines()
            if len(line.split()) > 5 and line.split()[4] == path]


def null_mount(path):
    return bool(mounts(path)) and os.path.samestat(Path(path).stat(), Path('/dev/null').stat())


def guard_unit(unit, properties):
    if unit not in UNITS or properties.get('Id') != unit or properties.get('LoadState') != 'loaded':
        raise RuntimeError('Unreviewed unit identity: ' + unit)
    # Stopping a unit propagates through these reverse relationships.
    for key in ('RequiredBy', 'BoundBy', 'ConsistsOf'):
        if properties.get(key):
            raise RuntimeError('Stop would propagate: ' + unit + ' ' + key + '=' + properties[key])


def stop_unit(unit):
    if unit not in UNITS:
        raise RuntimeError('Refusing to stop unreviewed unit: ' + unit)
    # A blocking systemctl client can wait indefinitely on the stop job.
    # Queue it, then require an observed inactive/failed state before proceeding.
    run(['systemctl', 'stop', '--no-block', unit])
    started = time.monotonic()
    killed_logger = False
    while True:
        current = props(unit)
        if current.get('ActiveState') in ('inactive', 'failed'):
            print('Stopped:', unit, flush=True)
            return
        elapsed = time.monotonic() - started
        if elapsed >= 15:
            raise RuntimeError('Stop did not complete: ' + unit + ' ' + str(current))
        # The captured service-logger unit explicitly documents SIGKILL stop
        # behavior. Limit this fallback to its verified main executable/PID.
        if unit == 'service-logger.service' and elapsed >= 5 and not killed_logger:
            pid = int(current.get('MainPID', '0'))
            if pid > 1:
                try:
                    actual = os.readlink('/proc/' + str(pid) + '/exe')
                    latest = props(unit)
                    if (actual == '/usr/sbin/service-logger' and
                            latest.get('MainPID') == str(pid) and
                            latest.get('ActiveState') == 'deactivating' and
                            os.readlink('/proc/' + str(pid) + '/exe') == actual):
                        os.kill(pid, signal.SIGKILL)
                        killed_logger = True
                        print('Finished stalled logger stop using its verified main PID:', pid, flush=True)
                except (ProcessLookupError, FileNotFoundError):
                    pass
        time.sleep(0.5)


def preflight(review):
    safe_catalog()
    identity()
    if not Path('/usr/sbin/sdx').is_file() or not any(exe == '/usr/sbin/sdx' for _, exe in processes()):
        raise RuntimeError('SDX must be running before the trial')
    state = {'version': 1, 'sdx_sha256': sha('/usr/sbin/sdx'), 'units': {}, 'binaries': {},
             'core': {unit: props(unit)['ActiveState'] for unit in CORE}, 'owned_masks': [], 'owned_mounts': []}
    for unit in UNITS:
        current = props(unit)
        guard_unit(unit, current)
        actual = run(['systemctl', 'cat', unit, '--no-pager'])
        if actual != review.get(unit):
            raise RuntimeError('Unit definition changed since review: ' + unit)
        mask = MASKDIR / unit
        if mask.exists() or mask.is_symlink():
            raise RuntimeError('Existing runtime override: ' + str(mask))
        state['units'][unit] = {'active': current['ActiveState']}
    for path in BINARIES:
        candidate = Path(path)
        if not candidate.exists():
            continue
        if candidate.is_symlink() or not candidate.is_file() or mounts(path):
            raise RuntimeError('Unexpected binary or existing mount: ' + path)
        if os.path.samefile(path, '/usr/sbin/sdx'):
            raise RuntimeError('SDX alias detected')
        with candidate.open('rb') as stream:
            if stream.read(4) != b'\x7fELF':
                raise RuntimeError('Expected ELF executable: ' + path)
        state['binaries'][path] = sha(path)
    return state


def verify(state):
    safe_catalog()
    if sha('/usr/sbin/sdx') != state['sdx_sha256'] or not any(exe == '/usr/sbin/sdx' for _, exe in processes()):
        raise RuntimeError('SDX health check failed')
    for unit, previous in state['core'].items():
        if previous == 'active' and props(unit)['ActiveState'] != 'active':
            raise RuntimeError('Protected core unit no longer active: ' + unit)
    errors = []
    for unit in state['owned_masks']:
        mask = MASKDIR / unit
        if not mask.is_symlink() or os.readlink(str(mask)) != '/dev/null':
            errors.append('Missing mask ' + unit)
        status = props(unit)
        if status['LoadState'] != 'masked' or status['ActiveState'] not in ('inactive', 'failed'):
            errors.append('Unit not disabled: ' + unit + ' ' + str(status))
    for path in state['owned_mounts']:
        if not null_mount(path):
            errors.append('Missing binary override: ' + path)
    running = [exe for _, exe in processes() if target_process(exe)]
    if running:
        errors.append('Target processes still running: ' + ', '.join(running))
    if errors:
        raise RuntimeError('\n'.join(errors))
    print('Verified: selected services stopped/masked, binary overrides present, no target processes running.')
    print('SDX executable unchanged and process running. Previously active protected core units remain active.')


def request_restarts(state):
    errors = []
    if set(state['owned_masks']) - RESTORE_UNITS:
        raise RuntimeError('Unreviewed restart target')
    for unit in state['owned_masks']:
        if state['units'][unit]['active'] == 'active':
            try:
                run(['systemctl', 'start', '--no-block', unit])
            except Exception as error:
                errors.append(unit + ': ' + str(error))
    return errors


def restore(state):
    safe_catalog()
    if (set(state['owned_masks']) - RESTORE_UNITS or set(state['owned_mounts']) - RESTORE_BINARIES
            or set(state['units']) - RESTORE_UNITS):
        raise RuntimeError('Invalid rollback targets')
    if HOOK.exists() and MARKER not in HOOK.read_text():
        raise RuntimeError('Startup hook conflict')
    # Check all ownership before changing anything.
    for path in state['owned_mounts']:
        if mounts(path) and not null_mount(path):
            raise RuntimeError('Foreign mount blocks restore: ' + path)
    for unit in state['owned_masks']:
        mask = MASKDIR / unit
        if (mask.exists() or mask.is_symlink()) and (not mask.is_symlink() or os.readlink(str(mask)) != '/dev/null'):
            raise RuntimeError('Foreign mask blocks restore: ' + unit)
    if HOOK.exists():
        HOOK.unlink()
    for path in reversed(state['owned_mounts']):
        if null_mount(path):
            run(['umount', path])
        if sha(path) != state['binaries'][path]:
            raise RuntimeError('Original executable mismatch: ' + path)
    for unit in state['owned_masks']:
        mask = MASKDIR / unit
        if mask.is_symlink():
            mask.unlink()
    run(['systemctl', 'daemon-reload'])
    restart_errors = request_restarts(state)
    print('Owned service overrides removed; restart jobs requested without waiting.', flush=True)
    print('Recovery is not confirmed until a full reboot and physical TV checks. Backup retained.', flush=True)
    if restart_errors:
        raise RuntimeError('Some restart requests failed; full reboot required: ' + '; '.join(restart_errors))


def apply(review):
    if STATE.exists():
        old = json.loads(STATE.read_text())
        if any(mounts(path) for path in old['owned_mounts']) or any((MASKDIR / unit).is_symlink() for unit in old['owned_masks']):
            verify(old)
            print('Already applied; original snapshot unchanged.')
            return
    fresh = preflight(review)
    # Preserve the original restore baseline across reboot reapplication.
    if STATE.exists():
        old = json.loads(STATE.read_text())
        previous_binaries = {path: value for path, value in old['binaries'].items() if path in BINARIES}
        if old['sdx_sha256'] != fresh['sdx_sha256'] or previous_binaries != fresh['binaries']:
            raise RuntimeError('Firmware/binary drift since original backup')
        if 'nudge.service' in old['units']:
            archived = ROOT / 'original-state-before-nudge-exclusion.json'
            if not archived.exists():
                write(archived, STATE.read_bytes())
        fresh['units'] = {unit: old['units'][unit] for unit in UNITS}
        fresh['core'] = old['core']
    write(STATE, fresh)
    MASKDIR.mkdir(parents=True, exist_ok=True)
    try:
        for unit in UNITS:
            guard_unit(unit, props(unit))
            fresh['owned_masks'].append(unit)
            write(STATE, fresh)
            (MASKDIR / unit).symlink_to('/dev/null')
        run(['systemctl', 'daemon-reload'])
        for unit in UNITS:
            stop_unit(unit)
        for path in fresh['binaries']:
            fresh['owned_mounts'].append(path)
            write(STATE, fresh)
            run(['mount', '--bind', '/dev/null', path])
        for pid, exe in processes():
            if target_process(exe):
                try:
                    if os.readlink('/proc/' + str(pid) + '/exe') == exe:
                        os.kill(pid, signal.SIGTERM)
                except (ProcessLookupError, FileNotFoundError):
                    pass
        time.sleep(3)
        verify(fresh)
    except Exception as primary:
        print('Original apply failure: ' + repr(primary), file=sys.stderr, flush=True)
        print('Attempting rollback.', file=sys.stderr, flush=True)
        try:
            restore(fresh)
        except Exception as rollback_error:
            raise RuntimeError('Apply failed: ' + repr(primary) + '; rollback incomplete: ' +
                               repr(rollback_error) + '. Full reboot and recovery checks required.') from primary
        raise
    print('Trial applied. Runtime masks and mounts disappear on a full reboot unless startup is installed.')


def self_test():
    import unittest
    test = unittest.TestCase()
    safe_catalog()
    test.assertFalse(target_process('/usr/sbin/sdx'))
    test.assertFalse(target_process('/usr/sbin/pacrunner'))
    test.assertFalse(target_process('/usr/sbin/alwaysready'))
    test.assertFalse(target_process('/usr/sbin/nudge'))
    test.assertNotIn('nudge.service', UNITS)
    test.assertIn('nudge.service', RESTORE_UNITS)
    test.assertTrue(target_process('/usr/sbin/contentminer'))
    test.assertTrue(target_process('/var/palm/jail/com.webos.service.voice.performer/usr/sbin/performer'))
    good = {'Id': UNITS[0], 'LoadState': 'loaded', 'RequiredBy': '', 'BoundBy': '', 'ConsistsOf': ''}
    guard_unit(UNITS[0], good)
    for key in ('RequiredBy', 'BoundBy', 'ConsistsOf'):
        test.assertRaises(RuntimeError, guard_unit, UNITS[0], dict(good, **{key: 'sdx.service'}))
    test.assertRaises(RuntimeError, guard_unit, 'sdx.service', good)
    from unittest.mock import patch
    with patch(__name__ + '.run') as execute, patch(__name__ + '.props', return_value={'ActiveState': 'inactive'}), patch('builtins.print'):
        stop_unit(UNITS[0])
        execute.assert_called_once_with(['systemctl', 'stop', '--no-block', UNITS[0]])
    with patch(__name__ + '.run') as execute:
        test.assertRaises(RuntimeError, stop_unit, 'sdx.service')
        execute.assert_not_called()
    stopping = {'ActiveState': 'deactivating', 'MainPID': '777'}
    with patch(__name__ + '.run'), patch(__name__ + '.props', side_effect=[stopping, stopping, {'ActiveState': 'inactive'}]), \
            patch(__name__ + '.time.monotonic', side_effect=[0, 6]), patch(__name__ + '.time.sleep'), \
            patch(__name__ + '.os.readlink', return_value='/usr/sbin/service-logger'), patch(__name__ + '.os.kill') as kill, patch('builtins.print'):
        stop_unit('service-logger.service')
        kill.assert_called_once_with(777, signal.SIGKILL)
    with patch(__name__ + '.run'), patch(__name__ + '.props', return_value=stopping), \
            patch(__name__ + '.time.monotonic', side_effect=[0, 6, 16]), patch(__name__ + '.time.sleep'), \
            patch(__name__ + '.os.readlink', return_value='/usr/sbin/sdx'), patch(__name__ + '.os.kill') as kill:
        test.assertRaises(RuntimeError, stop_unit, 'service-logger.service')
        kill.assert_not_called()
    restarting = {'owned_masks': ['nudge.service', 'voiceinput.service'], 'units': {
        'nudge.service': {'active': 'active'}, 'voiceinput.service': {'active': 'active'}}}
    with patch(__name__ + '.run', side_effect=[RuntimeError('restart unavailable'), '']) as execute:
        test.assertEqual(len(request_restarts(restarting)), 1)
        test.assertEqual(execute.call_count, 2)
        test.assertEqual(execute.call_args_list[0].args[0], ['systemctl', 'start', '--no-block', 'nudge.service'])
    with patch(__name__ + '.run') as execute:
        test.assertRaises(RuntimeError, request_restarts, {'owned_masks': ['sdx.service']})
        execute.assert_not_called()
    print('Regression checks passed: SDX/core exclusions, nudge exclusion/legacy restore, exact processes, stop/restart bounds and logger PID protection.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['apply', 'verify', 'restore', 'install-startup', 'boot', 'self-test'])
    parser.add_argument('--review', default=str(REVIEW))
    args = parser.parse_args()
    self_test()
    if args.action == 'self-test':
        return
    if os.geteuid() != 0:
        raise RuntimeError('Root required')
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (ROOT / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action == 'restore':
            restore(json.loads(STATE.read_text()))
        elif args.action == 'verify':
            verify(json.loads(STATE.read_text()))
        elif args.action == 'install-startup':
            verify(json.loads(STATE.read_text()))
            if HOOK.exists() and MARKER not in HOOK.read_text():
                raise RuntimeError('Startup hook conflict')
            write(SCRIPT, Path(__file__).read_bytes(), 0o700)
            write(REVIEW, Path(args.review).read_bytes())
            write(HOOK, ('#!/bin/sh\n' + MARKER + '\n(python3 ' + str(SCRIPT) +
                ' boot >' + str(ROOT / 'startup.log') + ' 2>&1) </dev/null >/dev/null 2>&1 &\n').encode(), 0o700)
            print('Startup installed. Reboot and verify; log: ' + str(ROOT / 'startup.log'))
        else:
            if args.action == 'boot':
                time.sleep(45)
            apply(json.loads(Path(args.review).read_text(encoding='utf-8-sig')))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('STOP: ' + str(error), file=sys.stderr)
        sys.exit(1)
