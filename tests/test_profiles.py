"""Checks for the device-profile guard and the onboarding check. Run: python -m unittest discover tests"""
import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
GUARDED = {
    'debloat-tv.py': 'debloat',
    'hdmi-cleanup.py': 'hdmi-cleanup',
    'lg-home-layout.py': 'home-layout',
    'alexa-tiles.py': 'alexa-tiles',
    'no-signal-background.py': 'no-signal-background',
    'dashboard/home-router.py': 'home-router',
}
REFERENCE = {'modelName': 'OLED48C24LA', 'firmwareVersion': '33.31.68', 'sdkVersion': '10.3.1'}
OTHER = {'modelName': 'OLED55C34LA', 'firmwareVersion': '03.10.20', 'sdkVersion': '8.1.0'}
REGISTRY = json.loads((ROOT / 'profiles' / 'lg-reviewed-profiles.json').read_text(encoding='utf-8'))


def tree(path):
    return ast.parse((ROOT / path).read_text(encoding='utf-8'))


def function_source(path, name):
    text = (ROOT / path).read_text(encoding='utf-8')
    for node in tree(path).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(text, node)
    raise AssertionError(name + ' not found in ' + path)


def load_function(path, name, directory):
    namespace = {'json': json, 'Path': Path, 'os': os, '__file__': str(Path(directory) / 'script.py'),
                 'REFERENCE_TV': ('OLED48C24LA', '33.31.68', '10.3.1'), 'REFERENCE_MODEL': 'OLED48C24LA',
                 'PROFILES_FILE': 'lg-reviewed-profiles.json'}
    exec(function_source(path, name), namespace)
    return namespace[name]


def write_registry(directory, profiles):
    Path(directory, 'lg-reviewed-profiles.json').write_text(json.dumps({'schema': 1, 'profiles': profiles}))


