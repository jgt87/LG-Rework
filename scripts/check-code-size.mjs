// Code-size ratchet: functions under 80 lines and cyclomatic complexity 10 or
// less. Older code may break the rule, so a source file may not gain
// violations over the committed baseline, and a file not in the baseline may
// have none. Tests are exempt (a describe block is long by nature).
// Origin: a canvas app's scripts/check-code-size.mjs (Sept 2026 health batches).
//
//   node scripts/check-code-size.mjs            check (chain it into `npm run lint`)
//   node scripts/check-code-size.mjs --update   write or lower the baseline after
//                                               a split; it never rises by hand
//
//   node scripts/check-code-size.mjs --reader   measure with the reader, not ESLint
//
// First run in a project: `--update` writes the baseline from the current tree.
// A file that must grow past the limit is split instead; raising its number in
// the baseline is the operator's decision. Measures with `eslint` (flat config)
// when it and its parser load; else, or with --reader, with the dependency-free
// reader copied beside this script (scripts/code-size-reader.mjs, from
// templates/scripts/). ESLint's TypeScript parser cannot run with TypeScript 7,
// which has no JS API (a test audit, 24 Nov 2026). The readers count slightly
// differently: write the baseline with the reader the check runs with.
// Baseline keys are paths relative to the project root (this script's folder's
// parent), with forward slashes, whichever reader measured them.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Adjust per project, here only: a copy that differs from this template outside the CONFIG block
// is reported as stale by the audit, so a refresh stays a plain copy plus this block (a project
// had to edit three more lines to leave out its copied-in checkers, 26 Nov 2026).
//   globs    what to measure, from the project root
//   exclude  files left out, project-relative with forward slashes: copies of another repo's
//            scripts, held by that repo's own ratchet (CommonShared's rendered checkers)
const CONFIG = {
  globs: ['dashboard/*.{js,mjs}', 'scripts/**/*.mjs'],
  // Python files share scripts/code-size-baseline.json and are held by tests/test_code_size.py.
  exclude: ['scripts/check-code-size.mjs', 'scripts/code-size-reader.mjs'],
};
const GLOBS = CONFIG.globs;
const IS_TEST = /\.(test|spec)\.[cm]?[jt]sx?$/;
const MAX_LINES = 80;
const MAX_COMPLEXITY = 10;

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const baselinePath = path.join(root, 'scripts', 'code-size-baseline.json');
const RULES = {
  'max-lines-per-function': ['warn', { max: MAX_LINES, skipBlankLines: true, skipComments: true }],
  complexity: ['warn', MAX_COMPLEXITY],
};

/** Violations per file and rule, source files only, files sorted. `results` are ESLint's. */
export function violationCounts(results, base) {
  const counts = {};
  for (const result of results) {
    const file = path.relative(base, result.filePath).split(path.sep).join('/');
    if (IS_TEST.test(file)) continue;
    for (const message of result.messages) {
      if (!(message.ruleId in RULES)) continue;
      counts[file] ??= {};
      counts[file][message.ruleId] = (counts[file][message.ruleId] ?? 0) + 1;
    }
  }
  return Object.fromEntries(Object.keys(counts).sort().map((file) => [file, counts[file]]));
}

/** The baseline --update writes: it only ever lowers; a count above the old baseline keeps the old number. */
export function lowerBaseline(counts, baseline) {
  const next = {};
  for (const [file, rules] of Object.entries(counts)) {
    for (const [rule, count] of Object.entries(rules)) {
      const old = baseline ? baseline[file]?.[rule] ?? 0 : count;
      if (count <= old) (next[file] ??= {})[rule] = count;
      else if (old > 0) (next[file] ??= {})[rule] = old;
    }
  }
  return next;
}

/** Each file and rule over its baseline count, as "file: rule count (allowed n)". */
export function ratchetFailures(counts, baseline) {
  const failures = [];
  for (const [file, rules] of Object.entries(counts)) {
    for (const [rule, count] of Object.entries(rules)) {
      const allowed = baseline[file]?.[rule] ?? 0;
      if (count > allowed) failures.push(`${file}: ${rule} ${count} (allowed ${allowed})`);
    }
  }
  return failures;
}

/** The files the globs find, project-relative with forward slashes, without node_modules and CONFIG.exclude. */
export function sourceFiles(base = root, { globs = GLOBS, exclude = CONFIG.exclude } = {}) {
  return fs.globSync(globs, { cwd: base, exclude: (f) => /node_modules/.test(f) })
    .map((f) => f.split(path.sep).join('/'))
    .filter((f) => !exclude.includes(f));
}

