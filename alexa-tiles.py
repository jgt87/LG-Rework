#!/usr/bin/env python3
"""Hide built-in Alexa launcher entries without deleting firmware files."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

IDS = ('amazon.alexa.view', 'amazon.alexapr')
BLOCKS = Path('/var/preferences/com.webos.applicationManager/blockedSystemAppList/NLD.json')
ROOT = Path('/var/lib/lg-alexa-tiles')
STATE = ROOT / 'original-state.json'
HOOK = Path('/var/lib/webosbrew/init.d/91-lg-alexa-tiles')
SCRIPT = ROOT / 'alexa-tiles.py'
MARKER = '# Managed by lg-alexa-tiles'


def write(path, data, mode=0o600):
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('wb') as stream:
        os.chmod(str(tmp), mode)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(tmp), str(path))


def document():
    data = json.loads(BLOCKS.read_text())
    if not isinstance(data.get('blocked_system_applist'), list):
        raise RuntimeError('Unexpected block-list schema')
    return data


def verify():
    current = document()['blocked_system_applist']
    missing = [name for name in IDS if name not in current]
    if missing:
        raise RuntimeError('Alexa tile blocks missing: ' + ', '.join(missing))
    print('Verified: both Alexa IDs blocked in launcher configuration. Check LG Home visually.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['apply', 'verify', 'restore', 'install-startup', 'boot'])
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('Root required')
    if args.action == 'boot':
        time.sleep(50)
        if not HOOK.exists():
            return
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Share the older cleanup lock because both tools merge the same file.
    lockpath = Path('/var/lib/lg-hdmi-cleanup/operation.lock')
    if not lockpath.parent.is_dir():
        raise RuntimeError('Expected existing HDMI cleanup installation')
    with lockpath.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action == 'verify':
            verify()
            return
        if args.action == 'restore':
            old = json.loads(STATE.read_text())
            owned = old['added']
            if not isinstance(owned, list) or set(owned) - set(IDS):
                raise RuntimeError('Invalid Alexa backup')
            if HOOK.exists() and MARKER not in HOOK.read_text():
                raise RuntimeError('Hook ownership conflict')
            before = BLOCKS.read_bytes()
            current = document()
            current['blocked_system_applist'] = [x for x in current['blocked_system_applist'] if x not in owned]
            if BLOCKS.read_bytes() != before:
                raise RuntimeError('Block list changed during restore')
            if HOOK.exists():
                HOOK.unlink()
            write(BLOCKS, (json.dumps(current) + '\n').encode(), BLOCKS.stat().st_mode & 0o777)
            print('Owned Alexa tile blocks removed. Other entries and backup retained.')
            return
        result = subprocess.run(['luna-send', '-w', '3000', '-n', '1',
            'luna://com.webos.service.tv.systemproperty/getSystemInfo',
            '{"keys":["modelName","firmwareVersion","sdkVersion"]}'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=6)
        info = json.loads(result.stdout)
        if result.returncode or info.get('returnValue') is not True or [info.get(k) for k in (
                'modelName', 'firmwareVersion', 'sdkVersion')] != ['OLED48C24LA', '33.31.68', '10.3.1']:
            raise RuntimeError('Unreviewed TV/firmware')
        for appid in IDS:
            metadata = json.loads((Path('/usr/palm/applications') / appid / 'appinfo.json').read_text())
            if metadata.get('id') != appid:
                raise RuntimeError('Alexa app identity mismatch')
        if HOOK.exists() and MARKER not in HOOK.read_text():
            raise RuntimeError('Hook ownership conflict')
        before = BLOCKS.read_bytes()
        current = document()
        if not STATE.exists():
            write(STATE, (json.dumps({'added': [x for x in IDS if x not in current['blocked_system_applist']],
                                     'original_document': current}) + '\n').encode())
        for appid in IDS:
            if appid not in current['blocked_system_applist']:
                current['blocked_system_applist'].append(appid)
        if BLOCKS.read_bytes() != before:
            raise RuntimeError('Block list changed during apply')
        if before != (json.dumps(current) + '\n').encode():
            write(BLOCKS, (json.dumps(current) + '\n').encode(), BLOCKS.stat().st_mode & 0o777)
        verify()
        if args.action == 'install-startup':
            write(SCRIPT, Path(__file__).read_bytes(), 0o700)
            HOOK.parent.mkdir(parents=True, exist_ok=True)
            write(HOOK, ('#!/bin/sh\n' + MARKER + '\n(python3 ' + str(SCRIPT) +
                ' boot >' + str(ROOT / 'startup.log') + ' 2>&1) </dev/null >/dev/null 2>&1 &\n').encode(), 0o700)
            print('Alexa tile startup repair installed.')
        print('Built-in packages retained. No SDX or service changes. Reopen LG Home to inspect.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('STOP: ' + str(error), file=sys.stderr)
        sys.exit(1)
