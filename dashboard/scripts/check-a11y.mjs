// Automated WCAG A/AA scan of every view, in light and dark, with reduced motion, and zero console
// errors in the same run (rules/testing.md, docs/04 §3). Reduced motion first, so the scan never
// samples a colour halfway through a fade.
//
//   node scripts/check-a11y.mjs --config design-check.json [--axe <axe.min.js>] [--port 9563] [--browser <path>]
//   node scripts/check-a11y.mjs --self-test      proves both rules fail on a broken page and hold on a kept one
//
// The scan is axe-core, which this file does not carry: it is read from --axe, else AXE_PATH, else
// node_modules/axe-core in the current folder (`npm i -D axe-core`). Without it the run is a setup
// error, never a pass. It reads the views of design-check.json (check-design-rules.mjs documents the
// file); "a11y": false skips a view, and "a11yIgnore": ["rule-id"] on the config leaves out an axe
// rule, which needs "a11yReason" beside it. "a11yExclude": ["<css>"] leaves out only those elements
// (a contrast table that draws the source's own failing pair on purpose), never the whole rule; it
// needs "a11yReason" too.
//   a11y-violation  an axe WCAG 2 A/AA violation: rule, impact, how many places, the first three
//   console-error   console.error, an uncaught error or an unhandled rejection while the view loads
// Exit 0 = none; 1 = a violation or a console error (view, rule, what); 2 = setup. Run it against the
// dev server or the built app on a test port, never the person's live instance.
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { open, withBrowser } from './check-design-rules.mjs';

export const TAGS = ['a11y-violation', 'console-error'];
const DEFAULTS = { base: '', api: null, wait: 500, size: [1440, 900], a11yIgnore: [], a11yExclude: [], views: [] };
const WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

// Records console errors from the first script of each load on.
const CAPTURE = `window.__a11yErrors = [];
{ const keep = (m) => window.__a11yErrors.push(String(m).slice(0, 160));
  const err = console.error.bind(console); console.error = (...a) => { keep(a.map((x) => (x && x.message) || x).join(' ')); err(...a); };
  addEventListener('error', (e) => keep('uncaught: ' + (e.message || e.error)));
  addEventListener('unhandledrejection', (e) => keep('unhandled rejection: ' + ((e.reason && e.reason.message) || e.reason))); }`;

/** The axe-core source: --axe, AXE_PATH, else the project's node_modules. Null when none is found. */
export function findAxe(given = '', env = process.env, cwd = process.cwd()) {
  for (const p of [given, env.AXE_PATH]) if (p && existsSync(p)) return p;
  try {
    const main = createRequire(join(cwd, 'noop.js')).resolve('axe-core');
    const min = join(main, '..', 'axe.min.js');
    return existsSync(min) ? min : main;
  } catch { return null; }
}

// The context leaves out the excluded elements; with none, it is the whole document as before.
const scan = (ignore, exclude = []) => `axe.run(${exclude.length ? `{ include: [document], exclude: ${JSON.stringify(exclude.map((s) => [s]))} }` : 'document'}, { runOnly: { type: 'tag', values: ${JSON.stringify(WCAG)} }, resultTypes: ['violations'],
  rules: Object.fromEntries(${JSON.stringify(ignore)}.map((r) => [r, { enabled: false }])) })
  .then((r) => JSON.stringify(r.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help, n: v.nodes.length, at: v.nodes.slice(0, 3).map((n) => n.target.join(' ')) }))))`;

/** One view, in one scheme: its violations and its console errors as problem lines. */
async function viewAt(page, cfg, view, axe, dark) {
  await open(page, cfg, view, cfg.size, false, { reduced: true, dark });
  await page.js(axe);
  const found = JSON.parse(await page.js(scan(cfg.a11yIgnore, cfg.a11yExclude)));
  const errors = await page.js('JSON.stringify(window.__a11yErrors || [])').then(JSON.parse);
  const where = `${view.name} (${dark ? 'dark' : 'light'})`;
  return [
    ...found.map((v) => `${where}  [a11y-violation]  ${v.id} (${v.impact}): ${v.help}; ${v.n} place(s): ${v.at.join(', ')}`),
    ...errors.map((e) => `${where}  [console-error]  ${e}`),
  ];
}

export async function run(page, cfg, axe) {
  await page.S('Page.addScriptToEvaluateOnNewDocument', { source: CAPTURE });
  const problems = [];
  let views = 0;
  for (const view of cfg.views) {
    if (view.a11y === false) continue;
    views++;
    for (const dark of [false, true]) problems.push(...await viewAt(page, cfg, view, axe, dark));
  }
  return { problems, views };
}