class GuardTests(unittest.TestCase):
    def test_guard_copies_are_identical(self):
        for name in ('reviewed_tv', 'keep_profiles'):
            sources = {path: function_source(path, name) for path in GUARDED}
            self.assertEqual(len(set(sources.values())), 1, name + ' differs between scripts')

    def test_reference_constant_unchanged_everywhere(self):
        for path in GUARDED:
            text = (ROOT / path).read_text(encoding='utf-8')
            self.assertIn("REFERENCE_TV = ('OLED48C24LA', '33.31.68', '10.3.1')", text)

    def test_each_script_checks_its_own_component(self):
        for path, component in GUARDED.items():
            calls = re.findall(r"reviewed_tv\(\w+, '([a-z-]+)'\)", (ROOT / path).read_text(encoding='utf-8'))
            self.assertEqual(calls, [component], path)

    def test_no_hardcoded_identity_comparisons_left(self):
        for path in list(GUARDED) + ['dashboard/dashboard-tv.py']:
            text = (ROOT / path).read_text(encoding='utf-8')
            self.assertNotRegex(text, r"[!=]= \[?\(?\s*'OLED48C24LA'", path)
            self.assertNotIn("!= 'OLED48C24LA'", text, path)

    def test_persistent_installs_copy_the_registry(self):
        for path in GUARDED:
            if path == 'no-signal-background.py':
                continue  # no startup copy
            self.assertIn('keep_profiles(ROOT)', (ROOT / path).read_text(encoding='utf-8'), path)

    def test_reference_runs_without_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            reviewed = load_function('debloat-tv.py', 'reviewed_tv', directory)
            for component in REGISTRY['components']:
                self.assertTrue(reviewed(dict(REFERENCE), component))
            self.assertFalse(reviewed(dict(OTHER), 'dashboard'))

    def test_registry_unlocks_only_listed_components_on_exact_match(self):
        with tempfile.TemporaryDirectory() as directory:
            reviewed = load_function('debloat-tv.py', 'reviewed_tv', directory)
            write_registry(directory, [dict(OTHER, components=['dashboard', 'home-router'])])
            self.assertTrue(reviewed(dict(OTHER), 'home-router'))
            self.assertFalse(reviewed(dict(OTHER), 'debloat'))
            self.assertFalse(reviewed(dict(OTHER, firmwareVersion='03.10.21'), 'home-router'))
            self.assertFalse(reviewed(dict(OTHER, sdkVersion=None), 'home-router'))

    def test_malformed_registries_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            reviewed = load_function('debloat-tv.py', 'reviewed_tv', directory)
            registry = Path(directory, 'lg-reviewed-profiles.json')
            for content in ['not json', '[]', '{"profiles": {}}', '{"profiles": ["x"]}',
                            json.dumps({'profiles': [dict(OTHER, components='home-router-and-more')]}),
                            json.dumps({'profiles': [dict(modelName=None, firmwareVersion=None, sdkVersion=None,
                                                          components=['dashboard'])]})]:
                registry.write_text(content)
                self.assertFalse(reviewed(dict(OTHER), 'home-router'), content)
                self.assertFalse(reviewed({}, 'dashboard'), content)

    def test_keep_profiles_copies_next_to_target(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            write_registry(source, [])
            keep = load_function('debloat-tv.py', 'keep_profiles', source)
            keep(target)
            self.assertEqual(Path(target, 'lg-reviewed-profiles.json').read_text(),
                             Path(source, 'lg-reviewed-profiles.json').read_text())
            keep(source)  # same directory: no-op
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            load_function('debloat-tv.py', 'keep_profiles', source)(target)  # nothing uploaded
            self.assertFalse(Path(target, 'lg-reviewed-profiles.json').exists())

    def test_dashboard_checks_model_only(self):
        with tempfile.TemporaryDirectory() as directory:
            reviewed = load_function('dashboard/dashboard-tv.py', 'reviewed_model', directory)
            self.assertTrue(reviewed(dict(REFERENCE, firmwareVersion='99.0.0')))
            self.assertFalse(reviewed(dict(OTHER)))
            write_registry(directory, [dict(OTHER, components=['home-router'])])
            self.assertFalse(reviewed(dict(OTHER)))
            write_registry(directory, [dict(OTHER, components=['dashboard'])])
            self.assertTrue(reviewed(dict(OTHER, firmwareVersion='anything')))


class RegistryTests(unittest.TestCase):
    def test_registry_shape(self):
        known = set(REGISTRY['components'])
        self.assertEqual(known, set(GUARDED.values()) | {'dashboard'})
        ids = set()
        for profile in REGISTRY['profiles']:
            for key in ('id', 'modelName', 'firmwareVersion', 'sdkVersion', 'reviewedBy', 'reviewedOn'):
                self.assertIsInstance(profile.get(key), str, key)
            self.assertEqual(profile['id'], profile['modelName'] + '_' + profile['firmwareVersion'])
            self.assertNotIn(profile['id'], ids)
            ids.add(profile['id'])
            self.assertTrue(set(profile['components']) <= known, profile['id'])

    def test_reference_profile_lists_everything(self):
        reference = [p for p in REGISTRY['profiles'] if p['id'] == 'OLED48C24LA_33.31.68']
        self.assertEqual(len(reference), 1)
        self.assertEqual(set(reference[0]['components']), set(REGISTRY['components']))


class InitCheckTests(unittest.TestCase):
    SAFE_TOP_LEVEL = (ast.Import, ast.ImportFrom, ast.Assign, ast.FunctionDef, ast.ClassDef, ast.If, ast.Expr)

    def test_component_scripts_are_safe_to_import(self):
        # init-tv.py imports these for their constants; nothing may run at import time.
        for path in GUARDED:
            for node in tree(path).body:
                self.assertIsInstance(node, self.SAFE_TOP_LEVEL, path + ':' + str(node.lineno))
                if isinstance(node, ast.Expr):
                    self.assertIsInstance(node.value, ast.Constant, path + ':' + str(node.lineno))
                if isinstance(node, ast.If):
                    self.assertIn('__main__', ast.unparse(node.test), path + ':' + str(node.lineno))
                if isinstance(node, ast.Assign):
                    calls = [n for n in ast.walk(node.value) if isinstance(n, ast.Call)]
                    allowed = {'Path', 'set', 'split', 'join'}
                    for call in calls:
                        name = call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, 'id', '')
                        self.assertIn(name, allowed, path + ':' + str(node.lineno))

    def test_init_only_calls_read_methods(self):
        init = tree('init-tv.py')
        for node in ast.walk(init):
            if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'luna':
                method = node.args[1]
                self.assertIsInstance(method, ast.Constant)
                self.assertTrue(method.value.split('/')[-1].startswith('get'), method.value)
            if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'systemctl':
                self.assertIn(node.args[0].value, ('cat', 'show'))
        text = (ROOT / 'init-tv.py').read_text(encoding='utf-8')
        for word in ('setSystemSettings', 'setPreloadPolicy', "'launch'", 'umount', 'write_text', 'write_bytes',
                     'unlink', '.main(', 'mkdir'):
            self.assertNotIn(word, text, word)

    def load_init(self):
        spec = importlib.util.spec_from_file_location('init_tv', str(ROOT / 'init-tv.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_luna_refuses_write_methods(self):
        init = self.load_init()
        with self.assertRaises(RuntimeError):
            init.luna('com.webos.settingsservice', 'setSystemSettings', {})
        with self.assertRaises(RuntimeError):
            init.luna('com.webos.service.tvpower', 'power/turnOffScreen', {})
        with self.assertRaises(RuntimeError):
            init.systemctl('stop', 'x.service')
        calls = []
        init.run = lambda args: (calls.append(args), (0, '{"returnValue": true, "state": "Active"}'))[1]
        self.assertEqual(init.luna('com.webos.service.tvpower', 'power/getPowerState', {})['state'], 'Active')
        self.assertTrue(calls[0][-2].endswith('/power/getPowerState'))

    def test_status_aggregation_and_profile_id(self):
        init = self.load_init()
        component = init.Component()
        component.add('a', 'matches')
        self.assertEqual(component.result()['status'], 'matches')
        component.add('b', 'differs')
        self.assertEqual(component.result()['status'], 'differs')
        component.add('c', 'missing')
        self.assertEqual(component.result()['status'], 'missing')
        self.assertEqual(init.profile_id(REFERENCE), 'OLED48C24LA_33.31.68')
        self.assertEqual(init.profile_id({'modelName': '../x y', 'firmwareVersion': None}), '..-x-y_unknown')

    def test_layout_check_compares_reviewed_hash(self):
        init = self.load_init()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory, 'home.xml')
            target.write_bytes(b'layout')
            fake = type('Module', (), {'TARGET': target,
                                       'EXPECTED': __import__('hashlib').sha256(b'layout').hexdigest()})
            component = init.Component()
            init.check_layout(component, fake)
            self.assertEqual(component.result()['status'], 'matches')
            target.write_bytes(b'changed')
            component = init.Component()
            init.check_layout(component, fake)
            self.assertEqual(component.result()['status'], 'differs')
            target.unlink()
            component = init.Component()
            init.check_layout(component, fake)
            self.assertEqual(component.result()['status'], 'missing')

    def test_debloat_check_uses_reviewed_definitions_without_copying_them(self):
        init = self.load_init()
        review = json.loads((ROOT / 'debloat-reviewed-units.json').read_text(encoding='utf-8-sig'))
        unit = next(iter(review))
        fake = type('Module', (), {'UNITS': [unit], 'BINARIES': [], 'CORE': []})

        def systemctl(verb, *args):
            if verb == 'cat':
                return 0, review[unit]
            return 0, 'LoadState=loaded\nRequiredBy=\nBoundBy=\nConsistsOf=\n'
        init.systemctl = systemctl
        component = init.Component()
        init.check_debloat(component, fake)
        statuses = {c['check']: c['status'] for c in component.checks}
        self.assertEqual(statuses['Unit ' + unit], 'matches')
        self.assertEqual(statuses['Unit ' + unit + ' dependencies'], 'matches')
        report = json.dumps(component.checks)
        self.assertNotIn('ExecStart', report)  # hashes only, never unit text
        init.systemctl = lambda verb, *args: (0, review[unit] + '# edited\n') if verb == 'cat' else (0, 'LoadState=loaded')
        component = init.Component()
        init.check_debloat(component, fake)
        self.assertEqual(component.checks[0]['status'], 'differs')


class LauncherTests(unittest.TestCase):
    UPLOADS = ['alexa-tiles.ps1', 'dashboard.ps1', 'dashboard-home.ps1', 'debloat-tv.ps1', 'hdmi-cleanup.ps1',
               'lg-home-layout.ps1', 'no-signal-background.ps1']

    def test_launchers_use_shared_address(self):
        for path in ROOT.glob('*.ps1'):
            if path.name in ('tv-address.ps1', 'init.ps1'):
                continue
            text = path.read_text(encoding='utf-8')
            if 'ssh' in text:
                self.assertIn("tv-address.ps1", text, path.name)
                self.assertNotIn('192.168.', text, path.name)

    def test_guarded_launchers_upload_registry_with_matching_script_names(self):
        for name in self.UPLOADS:
            text = (ROOT / name).read_text(encoding='utf-8')
            self.assertIn("profiles\\lg-reviewed-profiles.json", text, name)
            uploads = re.findall(r"Join-Path \$\w+ '(?:dashboard\\)?([\w-]+\.py)'", text)
            uploaded = {Path(u).name for u in uploads} | {
                Path(m).name for m in re.findall(r"\\([\w-]+\.py)'", text)}
            for remote in re.findall(r'/tmp/([\w-]+\.py)', text):
                self.assertIn(remote, uploaded, name + ' runs /tmp/' + remote)


if __name__ == '__main__':
    unittest.main()
