"""Size ratchet for the Python scripts (D-006). Run: python -m unittest discover tests

Functions should stay at or under 80 code lines and cyclomatic complexity 10. Older functions may
break that, so each file may not gain violations over scripts/code-size-baseline.json, and a file
not in it may have none. The JavaScript files share the baseline and are held by
scripts/check-code-size.mjs. Lines and complexity are counted the way CommonShared's audit counts
them: non-blank, non-comment lines; 1 + each if / for / while / except / with, conditional
expression, comprehension `if`, and each extra operand of `and` / `or`; a nested function on its own.

To lower the baseline after a split, `python -I tests/test_code_size.py` prints the current counts.
Raising a number is the operator's decision.
"""
import ast
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / 'scripts' / 'code-size-baseline.json'
MAX_LINES = 80
MAX_COMPLEXITY = 10
BRANCHES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.With, ast.AsyncWith, ast.IfExp)
FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def own_nodes(fn):
    stack = list(ast.iter_child_nodes(fn))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, FUNCS):
            stack.extend(ast.iter_child_nodes(node))


def complexity(fn):
    n = 1
    for node in own_nodes(fn):
        if isinstance(node, BRANCHES):
            n += 1
        elif isinstance(node, ast.BoolOp):
            n += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            n += len(node.ifs)
    return n


def code_lines(lines, start, end):
    return sum(1 for line in lines[start - 1:end] if line.strip() and not line.strip().startswith('#'))


def counts_for(source):
    """{rule: count} of the functions in one file's source over the limits."""
    lines = source.splitlines()
    counts = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if code_lines(lines, node.lineno, node.end_lineno or node.lineno) > MAX_LINES:
            counts['max-lines-per-function'] = counts.get('max-lines-per-function', 0) + 1
        if complexity(node) > MAX_COMPLEXITY:
            counts['complexity'] = counts.get('complexity', 0) + 1
    return counts


def python_files():
    out = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-co', '--exclude-standard', '*.py'],
                         capture_output=True, text=True, check=True).stdout
    return sorted(f for f in out.splitlines()
                  if not f.startswith('tests/') and not Path(f).name.startswith('test_') and (ROOT / f).is_file())


def current_counts():
    found = {}
    for rel in python_files():
        counts = counts_for((ROOT / rel).read_text(encoding='utf-8'))
        if counts:
            found[rel] = counts
    return found


def ratchet_failures(found, baseline):
    """Each file and rule over its baseline count, as "file: rule count (allowed n)"."""
    return [f'{rel}: {rule} {count} (allowed {baseline.get(rel, {}).get(rule, 0)})'
            for rel, rules in sorted(found.items()) for rule, count in sorted(rules.items())
            if count > baseline.get(rel, {}).get(rule, 0)]


class CodeSizeRatchet(unittest.TestCase):
    def test_no_python_file_gains_a_violation(self):
        baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
        self.assertEqual(ratchet_failures(current_counts(), baseline), [],
                         'a function grew past 80 lines or complexity 10; split it')

    def test_the_counter_sees_a_long_and_a_complex_function(self):
        long_fn = 'def f():\n' + ''.join(f'    v{i} = {i}\n' for i in range(81))
        branchy = 'def g(a):\n' + ''.join(f'    if a == {i}:\n        return {i}\n' for i in range(10))
        self.assertEqual(counts_for(long_fn), {'max-lines-per-function': 1})
        self.assertEqual(counts_for(branchy), {'complexity': 1})
        self.assertEqual(counts_for('def h():\n    # note\n\n    return 1\n'), {})

    def test_a_new_violation_fails_the_ratchet(self):
        self.assertEqual(ratchet_failures({'a.py': {'complexity': 2}}, {'a.py': {'complexity': 1}}),
                         ['a.py: complexity 2 (allowed 1)'])
        self.assertEqual(ratchet_failures({'b.py': {'complexity': 1}}, {}), ['b.py: complexity 1 (allowed 0)'])
        self.assertEqual(ratchet_failures({'a.py': {'complexity': 1}}, {'a.py': {'complexity': 2}}), [])


if __name__ == '__main__':
    print(json.dumps(current_counts(), indent=2, sort_keys=True))
