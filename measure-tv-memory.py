#!/usr/bin/env python3
"""Read-only RAM samples. No cache dropping, process stops or app launches."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

APP = 'com.local.hdmihome'


def numeric_fields(path):
    fields = {}
    for line in Path(path).read_text().splitlines():
        key, separator, rest = line.partition(':')
        if separator and rest.split() and rest.split()[0].isdigit():
            fields[key] = int(rest.split()[0])
    return fields


def foreground():
    try:
        result = subprocess.run(['luna-send', '-w', '2000', '-n', '1',
            'luna://com.webos.applicationManager/getForegroundAppInfo', '{}'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=4)
        return json.loads(result.stdout)
    except Exception as error:
        return {'unavailable': str(error)}


def process_memory(directory):
    status = numeric_fields(directory / 'status')
    try:
        name = (directory / 'comm').read_text().strip()
    except OSError:
        name = '?'
    try:
        executable = os.readlink(str(directory / 'exe'))
    except OSError:
        executable = name
    # Read arguments only for matching; never include raw arguments in reports.
    try:
        args = (directory / 'cmdline').read_bytes().replace(b'\0', b' ').decode('utf-8', errors='replace')
    except OSError:
        args = ''
    try:
        memory = numeric_fields(directory / 'smaps_rollup')
        origin = 'smaps_rollup'
    except OSError:
        try:
            memory = {}
            for line in (directory / 'smaps').read_text().splitlines():
                parts = line.split()
                if len(parts) == 3 and parts[2] == 'kB' and parts[0].endswith(':'):
                    key = parts[0][:-1]
                    if key in ('Rss', 'Pss', 'Private_Clean', 'Private_Dirty', 'Swap', 'SwapPss'):
                        memory[key] = memory.get(key, 0) + int(parts[1])
            origin = 'smaps'
        except OSError:
            memory, origin = {}, 'status_only'
    return {'pid': int(directory.name), 'name': name, 'executable': executable,
            'dashboard_id_in_arguments': APP in args,
            'rss_kib': memory.get('Rss', status.get('VmRSS', 0)),
            'pss_kib': memory.get('Pss'),
            'private_kib': memory.get('Private_Clean', 0) + memory.get('Private_Dirty', 0) if memory else None,
            'swap_kib': memory.get('Swap', status.get('VmSwap', 0)),
            'swap_pss_kib': memory.get('SwapPss'), 'source': origin}


def sample():
    # Capture foreground before reading memory; the temporary luna-send process
    # has exited before /proc is scanned.
    front = foreground()
    mem = numeric_fields('/proc/meminfo')
    processes, skipped = [], 0
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit():
            continue
        try:
            processes.append(process_memory(directory))
        except (OSError, ValueError):
            skipped += 1
    processes.sort(key=lambda row: row['pss_kib'] if row['pss_kib'] is not None else row['rss_kib'], reverse=True)
    return {'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'uptime_seconds': float(Path('/proc/uptime').read_text().split()[0]),
        'foreground': front, 'dashboard_foreground': front.get('appId') == APP,
        'meminfo_kib': mem,
        'used_excluding_available_kib': mem['MemTotal'] - mem['MemAvailable'] if 'MemAvailable' in mem else None,
        'swap_used_kib': mem.get('SwapTotal', 0) - mem.get('SwapFree', 0),
        'observer_pid': os.getpid(), 'skipped_processes': skipped,
        'pss_available_processes': sum(row['pss_kib'] is not None for row in processes),
        'dashboard_candidates': [row for row in processes if row['dashboard_id_in_arguments']],
        'processes': processes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples', type=int, default=3)
    parser.add_argument('--interval', type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.samples <= 10 or not 1 <= args.interval <= 60:
        raise RuntimeError('Samples must be 1..10 and interval 1..60 seconds')
    result = {'mode': 'READ ONLY', 'units': 'KiB (1024 bytes); divide by 1024 for MiB',
        'notes': ['Used = MemTotal minus MemAvailable; cache is not automatically wasted memory.',
                  'PSS apportions shared mappings; summing RSS double-counts shared pages.',
                  'Dashboard candidates match its app ID in process arguments; shared web-engine helpers may not be attributable.',
                  'The Python observer and SSH server consume RAM during measurement; observer PID is included.',
                  'No settings, caches, services, apps or boot hooks are changed.'], 'samples': []}
    for index in range(args.samples):
        if index:
            time.sleep(args.interval)
        result['samples'].append(sample())
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
