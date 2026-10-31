#!/usr/bin/env python3
"""Reversible, firmware-specific LG Home layout override. No service debloating."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

TARGET = Path('/usr/palm/applications/com.webos.app.home/data/flutter_assets/assets/home.xml')
ROOT = Path('/var/lib/lg-home-layout')
ORIGINAL = ROOT / 'original-home.xml'
CUSTOM = ROOT / 'clean-home.xml'
SCRIPT = ROOT / 'lg-home-layout.py'
HOOK = Path('/var/lib/webosbrew/init.d/84-lg-home-layout')
EXPECTED = '8f0bf119efe54285c44e15ed9f608da9f38dd94178e73ec5441f22df3d5aa9d7'
MARKER = '# Managed by lg-home-layout'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def transform(data):
    if digest(data) != EXPECTED:
        raise RuntimeError('Unreviewed LG layout; refusing to change it.')
    # This is deliberately a patch for one checksum-locked file, not an XML
    # parser. webOS ships Python without the xml standard-library package.
    changes = [
        (b'\t\t\t<item id="qcardList" itemWidth="3840" itemHeight="180" focusType="scope" autoFocus="false"/>\n', b''),
        (b'\t\t\t<item id="recommendedShelf" itemWidth="3798" itemHeight="531" focusType="scope" autoFocus="false"/>\n', b''),
        (b'<item id="container" hasChildren="true" itemWidth="3840" itemHeight="900" focusType="scope">',
         b'<item id="container" hasChildren="true" itemWidth="3840" itemHeight="1611" focusType="scope">'),
        (b'<item id="herobanner" itemWidth="3492" itemHeight="900" focusType="scope" autoFocus="false"/>',
         b'<item id="herobanner" itemWidth="0" itemHeight="0" focusType="none" autoFocus="false"/>')]
    for original, replacement in changes:
        if data.count(original) != 1:
            raise RuntimeError('Expected unique layout fragment missing')
        data = data.replace(original, replacement, 1)
    return data


def run(args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8).stdout


def preflight():
    if os.geteuid() != 0:
        raise RuntimeError('Root required')
    reply = json.loads(run(['luna-send', '-w', '3000', '-n', '1',
        'luna://com.webos.service.tv.systemproperty/getSystemInfo',
        '{"keys":["modelName","firmwareVersion","sdkVersion"]}']))
    if reply.get('returnValue') is not True or tuple(reply.get(k) for k in (
            'modelName', 'firmwareVersion', 'sdkVersion')) != ('OLED48C24LA', '33.31.68', '10.3.1'):
        raise RuntimeError('Unreviewed TV/firmware: ' + str(reply))


def mount_records():
    return [line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines()
            if len(line.split()) > 6 and line.split()[4] == str(TARGET)]


def owned_mount():
    records = mount_records()
    if not records:
        return False
    if len(records) != 1 or not CUSTOM.exists() or not os.path.samestat(TARGET.stat(), CUSTOM.stat()):
        raise RuntimeError('Another mount covers Home layout; refusing to touch it.')
    return True


def atomic(path, data, mode=0o600):
    temp = path.with_name(path.name + '.tmp')
    with temp.open('wb') as stream:
        os.chmod(str(temp), mode)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temp), str(path))


def home_process(data):
    args = data.rstrip(b'\0').split(b'\0')
    return bool(args and args[0].split(b'/')[-1] == b'flutter-client' and
                any(args[i:i+2] == [b'-i', b'com.webos.app.home'] for i in range(1, len(args)-1)))


def restart_home():
    # Exact executable and -i argument; never stop other Flutter apps or SAM.
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if home_process((proc / 'cmdline').read_bytes()):
                if home_process((proc / 'cmdline').read_bytes()):
                    os.kill(int(proc.name), signal.SIGTERM)
                    print('Requested LG Home reload, PID ' + proc.name)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue


def verify():
    if not owned_mount():
        raise RuntimeError('Layout override is not mounted')
    wanted = transform(ORIGINAL.read_bytes())
    if TARGET.read_bytes() != wanted or CUSTOM.read_bytes() != wanted:
        raise RuntimeError('Mounted layout does not match expected cleanup')
    print('Verified mounted layout: Quick Cards and recommendation/device shelf removed; banner artwork hidden.')
    print('App row, native navigation and quickGuide retained. Visual result needs checking on TV.')


def apply(persistent=False, boot=False):
    preflight()
    mounted = owned_mount()
    source = ORIGINAL.read_bytes() if mounted else TARGET.read_bytes()
    wanted = transform(source)
    if ORIGINAL.exists() and ORIGINAL.read_bytes() != source:
        raise RuntimeError('Original backup conflicts with current LG layout')
    if HOOK.exists() and MARKER not in HOOK.read_text():
        raise RuntimeError('Startup hook already belongs to another tool')
    if not ORIGINAL.exists():
        atomic(ORIGINAL, source)
    changed = not mounted
    if mounted:
        if TARGET.read_bytes() != wanted:
            previous = CUSTOM.read_bytes()
            run(['umount', str(TARGET)])
            try:
                atomic(CUSTOM, wanted, 0o644)
                run(['mount', '--bind', str(CUSTOM), str(TARGET)])
                verify()
                changed = True
            except Exception:
                if owned_mount():
                    run(['umount', str(TARGET)])
                atomic(CUSTOM, previous, 0o644)
                run(['mount', '--bind', str(CUSTOM), str(TARGET)])
                raise
        else:
            verify()
    else:
        atomic(CUSTOM, wanted, 0o644)
        try:
            run(['mount', '--bind', str(CUSTOM), str(TARGET)])
            verify()
        except Exception:
            if owned_mount():
                run(['umount', str(TARGET)])
            raise
    if persistent:
        atomic(SCRIPT, Path(__file__).read_bytes(), 0o700)
        atomic(HOOK, ('#!/bin/sh\n' + MARKER + '\n(python3 ' + str(SCRIPT) +
                      ' boot >' + str(ROOT / 'startup.log') + ' 2>&1) </dev/null >/dev/null 2>&1 &\n').encode(), 0o700)
        print('Startup hook installed: ' + str(HOOK))
    if changed:
        restart_home()
    print('No LG files overwritten; no apps, services, CEC or dashboard routing changed.')
    if not persistent and not boot:
        print('Trial only: reboot removes this mount. Use install-startup after visual validation.')


def restore():
    if HOOK.exists():
        if MARKER not in HOOK.read_text():
            raise RuntimeError('Startup hook ownership mismatch')
    mounted = owned_mount()
    if mounted and digest(ORIGINAL.read_bytes()) != EXPECTED:
        raise RuntimeError('Backup checksum mismatch')
    if HOOK.exists():
        HOOK.unlink()
    if mounted:
        run(['umount', str(TARGET)])
        restart_home()
    print('Override removed; original LG layout exposed. Backup retained.')


def self_test(fixture):
    import unittest
    check = unittest.TestCase()
    source = Path(fixture).read_bytes()
    cleaned = transform(source)
    check.assertNotIn(b'id="qcardList"', cleaned)
    check.assertNotIn(b'id="recommendedShelf"', cleaned)
    for name in ('appList', 'quickGuide', 'globalline', 'herobanner'):
        check.assertIn(('id="' + name + '"').encode(), cleaned)
    check.assertIn(b'<item id="herobanner" itemWidth="0" itemHeight="0" focusType="none" autoFocus="false"/>', cleaned)
    def total(data):
        import re
        # Nested side navigation and banner do not contribute page-row height.
        return sum(int(height) for name, height in re.findall(
            rb'<item id="([^"]+)"[^>]*itemHeight="([0-9]+)"', data)
            if name not in (b'globalline', b'herobanner'))
    check.assertEqual(total(source), total(cleaned))
    for line in source.splitlines():
        if not any(('id="' + name + '"').encode() in line for name in (
                'qcardList', 'recommendedShelf', 'container', 'herobanner')):
            check.assertIn(line, cleaned.splitlines())
    check.assertEqual(transform(source), cleaned)
    check.assertRaises(RuntimeError, transform, source + b' ')
    check.assertTrue(home_process(b'/usr/bin/flutter-client\0-i\0com.webos.app.home\0'))
    check.assertFalse(home_process(b'/usr/bin/flutter-client\0-i\0com.webos.app.settings\0'))
    check.assertFalse(home_process(b'/usr/bin/python3\0com.webos.app.home\0'))
    print('Checks passed: known-layout guard, removed rows, preserved navigation/height, exact Home process.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['apply', 'verify', 'restore', 'install-startup', 'boot', 'self-test'])
    parser.add_argument('--fixture')
    args = parser.parse_args()
    if args.action == 'self-test':
        self_test(args.fixture)
        return
    if os.geteuid() != 0:
        raise RuntimeError('Root required')
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (ROOT / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action == 'restore':
            restore()
        elif args.action == 'verify':
            verify()
        else:
            if args.action == 'boot':
                for attempt in range(15):
                    try:
                        preflight()
                        break
                    except (subprocess.SubprocessError, json.JSONDecodeError):
                        if attempt == 14:
                            raise
                        time.sleep(2)
            apply(persistent=args.action == 'install-startup', boot=args.action == 'boot')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('STOP: ' + str(error), file=sys.stderr)
        sys.exit(1)