// ---------- self-test ----------
const selfPage = (ok) => 'data:text/html;charset=utf-8,' + encodeURIComponent(`<!doctype html><html lang="en"><meta charset="utf-8"><title>Settings</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body { margin: 0; padding: 16px; font: 14px/1.5 sans-serif; background: #fff; color: #222; }
@media (prefers-color-scheme: dark) { body { background: #111; color: #eee; } }
.faint { color: ${ok ? 'inherit' : '#c8c8c8'}; } .sample { color: #fff; background: #e4572e; }</style>
<main><h1>Settings</h1><p class="faint">Changes are saved as you make them.</p>
<p class="sample">Aa</p>
<button id="go"${ok ? '' : ' aria-label=""'}>${ok ? 'Save' : '<svg width="16" height="16"></svg>'}</button>
${ok ? '<img src="data:," alt="">' : '<img src="data:,">'}</main>
<script>${ok ? '' : 'console.error("could not load the settings");'}</script>`);

async function selfTest(o) {
  const axePath = findAxe(o.axe);
  if (!axePath) { console.error('No axe-core: pass --axe <axe.min.js>, set AXE_PATH, or run from a folder with node_modules/axe-core.'); process.exit(2); }
  const view = (ok) => ({ name: ok ? 'kept' : 'broken', url: selfPage(ok), ready: 'main' });
  // The kept page holds a sample that fails contrast on purpose, left out by a11yExclude: the
  // exclusion is proven too (the broken page fails on its own faint text either way).
  const cfg = { ...DEFAULTS, wait: 150, a11yExclude: ['.sample'], views: [view(false), view(true)] };
  const { problems } = await withBrowser(o, cfg, (page) => run(page, cfg, readFileSync(axePath, 'utf8')));
  const missed = TAGS.filter((t) => !problems.some((p) => p.startsWith('broken') && p.includes(`[${t}]`)));
  const wrong = problems.filter((p) => p.startsWith('kept'));
  const good = !missed.length && !wrong.length;
  console.log(good ? `OK: the broken page failed both rules (${TAGS.join(', ')}), and the kept page was clean.`
    : `FAIL: not caught on the broken page: ${missed.join(', ') || 'none'}; wrongly flagged on the kept page: ${wrong.join(' | ') || 'none'}.`);
  process.exit(good ? 0 : 1);
}

function parseArgs(argv) {
  const o = { config: '', port: 9563, browser: '', axe: '', selfTest: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--config') o.config = argv[++i];
    else if (a === '--port') o.port = Number(argv[++i]);
    else if (a === '--browser') o.browser = argv[++i];
    else if (a === '--axe') o.axe = argv[++i];
    else if (a === '--self-test') o.selfTest = true;
    else { console.error(`Unknown argument: ${a}`); process.exit(2); }
  }
  return o;
}

/** The config with its defaults; exits 2 (setup) when there is nothing to scan or an ignore has no reason. */
function loadConfig(o) {
  if (!o.config) { console.error('Give --config <design-check.json> (or --self-test).'); process.exit(2); }
  const cfg = { ...DEFAULTS, ...JSON.parse(readFileSync(o.config, 'utf8')) };
  if (!cfg.views.some((v) => v.a11y !== false)) { console.error('The config lists no views to scan: nothing would be checked.'); process.exit(2); }
  if ((cfg.a11yIgnore.length || cfg.a11yExclude.length) && !(cfg.a11yReason?.trim().length >= 10)) { console.error('"a11yIgnore" and "a11yExclude" need an "a11yReason" of a sentence.'); process.exit(2); }
  return cfg;
}

async function main() {
  const o = parseArgs(process.argv.slice(2));
  if (o.selfTest) return selfTest(o);
  const cfg = loadConfig(o);
  const axePath = findAxe(o.axe);
  if (!axePath) { console.error('No axe-core found: run `npm i -D axe-core` in the project, or pass --axe <axe.min.js> (or set AXE_PATH).'); process.exit(2); }
  const { problems, views } = await withBrowser(o, cfg, (page) => run(page, cfg, readFileSync(axePath, 'utf8')));
  const left = [...cfg.a11yIgnore, ...cfg.a11yExclude.map((s) => `elements ${s}`)];
  if (left.length) console.log(`Left out: ${left.join(', ')} (${cfg.a11yReason})`);
  if (problems.length) { console.log('Accessibility rules broken:\n' + problems.join('\n')); process.exit(1); }
  console.log(`OK: ${views} view(s) scanned in light and dark with reduced motion: no WCAG A/AA violation, no console error.`);
  process.exit(0);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((e) => { console.error(`check-a11y: ${e.message}`); process.exit(2); });
}
