"""Template: injection sinks as a pytest check (docs/24, rules/security.md "Injection").

Copy into tests/, set SRC, run with `python -m pytest tests/test_injection.py`. The same rules as
templates/tests/injection.test.mjs, for projects without Node: it reads Python, PowerShell, C#
and the web files a Python app serves, and flags sinks built from strings (queries, commands,
raw HTML, evaluated strings, unsafe loaders). It cannot prove a sink safe; each sink still needs
its hostile-value test (docs/24 §5). A line that is safe as written carries `injection: <why>`.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The project's source: the first of src/, app/, lib/, else the project root (adjust if needed).
SRC = next((ROOT / d for d in ("src", "app", "lib") if (ROOT / d).is_dir()), ROOT)
# AUDIT_FILES (set by an audit): a text file with one project-relative path a line, the tracked
# files minus vendored folders and minified files, under AUDIT_ROOT (default: the working folder).
# When set, only those files are read.


def _audit_files() -> set[str] | None:
    listed = os.environ.get("AUDIT_FILES")
    if not listed:
        return None
    root = Path(os.environ.get("AUDIT_ROOT") or os.getcwd())
    lines = Path(listed).read_text(encoding="utf-8-sig").splitlines()
    return {os.path.normcase(str((root / line.strip()).resolve())) for line in lines if line.strip()}


AUDIT = _audit_files()


def audited(path: Path) -> bool:
    return AUDIT is None or os.path.normcase(str(path.resolve())) in AUDIT


SKIP = re.compile(r"(^|[\\/])(node_modules|dist|build|vendor|\.venv|venv|__pycache__|coverage|tests?)([\\/]|$)")

JS = re.compile(r"\.(m?[jt]sx?|cjs|vue|svelte|html)$")
PY = re.compile(r"\.py$")
PS = re.compile(r"\.psm?1$")
CS = re.compile(r"\.cs$")
SQL = r"\b(?:SELECT\s[^;]*?\bFROM\b|INSERT\s+INTO\b|UPDATE\s+[\w.\"]+\s+SET\b|DELETE\s+FROM\b)"

# (id, which files, pattern, what to do instead) — docs/24 §2
RULES = [
    ("sql-join", JS, re.compile(r"(?<![\w.$])`[^`]*" + SQL + r"[^`]*\$\{", re.I), "bind parameters"),
    ("sql-join", JS, re.compile(r"(?:\"[^\"\n]*" + SQL + r"[^\"\n]*\"|'[^'\n]*" + SQL + r"[^'\n]*')\s*\+\s*[\w$(]", re.I), "bind parameters"),
    ("sql-join", PY, re.compile(r"\.execute(?:many)?\s*\(\s*(?:f[\"']|[\"'][^\"'\n]*[\"']\s*(?:%|\.format\b|\+))"), "pass parameters as the second argument"),
    ("sql-join", CS, re.compile(r"new\s+(?:Sql|Npgsql|Sqlite|MySql)Command\s*\(\s*(?:\$\"|\"[^\"\n]*\"\s*\+)"), "use command.Parameters"),
    ("raw-html", JS, re.compile(r"\.(?:innerHTML|outerHTML)\s*\+?=\s*(?!\s*(?:'[^'$]*'|\"[^\"$]*\"|`[^`$]*`)\s*[;\n])"), "textContent, or an allow-list sanitiser"),
    ("raw-html", JS, re.compile(r"\b(?:insertAdjacentHTML|document\.write(?:ln)?)\s*\("), "insertAdjacentText / DOM nodes"),
    ("raw-html", PY, re.compile(r"\bMarkup\s*\(\s*f[\"']|\|\s*safe\b|\bmark_safe\s*\("), "let the template engine escape"),
    ("eval", JS, re.compile(r"(?<![\w.$])eval\s*\(|\bnew\s+Function\s*\("), "data is data: parse it, never run it"),
    ("eval", PY, re.compile(r"(?<![\w.])(?:eval|exec)\s*\("), "ast.literal_eval for literals; never run input"),
    # A bare exec() or one on child_process; `.exec(` on anything else is RegExp's (a test audit, 26 Nov 2026).
    ("shell", JS, re.compile(r"(?:(?<![\w$.])|(?<=child_process\.)|(?<=childProcess\.)|(?<=\bcp\.))exec(?:Sync)?\s*\(\s*(?:`[^`]*\$\{|[^)\n]*\+)|\bshell\s*:\s*true\b"), "execFile / spawn with an argument array"),
    ("shell", PY, re.compile(r"\bshell\s*=\s*True\b|\bos\.(?:system|popen)\s*\("), "subprocess.run([...]) without a shell"),
    ("shell", PS, re.compile(r"(?<![\w-])(?:Invoke-Expression|iex)(?![\w-])", re.I), "parameters or splatting"),
    ("path", PY, re.compile(r"\bopen\s*\([^)\n]*\brequest\.(?:args|form|query_params|path_params|json)"), "resolve, then require it inside the base"),
    ("redirect", PY, re.compile(r"\bredirect\s*\(\s*request\.(?:args|query_params)"), "a relative path or an allow-listed host"),
    ("deserialise", PY, re.compile(r"\bpickle\.loads?\s*\(|\byaml\.(?:unsafe_load|load)\s*\((?![^)]*SafeLoader)"), "JSON with a schema; yaml.safe_load"),
    ("deserialise", CS, re.compile(r"\bnew\s+BinaryFormatter\s*\(|\bTypeNameHandling\.(?:All|Auto|Objects)\b"), "System.Text.Json with known types"),
]


# A detector spells what it detects: in a guard, lint or check file (by its name), a line that holds
# a regex literal or a pattern string (re.compile, new RegExp, -match '...', [regex]) is the guard,
# not a use (a test audit, 24 Nov 2026).
GUARD_FILE = re.compile(r"(guard|lint|detect|scan|saniti[sz]|validat|policy|audit|hooks?|checks?|rules?)[^/\\]*$", re.I)
PATTERN_LINE = re.compile(
    r"(^|[=(,:!&|?\[\s])/(?![/*\s])(?:\\.|\[(?:\\.|[^\]\\\n])*\]|[^/\\\n\[])+/[dgimsuyv]*(?=\s*[.,;)\]}:]|\s*$)"
    r"|\bnew\s+RegExp\s*\(|\bre\.(?:compile|search|match|fullmatch|sub|findall)\s*\(|\[regex\]|\s-[ic]?(?:match|replace|split)\s+['\"]",
    re.I)


def detector_line(name: str, line: str) -> bool:
    return bool(GUARD_FILE.search(name) and PATTERN_LINE.search(line))


def injection_findings(name: str, text: str) -> list[str]:
    """Findings for one file as "line [id] what to do"; a line marked `injection:` is skipped."""
    lines = text.split("\n")
    out = []
    for rule_id, files, pattern, fix in RULES:
        if not files.search(name):
            continue
        for m in pattern.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            if "injection:" not in lines[line - 1] and not detector_line(name, lines[line - 1]):
                out.append(f"{line} [{rule_id}] {fix}")
    return out


def test_no_injection_sink_built_from_strings():
    bad = []
    for path in sorted(SRC.rglob("*")) if SRC.exists() else []:
        rel = path.relative_to(SRC).as_posix()
        if path.is_file() and audited(path) and not SKIP.search(rel) and any(r.search(rel) for r in (JS, PY, PS, CS)):
            bad += [f"{rel}:{x}" for x in injection_findings(rel, path.read_text(encoding="utf-8", errors="replace"))]
    assert bad == []


def test_each_rule_catches_its_case_and_leaves_the_safe_form_alone():
    def ids(name, text):
        return [re.search(r"\[([\w-]+)\]", x).group(1) for x in injection_findings(name, text)]
    cases = [
        ("db.py", 'cur.execute(f"SELECT * FROM t WHERE id = {x}")', ["sql-join"]),
        ("db.py", 'cur.execute("SELECT * FROM t WHERE id = %s", (x,))', []),
        ("db.py", 'cur.execute("SELECT * FROM t WHERE id = " + x)', ["sql-join"]),
        ("run.py", "subprocess.run(cmd, shell=True)", ["shell"]),
        ("run.py", "subprocess.run(['git', 'log', '--', branch])", []),
        ("run.py", "os.system('rm ' + name)", ["shell"]),
        ("calc.py", "value = eval(text)", ["eval"]),
        ("calc.py", "value = ast.literal_eval(text)", []),
        ("load.py", "data = yaml.load(f)", ["deserialise"]),
        ("load.py", "data = yaml.load(f, Loader=yaml.SafeLoader)", []),
        ("load.py", "obj = pickle.loads(blob)", ["deserialise"]),
        ("view.py", 'return Markup(f"<b>{name}</b>")', ["raw-html"]),
        ("app.js", "el.innerHTML = note.text;", ["raw-html"]),
        ("app.js", "el.textContent = note.text;", []),
        ("match.ts", "const m = SITE_URL.exec(`https://${value}`)", []),
        ("git.js", "cp.exec(`git log ${branch}`)", ["shell"]),
        ("git.js", "child_process.execSync('git log ' + branch)", ["shell"]),
        ("run.ps1", 'Invoke-Expression "git log $branch"', ["shell"]),
        ("files.py", "open(os.path.join(root, request.args['f']))", ["path"]),
        ("app.js", "el.innerHTML = TEMPLATE; // injection: a constant built above", []),
        ("tools/lint_sinks.py", 'SINK = re.compile(r"value = eval(text)")', []),
        ("tools/lint_sinks.py", "value = eval(text)", ["eval"]),
        ("tools/build.py", 'SINK = re.compile(r"value = eval(text)")', ["eval"]),
    ]
    for name, text, want in cases:
        assert ids(name, text) == want, f"{name}: {text}"
