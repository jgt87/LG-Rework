#!/usr/bin/env python3
"""Read-only compatibility check used to onboard a new TV. Changes nothing on the TV.

The target lists are imported from the component scripts themselves, so this check
always tests what the scripts would actually touch. It prints one JSON report that
holds names, paths, SHA-256 hashes and statuses only: no unit-file text, serial
numbers, network details or account data.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
SCRIPTS = {
    'home-router': 'home-router.py',
    'hdmi-cleanup': 'hdmi-cleanup.py',
    'alexa-tiles': 'alexa-tiles.py',
    'home-layout': 'lg-home-layout.py',
    'no-signal-background': 'no-signal-background.py',
    'debloat': 'debloat-tv.py',
}
COMPONENTS = ['dashboard'] + list(SCRIPTS)
REVIEW = HERE / 'debloat-reviewed-units.json'
APP_DIRS = ['/usr/palm/applications', '/media/system/apps/usr/palm/applications',
            '/mnt/otncabi/usr/palm/applications', '/mnt/otycabi/usr/palm/applications',
            '/media/cryptofs/apps/usr/palm/applications', '/media/developer/apps/usr/palm/applications']
DEVELOPER_APPS = Path('/media/developer/apps/usr/palm/applications')
INIT_HOOKS = Path('/var/lib/webosbrew/init.d')
# The only Luna methods this check may call. All of them read state.
READ_ONLY_METHODS = {'getSystemInfo', 'getSystemSettings', 'getPreloadPolicy',
                     'getForegroundAppInfo', 'getPowerState'}
# The only systemctl verbs this check may run.
READ_ONLY_SYSTEMCTL = {'cat', 'show'}


def run(args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, timeout=15)
    return result.returncode, result.stdout


def luna(service, method, payload):
    if method.split('/')[-1] not in READ_ONLY_METHODS:
        raise RuntimeError('Refusing non-read Luna method: ' + method)
    code, out = run(['luna-send', '-w', '5000', '-n', '1',
                     'luna://' + service + '/' + method, json.dumps(payload)])
    if code:
        raise RuntimeError('luna-send failed for ' + method)
    reply = json.loads(out)
    if reply.get('returnValue') is not True:
        raise RuntimeError(method + ' rejected: ' + str(reply.get('errorText') or reply.get('errorCode')))
    return reply


def systemctl(verb, *args):
    if verb not in READ_ONLY_SYSTEMCTL:
        raise RuntimeError('Refusing systemctl ' + verb)
    return run(['systemctl', verb] + list(args) + ['--no-pager'])


def load(name):
    """Import a component script for its constants. Its main() is never called."""
    spec = importlib.util.spec_from_file_location('lg_' + name.replace('-', '_'), str(HERE / SCRIPTS[name]))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def app_present(appid):
    return any((Path(base) / appid / 'appinfo.json').is_file() for base in APP_DIRS)


def sha_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class Component:
    def __init__(self):
        self.checks = []

    def add(self, check, status, detail=''):
        self.checks.append({'check': check, 'status': status, 'detail': detail})

    def attempt(self, check, function):
        try:
            function()
        except Exception as error:
            self.add(check, 'differs', 'could not check: ' + str(error)[:200])

    def result(self):
        statuses = {item['status'] for item in self.checks}
        status = 'missing' if 'missing' in statuses else 'differs' if 'differs' in statuses else 'matches'
        return {'status': status, 'checks': self.checks}


def setting(category, key):
    return luna('com.webos.settingsservice', 'getSystemSettings',
                {'category': category, 'keys': [key]}).get('settings', {}).get(key)


def check_dashboard(c):
    ports = [port for port in range(1, 5) if app_present('com.webos.app.hdmi' + str(port))]
    c.add('HDMI input apps', 'matches' if 2 in ports else 'differs',
          'inputs found: ' + ', '.join('HDMI' + str(p) for p in ports) + ' (the Xbox tile uses HDMI2)')
    c.add('Developer app directory', 'matches' if DEVELOPER_APPS.is_dir() else 'missing', str(DEVELOPER_APPS))
    c.add('Homebrew Channel', 'matches' if app_present('org.webosbrew.hbchannel') else 'missing',
          'needed for root access and the LG Home escape')


def check_router(c, mod):
    def foreground():
        appid = luna('com.webos.applicationManager', 'getForegroundAppInfo', {}).get('appId')
        c.add('Foreground app API', 'matches' if isinstance(appid, str) else 'differs')
    def power():
        state = luna('com.webos.service.tvpower', 'power/getPowerState', {}).get('state')
        c.add('Power state API', 'matches' if isinstance(state, str) else 'differs', str(state))
    def auto_launch():
        value = setting('general', 'homeAutoLaunch')
        c.add('homeAutoLaunch setting', 'matches' if value in ('on', 'off') else 'differs', str(value))
    c.attempt('Foreground app API', foreground)
    c.attempt('Power state API', power)
    c.attempt('homeAutoLaunch setting', auto_launch)
    c.add('Stock Home app ' + mod.STOCK, 'matches' if app_present(mod.STOCK) else 'missing')
    c.add('Homebrew startup hooks', 'matches' if INIT_HOOKS.is_dir() else 'missing', str(INIT_HOOKS))


def block_list(c, path):
    if path.is_file():
        try:
            valid = isinstance(json.loads(path.read_text()).get('blocked_system_applist'), list)
        except ValueError:
            valid = False
        c.add('Launcher block list ' + path.name, 'matches' if valid else 'differs',
              str(path) if valid else 'unexpected format')
    else:
        found = sorted(p.name for p in path.parent.glob('*.json')) if path.parent.is_dir() else []
        c.add('Launcher block list ' + path.name, 'missing',
              'this TV has: ' + (', '.join(found) or 'none') + ' (the block list is chosen by region)')


def check_hdmi_cleanup(c, mod):
    block_list(c, mod.BLOCKS)
    if mod.PRELOAD.is_file():
        try:
            valid = isinstance(json.loads(mod.PRELOAD.read_text()).get('allowedApps'), dict)
        except ValueError:
            valid = False
        c.add('Preload configuration', 'matches' if valid else 'differs', str(mod.PRELOAD))
    else:
        c.add('Preload configuration', 'missing', str(mod.PRELOAD))
    def preload_api():
        apps = luna('com.webos.service.preloadmanager', 'getPreloadPolicy', {}).get('applications')
        c.add('Preload policy API', 'matches' if isinstance(apps, list) else 'differs')
    c.attempt('Preload policy API', preload_api)
    for category, key in mod.TARGET_SETTINGS:
        def read(category=category, key=key):
            value = setting(category, key)
            c.add('Setting ' + category + '/' + key, 'differs' if value is None else 'matches')
        c.attempt('Setting ' + category + '/' + key, read)
    absent = [appid for appid in mod.TARGET_TILES if not app_present(appid)]
    c.add('Tile targets present', 'differs' if absent else 'matches',
          (str(len(mod.TARGET_TILES) - len(absent)) + ' of ' + str(len(mod.TARGET_TILES))) +
          ('; absent: ' + ', '.join(absent) if absent else ''))
    absent = sorted(appid for appid in mod.PROTECTED if appid != 'org.webosbrew.hbchannel' and not app_present(appid))
    c.add('Protected apps present', 'differs' if absent else 'matches', ', '.join(absent))


def check_alexa(c, mod):
    block_list(c, mod.BLOCKS)
    for appid in mod.IDS:
        path = Path('/usr/palm/applications') / appid / 'appinfo.json'
        try:
            ok = json.loads(path.read_text()).get('id') == appid
            c.add('App ' + appid, 'matches' if ok else 'differs')
        except (OSError, ValueError):
            c.add('App ' + appid, 'missing', str(path))


def check_layout(c, mod):
    if not mod.TARGET.is_file():
        c.add('LG Home layout file', 'missing', str(mod.TARGET))
        return
    actual = hashlib.sha256(mod.TARGET.read_bytes()).hexdigest()
    c.add('LG Home layout hash', 'matches' if actual == mod.EXPECTED else 'differs',
          'sha256 ' + actual + ('' if actual == mod.EXPECTED else ', reviewed ' + mod.EXPECTED))


def check_no_signal(c, mod):
    def read():
        value = setting('general', mod.KEY)
        c.add('Setting general/' + mod.KEY, 'matches' if value in ('on', 'off') else
              'missing' if value is None else 'differs', str(value))
    c.attempt('Setting general/' + mod.KEY, read)


def check_debloat(c, mod):
    try:
        review = json.loads(REVIEW.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as error:
        c.add('Reviewed unit definitions', 'missing', str(error)[:200])
        return
    for unit in mod.UNITS:
        code, text = systemctl('cat', unit)
        if code or not text.strip():
            c.add('Unit ' + unit, 'missing')
            continue
        actual, expected = sha_text(text), sha_text(review.get(unit, ''))
        c.add('Unit ' + unit, 'matches' if actual == expected else 'differs',
              'definition sha256 ' + actual + ('' if actual == expected else ', reviewed ' + expected))
        code, out = systemctl('show', unit, '--property=LoadState,RequiredBy,BoundBy,ConsistsOf')
        props = dict(line.split('=', 1) for line in out.splitlines() if '=' in line)
        linked = [key for key in ('RequiredBy', 'BoundBy', 'ConsistsOf') if props.get(key)]
        c.add('Unit ' + unit + ' dependencies',
              'matches' if props.get('LoadState') == 'loaded' and not linked else 'differs',
              'LoadState=' + str(props.get('LoadState')) + ('; reverse links: ' + ', '.join(linked) if linked else ''))
    absent = [path for path in mod.BINARIES if not Path(path).exists()]
    c.add('Target executables present', 'differs' if absent else 'matches',
          str(len(mod.BINARIES) - len(absent)) + ' of ' + str(len(mod.BINARIES)) +
          ('; absent: ' + ', '.join(absent) if absent else ''))
    for unit in mod.CORE:
        code, out = systemctl('show', unit, '--property=LoadState')
        c.add('Protected unit ' + unit, 'matches' if 'LoadState=loaded' in out else 'differs')
    c.add('SDX (never a target)', 'matches' if Path('/usr/sbin/sdx').exists() else 'differs',
          '/usr/sbin/sdx ' + ('present' if Path('/usr/sbin/sdx').exists() else 'not found'))


CHECKS = {'home-router': check_router, 'hdmi-cleanup': check_hdmi_cleanup, 'alexa-tiles': check_alexa,
          'home-layout': check_layout, 'no-signal-background': check_no_signal, 'debloat': check_debloat}


def profile_id(info):
    parts = [str(info.get('modelName') or 'unknown'), str(info.get('firmwareVersion') or 'unknown')]
    return re.sub(r'[^A-Za-z0-9._-]', '-', '_'.join(parts))


def probe():
    """Connection check for init.ps1 -Action connect: root, Python, Homebrew hooks and TV identity."""
    result = {'uid': os.geteuid(), 'python': sys.version.split()[0], 'homebrewInit': INIT_HOOKS.is_dir(), 'tv': None}
    try:
        info = luna('com.webos.service.tv.systemproperty', 'getSystemInfo',
                    {'keys': ['modelName', 'firmwareVersion', 'sdkVersion']})
        result['tv'] = {key: info.get(key) for key in ('modelName', 'firmwareVersion', 'sdkVersion')}
    except Exception as error:
        result['error'] = str(error)[:200]
    print(json.dumps(result))


def main():
    if sys.argv[1:] == ['probe']:
        return probe()
    if sys.argv[1:] not in ([], ['check']):
        raise RuntimeError('Usage: init-tv.py [check|probe]')
    if os.geteuid() != 0:
        raise RuntimeError('Connect as root')
    info = luna('com.webos.service.tv.systemproperty', 'getSystemInfo',
                {'keys': ['modelName', 'firmwareVersion', 'sdkVersion']})
    tv = {key: info.get(key) for key in ('modelName', 'firmwareVersion', 'sdkVersion')}
    modules, components = {}, {}
    for name in SCRIPTS:
        try:
            modules[name] = load(name)
        except Exception as error:
            components[name] = {'status': 'differs', 'checks': [
                {'check': 'Load ' + SCRIPTS[name], 'status': 'differs', 'detail': str(error)[:200]}]}
    c = Component()
    check_dashboard(c)
    components['dashboard'] = c.result()
    for name, check in CHECKS.items():
        if name in modules:
            c = Component()
            try:
                check(c, modules[name])
            except Exception as error:
                c.add('Run checks', 'differs', 'could not check: ' + str(error)[:200])
            components[name] = c.result()
    reviewed = []
    if 'home-router' in modules:
        reviewed = [name for name in COMPONENTS if modules['home-router'].reviewed_tv(tv, name)]
    report = {
        'tool': 'init-tv', 'schema': 1, 'readOnly': True,
        'generatedUtc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'profileId': profile_id(tv), 'tv': tv,
        'reviewedComponents': reviewed,
        'components': {name: components[name] for name in COMPONENTS if name in components},
    }
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('STOP: ' + str(error), file=sys.stderr)
        sys.exit(1)
