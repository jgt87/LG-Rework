#!/usr/bin/env python3
"""Install/launch this local dashboard only. No Home routing or startup changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

APPID = 'com.local.hdmihome'
APPDIR = Path('/media/developer/apps/usr/palm/applications') / APPID
IPK = Path('/tmp/lg-hdmi-home.ipk')


def request(service, method, payload):
    result = subprocess.run(['luna-send', '-w', '8000', '-n', '1',
                             'luna://' + service + '/' + method, json.dumps(payload)],
                            capture_output=True, text=True, timeout=12)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    reply = json.loads(result.stdout)
    if reply.get('returnValue') is not True:
        raise RuntimeError(json.dumps(reply))
    return reply


def check_app(version, expected_js):
    info = json.loads((APPDIR / 'appinfo.json').read_text())
    if info.get('id') != APPID or info.get('version') != version:
        raise RuntimeError('Installed app ID/version differs from this build')
    actual = hashlib.sha256((APPDIR / 'app.js').read_bytes()).hexdigest()
    if actual != expected_js:
        raise RuntimeError('Installed JavaScript hash differs from this build')
    print('Verified installed app:', APPID, 'version', version, flush=True)


def install(version, expected_ipk, expected_js):
    if hashlib.sha256(IPK.read_bytes()).hexdigest() != expected_ipk:
        raise RuntimeError('Uploaded package SHA-256 mismatch; installation not started')
    payload = {'id': APPID, 'ipkUrl': str(IPK), 'subscribe': True}
    proc = subprocess.Popen(['luna-send', '-w', '60000', '-i',
                             'luna://com.webos.appInstallService/dev/install', json.dumps(payload)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    decoder = json.JSONDecoder()
    buffer = ''
    deadline = time.monotonic() + 65
    complete = False
    try:
        while time.monotonic() < deadline and not complete:
            ready, _, _ = select.select([proc.stdout], [], [], min(1, max(0, deadline-time.monotonic())))
            if not ready:
                if proc.poll() is not None:
                    break
                continue
            chunk = os.read(proc.stdout.fileno(), 16384)
            if not chunk:
                break
            buffer += chunk.decode('utf-8', errors='replace')
            while buffer.strip():
                buffer = buffer.lstrip()
                try:
                    event, end = decoder.raw_decode(buffer)
                except json.JSONDecodeError:
                    break
                buffer = buffer[end:]
                print('Install:', json.dumps(event), flush=True)
                details = event.get('details') or {}
                if event.get('returnValue') is False or details.get('errorCode'):
                    raise RuntimeError('TV rejected the package: ' + json.dumps(event))
                if event.get('statusValue') == 30 or details.get('state') == 'installed':
                    packageid = details.get('packageId')
                    if packageid and packageid != APPID:
                        raise RuntimeError('Unexpected installed package ID: ' + packageid)
                    complete = True
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        proc.stdout.close()
    if not complete:
        print('No terminal install event. Checking installed files; do not automatically retry.', flush=True)
    check_app(version, expected_js)
    print('Installation complete. Startup and Home-button routing are unchanged.')
    print('Launch response:', request('com.webos.applicationManager', 'launch', {'id': APPID}))
    print('Launch accepted. Confirm the dashboard and input switching on the TV.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'verify', 'launch'])
    parser.add_argument('--version', required=True)
    parser.add_argument('--ipk-sha', required=True)
    parser.add_argument('--js-sha', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('Connect to the TV as root')
    for digest in [args.ipk_sha, args.js_sha]:
        if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise RuntimeError('Invalid expected SHA-256')
    info = request('com.webos.service.tv.systemproperty', 'getSystemInfo',
                   {'keys': ['modelName', 'sdkVersion', 'firmwareVersion']})
    print('Connected:', info.get('modelName'), info.get('firmwareVersion'), info.get('sdkVersion'), flush=True)
    if info.get('modelName') != 'OLED48C24LA':
        raise RuntimeError('Unexpected TV model')
    if args.action == 'install':
        install(args.version, args.ipk_sha, args.js_sha)
    else:
        check_app(args.version, args.js_sha)
        if args.action == 'launch':
            print('Launch response:', request('com.webos.applicationManager', 'launch', {'id': APPID}))
            print('Launch accepted. Confirm the screen and HDMI buttons using the TV remote.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('STOP:', error, file=sys.stderr)
        sys.exit(1)
