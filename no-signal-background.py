#!/usr/bin/env python3
"""Change only the native No Signal artwork setting, retaining its original value."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path('/var/lib/lg-no-signal-background')
BACKUP = ROOT / 'original-state.json'
KEY = 'noSignalScreenSaver'


REFERENCE_TV = ('OLED48C24LA', '33.31.68', '10.3.1')
PROFILES_FILE = 'lg-reviewed-profiles.json'


def reviewed_tv(info, component):
    """Exact model/firmware/SDK match: the reference TV, or a maintainer-reviewed profile
    from profiles/lg-reviewed-profiles.json that lists this component."""
    key = tuple(info.get(name) for name in ('modelName', 'firmwareVersion', 'sdkVersion'))
    if key == REFERENCE_TV:
        return True
    if not all(isinstance(part, str) and part for part in key):
        return False
    try:
        registry = json.loads(Path(__file__).resolve().with_name(PROFILES_FILE).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    profiles = registry.get('profiles') if isinstance(registry, dict) else None
    for profile in profiles if isinstance(profiles, list) else []:
        if not isinstance(profile, dict) or not isinstance(profile.get('components'), list):
            continue
        if (profile.get('modelName'), profile.get('firmwareVersion'), profile.get('sdkVersion')) == key \
                and component in profile['components']:
            return True
    return False


def keep_profiles(directory):
    """Copy an uploaded reviewed-profile registry next to the persistent script."""
    source = Path(__file__).resolve().with_name(PROFILES_FILE)
    target = Path(directory) / PROFILES_FILE
    if source.is_file() and source.resolve() != target.resolve():
        temp = target.with_name(PROFILES_FILE + '.tmp')
        temp.write_bytes(source.read_bytes())
        os.chmod(str(temp), 0o600)
        os.replace(str(temp), str(target))


def request(service, method, payload):
    result = subprocess.run(['luna-send', '-w', '3000', '-n', '1',
        'luna://' + service + '/' + method, json.dumps(payload)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=6)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace'))
    reply = json.loads(result.stdout)
    if reply.get('returnValue') is not True:
        raise RuntimeError(str(reply))
    return reply


def current():
    reply = request('com.webos.settingsservice', 'getSystemSettings',
                    {'category': 'general', 'keys': [KEY]})
    value = reply['settings'][KEY]
    if value not in ('on', 'off'):
        raise RuntimeError('Unexpected artwork setting: ' + str(value))
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['apply', 'verify', 'restore'])
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('Root required')
    info = request('com.webos.service.tv.systemproperty', 'getSystemInfo',
                   {'keys': ['modelName', 'firmwareVersion', 'sdkVersion']})
    if not reviewed_tv(info, 'no-signal-background'):
        raise RuntimeError('Unreviewed TV/firmware')
    value = current()
    if args.action == 'verify':
        if value != 'off':
            raise RuntimeError('No Signal artwork is enabled')
        print('Verified: No Signal artwork setting is off. Check the HDMI screen visually.')
        return
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    import fcntl
    with (ROOT / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        value = current()
        if args.action == 'apply' and not BACKUP.exists():
            # Exclusive creation retains the original across repeated apply calls.
            with BACKUP.open('x') as out:
                os.chmod(str(BACKUP), 0o600)
                json.dump({KEY: value, 'tv': info}, out)
                out.flush()
                os.fsync(out.fileno())
        saved = json.loads(BACKUP.read_text())
        if saved.get(KEY) not in ('on', 'off'):
            raise RuntimeError('Invalid original-state backup')
        desired = 'off' if args.action == 'apply' else saved[KEY]
        if value != desired:
            request('com.webos.settingsservice', 'setSystemSettings',
                    {'category': 'general', 'settings': {KEY: desired}})
        if current() != desired:
            raise RuntimeError('Artwork setting did not read back correctly; backup retained')
        print('No Signal artwork setting:', desired)
        print('Original setting retained at', BACKUP)
        print('No Signal text, auto-off, HDMI/CEC, OLED protection and SDX unchanged.')
        print('Switch away from the HDMI input and back if the old picture remains visible.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('STOP: ' + str(error), file=sys.stderr)
        sys.exit(1)