// A silent skip would report zero violations: a config that does not cover .ts/.tsx drops
// those files from the results without a message, and a file that fails to parse yields no
// rule results. So every extension the globs find must be linted, and every file must parse.
function requireFullCoverage(results) {
  const extensionsOf = (files) => new Set(files.map((f) => path.extname(f).toLowerCase()));
  const found = extensionsOf(sourceFiles());
  const linted = extensionsOf(results.map((r) => r.filePath));
  const uncovered = [...found].filter((ext) => !linted.has(ext));
  const unparsed = results.filter((r) => r.messages.some((m) => m.fatal));
  if (results.length && !uncovered.length && !unparsed.length) return;
  console.error(`code size: ${results.length} files linted; no file linted for ${uncovered.join(', ') || '-'}; ${unparsed.length} failed to parse. Fix the globs or the ESLint config.`);
  unparsed.forEach((r) => console.error(`  ${path.relative(root, r.filePath)}: ${r.messages.find((m) => m.fatal).message}`));
  process.exit(1);
}

/** The reader's results in ESLint's shape ({ filePath, messages: [{ ruleId }] }), one message per
 *  function over a limit. `measure(src)` gives [{ lines, complexity }] per function. */
export function readerResults(files, base, measure, readFile = (f) => fs.readFileSync(f, 'utf8')) {
  return files.map((rel) => {
    const filePath = path.join(base, rel);
    let fns;
    try { fns = measure(readFile(filePath)); } catch (e) { return { filePath, messages: [{ fatal: true, message: e.message }] }; }
    const messages = fns.flatMap((f) => [
      ...(f.lines > MAX_LINES ? [{ ruleId: 'max-lines-per-function' }] : []),
      ...(f.complexity > MAX_COMPLEXITY ? [{ ruleId: 'complexity' }] : []),
    ]);
    return { filePath, messages };
  });
}

/** ESLint's results, or null when ESLint or its parser cannot load (then the reader measures). */
async function eslintResults() {
  // Loaded here, not at the top: the tests import the pure parts above without ESLint installed.
  let ESLint;
  try { ({ ESLint } = await import('eslint')); } catch { return null; }
  // A project without an ESLint config of its own runs only the two rules: without this, ESLint
  // refuses to start ("Could not find config file"). The coverage guard then still fails a run
  // that skipped an extension (the defaults lint JS only).
  const ownConfig = fs.readdirSync(root).some((f) => /^eslint\.config\.[cm]?[jt]s$/.test(f));
  const eslint = new ESLint({
    cwd: root,
    overrideConfigFile: !ownConfig,
    overrideConfig: { rules: RULES },
    ignorePatterns: CONFIG.exclude,
    ruleFilter: ({ ruleId }) => ruleId in RULES,
    errorOnUnmatchedPattern: false,
  });
  try { return await eslint.lintFiles(GLOBS); } catch (e) {
    if (/parser|typescript|Cannot find (module|package)/i.test(e.message)) return null;
    throw e;
  }
}

async function readerRun() {
  const reader = path.join(path.dirname(fileURLToPath(import.meta.url)), 'code-size-reader.mjs');
  if (!fs.existsSync(reader)) {
    console.error('code size: ESLint or its parser cannot run here; copy templates/scripts/code-size-reader.mjs beside this script to measure without it.');
    process.exit(1);
  }
  const { measureJs } = await import(pathToFileURL(reader).href);
  return readerResults(sourceFiles(), root, measureJs);
}

async function main() {
  const forced = process.argv.includes('--reader');
  let results = forced ? null : await eslintResults();
  if (results) requireFullCoverage(results);
  else {
    results = await readerRun();
    console.log(`code size: measured by code-size-reader.mjs (${forced ? '--reader' : 'ESLint or its parser cannot run'})`);
  }
  const sorted = violationCounts(results, root);
  const baseline = fs.existsSync(baselinePath) ? JSON.parse(fs.readFileSync(baselinePath, 'utf8')) : null;

  if (process.argv.includes('--update')) {
    const next = lowerBaseline(sorted, baseline);
    fs.writeFileSync(baselinePath, `${JSON.stringify(next, null, 2)}\n`);
    console.log(`code size baseline written: ${Object.keys(next).length} files`);
    process.exit(0);
  }
  if (!baseline) {
    console.error('code size: no baseline yet. Run with --update once to write it.');
    process.exit(1);
  }
  const failures = ratchetFailures(sorted, baseline);
  if (failures.length) {
    console.error(`code size: a function grew past ${MAX_LINES} lines or complexity ${MAX_COMPLEXITY}; split it.`);
    failures.forEach((line) => console.error(`  ${line}`));
    process.exitCode = 1;
  } else {
    const total = Object.values(sorted).reduce((sum, r) => sum + Object.values(r).reduce((a, b) => a + b, 0), 0);
    console.log(`code size: no file grew (${total} older violations in the baseline)`);
  }
}

// Runs only as a program: the test imports violationCounts, lowerBaseline and ratchetFailures.
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
