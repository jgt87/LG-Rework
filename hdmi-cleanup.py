#!/usr/bin/env python3
"""Reversible, inventory-specific cleanup for OLED48C24LA / 33.31.68.

Independent implementation informed by D-Rekk's webos-debloat gist.
No app deletion, firmware writes, or service removal. Optional removable boot hook.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import shlex
import time
from contextlib import contextmanager

ROOT = Path('/var/lib/lg-hdmi-cleanup')
STATE = ROOT / 'original-state.json'
HOOK = Path('/var/lib/webosbrew/init.d/90-lg-hdmi-cleanup')
PERSISTENT = ROOT / 'hdmi-cleanup.py'
BOOT_LOG = ROOT / 'startup.log'
HOOK_MARKER = '# Managed by lg-hdmi-cleanup; removable with uninstall-startup.'
BLOCKS = Path('/var/preferences/com.webos.applicationManager/blockedSystemAppList/NLD.json')
PRELOAD = Path('/var/preferences/webos-preload-manager-conf.json')
TARGET_TILES = '''com.webos.app.lgchannels com.lge.app.viewster
com.webos.app.homeconnect com.webos.app.homeoffice com.webos.app.lifeonscreen
com.webos.app.premium com.webos.app.quicklinkcopilot com.webos.app.sportsteamsettings
com.webos.app.totalmusic com.webos.app.familycare com.webos.app.learning
com.webos.app.rdp com.webos.app.tvuserguide com.webos.app.helpandtips
com.webos.app.camera com.webos.app.multiviewsettings'''.split()
TARGET_PRELOADS = '''com.webos.app.lgchannels com.webos.app.browser
com.webos.app.voice youtube.leanback.v4 netflix amazon vudu pooq
globoplaywebos yandex.alice'''.split()
TARGET_SETTINGS = [('general', 'homePromotion'), ('general', 'sportsAlarm'),
                   ('option', 'livePromotion'), ('option', 'webOSPromotionVideo'),
                   ('option', 'promotionStreamer'), ('option', 'livePlus'),
                   ('other', 'contentRecommendation')]
PROTECTED = {'com.webos.app.home', 'com.webos.app.livetv', 'com.webos.app.gameoptimizer',
             'com.webos.app.hdmi1', 'com.webos.app.hdmi2', 'com.webos.app.hdmi3',
             'com.webos.app.hdmi4', 'com.palm.app.settings', 'org.webosbrew.hbchannel'}


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


def luna(service, method, payload):
    result = subprocess.run(['luna-send', '-w', '5000', '-n', '1',
                             'luna://' + service + '/' + method, json.dumps(payload)],
                            capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise RuntimeError('Luna call failed: ' + service + '/' + method + ': ' + result.stderr)
    reply = json.loads(result.stdout)
    if reply.get('returnValue') is not True:
        raise RuntimeError('Luna rejected ' + method + ': ' + json.dumps(reply))
    return reply


def setting(category, key):
    return luna('com.webos.settingsservice', 'getSystemSettings',
                {'category': category, 'keys': [key]})['settings'][key]


def set_setting(category, key, value):
    luna('com.webos.settingsservice', 'setSystemSettings',
         {'category': category, 'settings': {key: value}})
    if setting(category, key) != value:
        raise RuntimeError('Setting readback mismatch: ' + key)


def policy():
    apps = luna('com.webos.service.preloadmanager', 'getPreloadPolicy', {})['applications']
    return {app['id']: app for app in apps}


def set_preload(appid, enabled):
    luna('com.webos.service.preloadmanager', 'setPreloadPolicy',
         {'application': {'id': appid, 'isEnabled': enabled}})


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def atomic_write(path, text):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp-' + str(os.getpid()))
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    try:
        with temp.open('x', encoding='utf-8', newline='') as stream:
            os.chmod(str(temp), mode)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temp), str(path))
    finally:
        if temp.exists():
            temp.unlink()


def encode(value):
    return json.dumps(value, separators=(',', ':')) + '\n'


def file_change(path, new):
    original = path.read_text(encoding='utf-8')
    return {'path': str(path), 'original': original, 'new': encode(new)}


def plan_files(block_doc, preload_doc, apps):
    if not isinstance(block_doc.get('blocked_system_applist'), list):
        raise RuntimeError('Unexpected NLD block-list schema')
    if not isinstance(preload_doc.get('allowedApps'), dict):
        raise RuntimeError('Unexpected persistent preload schema')
    if PROTECTED.intersection(TARGET_TILES + TARGET_PRELOADS):
        raise RuntimeError('Protected app included in cleanup')
    blocks = json.loads(json.dumps(block_doc))
    preloads = json.loads(json.dumps(preload_doc))
    for appid in TARGET_TILES:
        if appid not in blocks['blocked_system_applist']:
            blocks['blocked_system_applist'].append(appid)
    for appid in TARGET_PRELOADS:
        if appid in apps:
            preloads['allowedApps'][appid] = False
    return blocks, preloads


def make_plan():
    info = luna('com.webos.service.tv.systemproperty', 'getSystemInfo',
                {'keys': ['modelName', 'firmwareVersion', 'sdkVersion']})
    if not reviewed_tv(info, 'hdmi-cleanup'):
        raise RuntimeError('TV identity/version differs from reviewed inventory: ' + json.dumps(info))
    if not BLOCKS.is_file() or not PRELOAD.is_file():
        raise RuntimeError('Expected NLD block list / preload configuration is missing')
    apps = policy()
    blocks, preloads = plan_files(json.loads(BLOCKS.read_text()), json.loads(PRELOAD.read_text()), apps)
    settings = []
    for category, key in TARGET_SETTINGS:
        value = setting(category, key)
        if value not in ('on', 'off'):
            raise RuntimeError('Unexpected setting type/value: ' + key)
        if value == 'on':
            settings.append({'category': category, 'key': key, 'original': value})
    return {'version': 1, 'tv': info,
            'files': [file_change(BLOCKS, blocks), file_change(PRELOAD, preloads)],
            'settings': settings,
            'preloads': {appid: apps[appid]['isEnabled'] for appid in TARGET_PRELOADS
                         if appid in apps and apps[appid].get('isEnabled') is True}}


def show(plan):
    for change in plan['files']:
        print('Configuration:', change['path'])
    print('System tiles to hide (not delete):', ', '.join(TARGET_TILES))
    print('Preloads to disable:', ', '.join(plan['preloads']))
    print('Settings to turn off:', ', '.join(item['key'] for item in plan['settings']))
    print('Preserves HDMI1-4, Home, Settings, Game Optimizer, Live TV, audio and OLED protection.')
    print('Home Auto Launch is not modified. Startup repair installed:', HOOK.is_file())


def diagnose(plan):
    print('=== Read-only post-reboot diagnosis ===')
    print('Delayed startup repair installed:', HOOK.is_file())
    if BOOT_LOG.is_file():
        print('Recent startup log:\n' + BOOT_LOG.read_text(encoding='utf-8', errors='replace')[-6000:])
    for change in plan['files']:
        path = Path(change['path'])
        print('\nConfiguration:', str(path))
        if not path.is_file():
            print('MISSING')
            continue
        current = path.read_text(encoding='utf-8')
        print('Current JSON:', current)
        print('Exact match to applied contents:', digest(current) == digest(change['new']))
        if path == BLOCKS:
            ids = json.loads(current)['blocked_system_applist']
            print('Missing target entries:', ', '.join(app for app in TARGET_TILES if app not in ids))
    print('\nCurrent preload policy:', json.dumps(policy()))
    for item in plan['settings']:
        print('Setting:', item['category'], item['key'], setting(item['category'], item['key']))
    bases = ['/media/system/apps/usr/palm/applications', '/usr/palm/applications',
             '/mnt/otncabi/usr/palm/applications', '/mnt/otycabi/usr/palm/applications']
    print('\nTarget app metadata:')
    for appid in TARGET_TILES:
        for base in bases:
            path = Path(base) / appid / 'appinfo.json'
            if path.is_file():
                info = json.loads(path.read_text())
                print(str(path), json.dumps({key: info[key] for key in
                      ['id', 'title', 'type', 'visible', 'removable', 'systemApp', 'lockable'] if key in info}))
    print('No changes made. Original backup retained.')


def verify(plan):
    errors = []
    current_blocks = json.loads(BLOCKS.read_text())['blocked_system_applist']
    for appid in TARGET_TILES:
        if appid not in current_blocks:
            errors.append('tile not hidden: ' + appid)
    conf = json.loads(PRELOAD.read_text())['allowedApps']
    live = policy()
    planned_conf = json.loads(plan['files'][1]['new'])['allowedApps']
    for appid in TARGET_PRELOADS:
        if appid not in planned_conf or planned_conf[appid] is not False:
            continue
        if conf.get(appid) is not False:
            errors.append('persistent preload not disabled: ' + appid)
        if live.get(appid, {}).get('isEnabled') is True and live.get(appid, {}).get('isAllowed') is not False:
            errors.append('runtime preload still active: ' + appid)
    for item in plan['settings']:
        if setting(item['category'], item['key']) != 'off':
            errors.append('setting still enabled: ' + item['key'])
    if errors:
        print('Delayed startup repair installed:', HOOK.is_file(), flush=True)
        if BOOT_LOG.is_file():
            print('Recent startup log:\n' + BOOT_LOG.read_text(encoding='utf-8', errors='replace')[-4000:], flush=True)
        raise RuntimeError('\n'.join(errors))
    print('Verified: target tiles blocked, persistent preloads disabled, promotional settings off.')
    print('Memory now:')
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith(('MemTotal:', 'MemAvailable:')):
            print(line)
    print('Tile hiding does not disable services. No RAM saving is assumed until measured after reboot.')


def merge_blocks(current, desired):
    result = json.loads(json.dumps(current))
    ids = result.get('blocked_system_applist')
    if not isinstance(ids, list) or not all(isinstance(app, str) for app in ids):
        raise RuntimeError('Unexpected current block-list schema')
    for appid in desired:
        if appid in PROTECTED:
            raise RuntimeError('Refusing to block protected app: ' + appid)
        if appid not in ids:
            ids.append(appid)
    return result


def rollback_document(change, current):
    original = json.loads(change['original'])
    applied = json.loads(change['new'])
    result = json.loads(json.dumps(current))
    if change['path'] == str(BLOCKS):
        owned = set(applied['blocked_system_applist']) - set(original['blocked_system_applist'])
        result['blocked_system_applist'] = [app for app in current['blocked_system_applist'] if app not in owned]
    elif change['path'] == str(PRELOAD):
        old = original['allowedApps']
        new = applied['allowedApps']
        allowed = result['allowedApps']
        for appid, value in new.items():
            if appid in old and old[appid] == value:
                continue
            if appid in allowed and allowed[appid] != value and (appid not in old or allowed[appid] != old[appid]):
                raise RuntimeError('Later preload edit requires manual review: ' + appid)
            if appid in old:
                allowed[appid] = old[appid]
            else:
                allowed.pop(appid, None)
    else:
        raise RuntimeError('Unexpected backup path')
    return result


def repair_settings(plan):
    # Only repair settings owned by the original cleanup snapshot. Do not
    # expand scope or overwrite that snapshot when LG resets a value later.
    pending = []
    for item in plan['settings']:
        category, key = item['category'], item['key']
        if (category, key) not in TARGET_SETTINGS or item['original'] != 'on':
            raise RuntimeError('Unexpected setting in cleanup backup: ' + key)
        value = setting(category, key)
        if value not in ('on', 'off'):
            raise RuntimeError('Unexpected current setting value: ' + key)
        if value == 'on':
            pending.append((category, key))
    for category, key in pending:
        set_setting(category, key, 'off')
        print('Restored setting to off:', category, key, flush=True)
    return pending


def repair(plan):
    change = next(item for item in plan['files'] if item['path'] == str(BLOCKS))
    current_text = BLOCKS.read_text(encoding='utf-8')
    current = json.loads(current_text)
    original_ids = set(json.loads(change['original'])['blocked_system_applist'])
    desired = [app for app in json.loads(change['new'])['blocked_system_applist'] if app not in original_ids]
    merged = merge_blocks(current, desired)
    missing = [app for app in desired if app not in current['blocked_system_applist']]
    if missing:
        snapshot = ROOT / ('blocks-before-repair-' + str(time.time_ns()) + '-' + str(os.getpid()) + '.json')
        if snapshot.exists():
            raise RuntimeError('Repair snapshot already exists; refusing to overwrite')
        atomic_write(snapshot, current_text)
        if BLOCKS.read_text(encoding='utf-8') != current_text:
            raise RuntimeError('LG changed the block list during repair; no replacement written')
        atomic_write(BLOCKS, encode(merged))
        print('Re-added:', ', '.join(missing), flush=True)
        print('Original backup unchanged. Current pre-repair list saved to', snapshot)
    else:
        print('No missing entries to repair.')
    repair_settings(plan)
    time.sleep(5)
    verify(plan)
    print('Verified after 5 seconds. Persistence across a future reboot remains unconfirmed.')


def hook_text(python):
    return ('#!/bin/sh\n' + HOOK_MARKER + '\n' +
            'exec ' + shlex.quote(python) + ' ' + shlex.quote(str(PERSISTENT)) + ' boot-start\n')


def remove_startup():
    if HOOK.exists():
        if HOOK_MARKER not in HOOK.read_text():
            raise RuntimeError('Unrecognized hook; refusing to remove it: ' + str(HOOK))
        HOOK.unlink()
        print('Removed delayed startup repair. Any waiting worker will skip changes.')


def install_startup(plan):
    if HOOK.exists() and HOOK_MARKER not in HOOK.read_text():
        raise RuntimeError('Unrecognized existing startup hook; refusing to overwrite')
    info = luna('com.webos.service.tv.systemproperty', 'getSystemInfo',
                {'keys': ['modelName', 'firmwareVersion', 'sdkVersion']})
    if any(info.get(key) != plan['tv'].get(key) for key in ['modelName', 'firmwareVersion', 'sdkVersion']):
        raise RuntimeError('TV firmware changed; review cleanup before installing startup repair')
    repair(plan)
    atomic_write(PERSISTENT, Path(__file__).read_text(encoding='utf-8'))
    os.chmod(str(PERSISTENT), 0o700)
    keep_profiles(ROOT)
    HOOK.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(HOOK, hook_text(sys.executable))
    os.chmod(str(HOOK), 0o700)
    print('Installed:', HOOK)
    print('At boot: background worker waits 45 seconds, then repairs the tile list and backed-up promotional settings once and verifies.')
    print('It does not delay other startup hooks, restart Home, or run a continuous watcher.')
    print('Reboot, wait at least 60 seconds after startup, then verify. Startup log:', BOOT_LOG)


def start_boot_worker():
    if not HOOK.is_file():
        return
    mode = 'w' if BOOT_LOG.exists() and BOOT_LOG.stat().st_size > 65536 else 'a'
    with BOOT_LOG.open(mode, encoding='utf-8') as log:
        os.chmod(str(BOOT_LOG), 0o600)
        subprocess.Popen([sys.executable, str(PERSISTENT), 'boot-run'],
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         start_new_session=True, close_fds=True)


@contextmanager
def mutation_lock():
    import fcntl
    with (ROOT / 'operation.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield


def self_test():
    import unittest
    check = unittest.TestCase()
    # Reproduce a list rewritten by LG: missing our entry, retaining another,
    # and adding a new LG regional block and an unrelated metadata field.
    change = {'path': str(BLOCKS), 'original': encode({'blocked_system_applist': ['stock']}),
              'new': encode({'blocked_system_applist': ['stock', 'ours-a', 'ours-b']})}
    current = {'blocked_system_applist': ['stock', 'ours-a', 'new-lg'], 'version': 9}
    merged = merge_blocks(current, ['ours-a', 'ours-b'])
    check.assertEqual(merged['blocked_system_applist'], ['stock', 'ours-a', 'new-lg', 'ours-b'])
    check.assertEqual(current['blocked_system_applist'], ['stock', 'ours-a', 'new-lg'])
    check.assertEqual(merge_blocks(merged, ['ours-a', 'ours-b']), merged)
    with check.assertRaises(RuntimeError):
        merge_blocks(current, ['com.webos.app.hdmi2'])
    check.assertEqual(rollback_document(change, current), {'blocked_system_applist': ['stock', 'new-lg'], 'version': 9})
    pre = {'path': str(PRELOAD), 'original': encode({'allowedApps': {'netflix': True, 'airplay': False, 'home': True}}),
           'new': encode({'allowedApps': {'netflix': False, 'airplay': False, 'home': True, 'voice': False}})}
    check.assertEqual(rollback_document(pre, {'allowedApps': {'netflix': False, 'airplay': False, 'home': True, 'voice': False, 'new-lg': True}}),
                      {'allowedApps': {'netflix': True, 'airplay': False, 'home': True, 'new-lg': True}})
    with check.assertRaises(RuntimeError):
        rollback_document(pre, {'allowedApps': {'netflix': 'unexpected'}})
    check.assertIn(HOOK_MARKER, hook_text('/usr/bin/python3'))
    check.assertEqual(hook_text('/usr/bin/python3').splitlines()[-1],
                      'exec /usr/bin/python3 /var/lib/lg-hdmi-cleanup/hdmi-cleanup.py boot-start')
    check.assertNotIn('sleep', hook_text('/usr/bin/python3'))
    check.assertIn("'/a b/python3'", hook_text('/a b/python3'))
    from unittest.mock import patch
    settings_plan = {'settings': [
        {'category': 'general', 'key': 'sportsAlarm', 'original': 'on'},
        {'category': 'general', 'key': 'homePromotion', 'original': 'on'}]}
    before = encode(settings_plan)
    with patch(__name__ + '.setting', side_effect=['on', 'off']), patch(__name__ + '.set_setting') as setter:
        check.assertEqual(repair_settings(settings_plan), [('general', 'sportsAlarm')])
        setter.assert_called_once_with('general', 'sportsAlarm', 'off')
    check.assertEqual(encode(settings_plan), before)
    with patch(__name__ + '.setting', return_value='off'), patch(__name__ + '.set_setting') as setter:
        check.assertEqual(repair_settings(settings_plan), [])
        setter.assert_not_called()
    with patch(__name__ + '.setting', side_effect=['on', 'unexpected']), patch(__name__ + '.set_setting') as setter:
        check.assertRaises(RuntimeError, repair_settings, settings_plan)
        setter.assert_not_called()
    with patch(__name__ + '.set_setting') as setter:
        check.assertRaises(RuntimeError, repair_settings, {'settings': [
            {'category': 'general', 'key': 'homeAutoLaunch', 'original': 'on'}]})
        setter.assert_not_called()
    print('Regression checks passed: merge/idempotence, HDMI protection, rollback/conflicts, startup hook/quoting, setting drift repair/backup preservation.')


def restore(plan):
    remove_startup()
    # Merge out only our changes; retain later unrelated LG entries and fields.
    restored_files = []
    for change in plan['files']:
        current = Path(change['path']).read_text(encoding='utf-8')
        restored = rollback_document(change, json.loads(current))
        restored_files.append((change, current, restored))
    for item in plan['settings']:
        if setting(item['category'], item['key']) not in ('off', item['original']):
            raise RuntimeError('Later setting change detected: ' + item['key'])
    for change, before, restored in restored_files:
        if Path(change['path']).read_text(encoding='utf-8') != before:
            raise RuntimeError('Configuration changed during restore; stop and inspect backup')
        atomic_write(change['path'], encode(restored))
    for appid, enabled in plan['preloads'].items():
        set_preload(appid, enabled)
    for item in plan['settings']:
        set_setting(item['category'], item['key'], item['original'])
    print('Cleanup changes reversed, preserving unrelated LG changes; original-state.json retained.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'apply', 'verify', 'restore', 'diagnose', 'repair', 'self-test',
                                         'install-startup', 'uninstall-startup', 'boot-start', 'boot-run'])
    args = parser.parse_args()
    if args.action == 'self-test':
        self_test()
        return
    if os.geteuid() != 0:
        raise RuntimeError('Run on the TV as root')
    if args.action == 'boot-start':
        start_boot_worker()
        return
    if args.action == 'boot-run':
        time.sleep(45)
        with mutation_lock():
            if not HOOK.is_file():
                print('Startup repair removed; skipping.')
                return
            print('Startup repair:', time.strftime('%Y-%m-%d %H:%M:%S'), flush=True)
            plan = json.loads(STATE.read_text())
            info = luna('com.webos.service.tv.systemproperty', 'getSystemInfo',
                        {'keys': ['modelName', 'firmwareVersion', 'sdkVersion']})
            if any(info.get(key) != plan['tv'].get(key) for key in ['modelName', 'firmwareVersion', 'sdkVersion']):
                raise RuntimeError('TV firmware changed; startup repair skipped pending review')
            repair(plan)
        return
    if args.action == 'plan':
        show(make_plan())
        print('Preview only; no changes made.')
        return
    if args.action == 'apply':
        if STATE.exists():
            raise RuntimeError('Existing backup found; use verify or restore. Backup will not be overwritten.')
        plan = make_plan()
        show(plan)
        ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
        atomic_write(STATE, encode(plan))  # Save all originals before any TV changes.
        print('Original values backed up to', STATE, flush=True)
        for change in plan['files']:
            if Path(change['path']).read_text(encoding='utf-8') != change['original']:
                raise RuntimeError('Configuration changed during planning; stop and inspect backup')
            atomic_write(change['path'], change['new'])
        for appid in plan['preloads']:
            set_preload(appid, False)
        for item in plan['settings']:
            set_setting(item['category'], item['key'], 'off')
        verify(plan)
        print('Cleanup applied. Reboot normally, then run verify again.')
    else:
        with mutation_lock():
            plan = json.loads(STATE.read_text())
            if args.action == 'verify':
                verify(plan)
            elif args.action == 'diagnose':
                diagnose(plan)
            elif args.action == 'repair':
                repair(plan)
            elif args.action == 'install-startup':
                install_startup(plan)
            elif args.action == 'uninstall-startup':
                remove_startup()
            else:
                restore(plan)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('STOP:', error, file=sys.stderr)
        print('If apply started, retain /var/lib/lg-hdmi-cleanup/original-state.json for rollback.', file=sys.stderr)
        sys.exit(1)
