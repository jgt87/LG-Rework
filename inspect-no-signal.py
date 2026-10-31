#!/usr/bin/env python3
"""Read-only discovery of HDMI No Signal settings and UI resources."""
import json
import hashlib
from pathlib import Path
import re
import subprocess


def request(uri, payload):
    try:
        result = subprocess.run(['luna-send', '-w', '3000', '-n', '1', uri, json.dumps(payload)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=6)
        return {'exit': result.returncode, 'stdout': result.stdout.decode(errors='replace'),
                'stderr': result.stderr.decode(errors='replace')}
    except Exception as error:
        return {'error': str(error)}


def main():
    pattern = re.compile(r'no.?signal|signal.?lost|no.?input|nosignalScreenSaver', re.I)
    report = {'mode': 'READ ONLY; no settings, apps, mounts or services changed',
        'identity': request('luna://com.webos.service.tv.systemproperty/getSystemInfo',
            {'keys': ['modelName', 'firmwareVersion', 'sdkVersion']}),
        'gallery_setting': request('luna://com.webos.settingsservice/getSystemSettings',
            {'category': 'general', 'keys': ['noSignalScreenSaver']}), 'apps': {}}
    for appid in ['com.webos.app.hdmi1', 'com.webos.app.hdmi2', 'com.webos.app.hdmi3',
                  'com.webos.app.hdmi4', 'com.webos.app.inputcommon',
                  'com.webos.app.livetv', 'com.webos.app.screensaver']:
        directory = Path('/usr/palm/applications') / appid
        entry = {'path': str(directory), 'matches': [], 'inventory': [], 'truncated': False}
        info = directory / 'appinfo.json'
        if info.is_file():
            entry['metadata'] = json.loads(info.read_text())
        count = 0
        for path in directory.rglob('*'):
            if not path.is_file():
                continue
            count += 1
            if count > 3000:
                entry['truncated'] = True
                break
            relative = str(path.relative_to(directory))
            if len(entry['inventory']) < 300:
                entry['inventory'].append(relative)
            if pattern.search(relative):
                entry['matches'].append({'path': relative, 'reason': 'filename'})
            if path.suffix.lower() in ('.qml', '.js', '.json', '.xml', '.html'):
                try:
                    if path.stat().st_size > 1048576:
                        continue
                    hits = []
                    for number, line in enumerate(path.read_text(errors='replace').splitlines(), 1):
                        if pattern.search(line):
                            hits.append({'line': number, 'text': line[:600]})
                            if len(hits) >= 6:
                                break
                    if hits:
                        entry['matches'].append({'path': relative, 'hits': hits})
                except OSError:
                    pass
            if len(entry['matches']) >= 150:
                entry['truncated'] = True
                break
        entry['scanned_files'] = min(count, 3000)
        report['apps'][appid] = entry
    # Follow the exact presentation components found in the first inventory.
    # Capture complete source, rather than inferring behavior from search snippets.
    base = Path('/usr/palm/applications/com.webos.app.inputcommon/qml')
    report['presentation_sources'] = {}
    for relative in [
            'Interfaces/ScreensaverInterfaces/NoSignalPhotoModel.qml',
            'Interfaces/ScreensaverInterfaces/AppServices.js',
            'UserInterfaceLayer/Containers/BgViewLayer/PhotoSlide.qml',
            'UserInterfaceLayer/Containers/BgViewLayer/Screensaver.qml',
            'UserInterfaceLayer/Containers/BgViewLayer/ScreensaverMainText.qml',
            'UserInterfaceLayer/Containers/BgViewLayer/ScreensaverSubText.qml',
            'UserInterfaceLayer/Containers/BgViewLayer/RandomMoveItem.qml']:
        path = base / relative
        if path.is_file() and path.stat().st_size <= 262144:
            data = path.read_bytes()
            report['presentation_sources'][relative] = {
                'sha256': hashlib.sha256(data).hexdigest(),
                'text': data.decode('utf-8', errors='replace')}
        else:
            report['presentation_sources'][relative] = {'unavailable': True}
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
