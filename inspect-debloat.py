#!/usr/bin/env python3
"""Read-only inventory for a reviewed HDMI-only debloat. Never stops services."""
import json
from pathlib import Path
import re
import subprocess

PATTERN = re.compile(r'acr|adoverlay|advert|contentminer|logger|rdxd|dmost|mycar|familycare|buddyconnector|camera|voice|alexa|iconnectivity|sportsalarm|uploadd|nlpmanager|performer|remotediag|nudge', re.I)
PROTECTED = ['sdx.service', 'sam.service', 'surface-manager.service', 'WebAppMgr.service',
             'tvpower.service', 'audio.service', 'connman.service', 'devmode.service',
             'alwaysready.service', 'tvdataexchanger.service']


def command(args):
    try:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, timeout=12)
        return {'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
    except Exception as error:
        return {'error': str(error)}


def main():
    report = {'mode': 'READ ONLY; no settings or services changed',
              'sdx': 'EXPLICITLY PROTECTED; do not disable, mask, stop or replace',
              'identity': command(['luna-send', '-w', '3000', '-n', '1',
                'luna://com.webos.service.tv.systemproperty/getSystemInfo',
                '{"keys":["modelName","firmwareVersion","sdkVersion"]}'])}
    units = command(['systemctl', 'list-unit-files', '--no-pager', '--no-legend'])
    report['unit_listing'] = units
    names = set(PROTECTED)
    for line in units.get('stdout', '').splitlines():
        fields = line.split()
        if fields and PATTERN.search(fields[0]):
            names.add(fields[0])
    report['units'] = {}
    for name in sorted(names):
        report['units'][name] = {
            'properties': command(['systemctl', 'show', name, '--no-pager',
                '--property=Id,LoadState,ActiveState,SubState,UnitFileState,FragmentPath,ExecStart,Restart,Requires,Wants,Requisite,BindsTo,PartOf,Conflicts,Before,After,RequiredBy,WantedBy,BoundBy,ConsistsOf']),
            'definition': command(['systemctl', 'cat', name, '--no-pager']),
            'reverse_dependencies': command(['systemctl', 'list-dependencies', '--reverse', '--all', '--no-pager', name])}
    report['luna_specs'] = {}
    for base in ('/usr/share/luna-service2/services', '/usr/share/luna-service2/system-services',
                 '/var/luna-service2/services'):
        directory = Path(base)
        if directory.is_dir():
            for path in directory.glob('*.service'):
                if PATTERN.search(path.name) or 'sdx' in path.name.lower():
                    report['luna_specs'][str(path)] = path.read_text(errors='replace')[:16384]
    report['candidate_processes'] = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            # Executable only: do not collect command arguments or environment secrets.
            executable = str((proc / 'exe').resolve(strict=True))
            if PATTERN.search(Path(executable).name) or Path(executable).name == 'sdx':
                report['candidate_processes'].append({'pid': int(proc.name), 'executable': executable})
        except (OSError, RuntimeError):
            pass
    report['memory'] = '\n'.join(line for line in Path('/proc/meminfo').read_text().splitlines()
                                  if line.startswith(('MemTotal:', 'MemAvailable:')))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
