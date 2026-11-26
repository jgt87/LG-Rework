// Runs both rendered checks on a built app with invented data: a small server on the test port in the
// config's "base" serves the build folder and answers every path the config's "api" block lists (any
// path: /api/status, /data/demo.json) and refuses writes to any other (api-stubs.mjs), then
// check-design-rules.mjs (every view in the config) and check-control-rows.mjs (the first screen at
// the given widths) run against it, and the server stops. Every check also answers "api" in the
// browser the same way, so they all see the same data. Never the person's running app.
//
//   node scripts/design-checks.mjs --root ../dist [--config design-check.json] [--widths 1440,720,390]
//        [--design-port 9571] [--rows-port 9572] [--interaction [--interaction-port 9573]]
//        [--a11y [--a11y-port 9574] [--axe <axe.min.js>]] [--elements [--elements-port 9575]]
//
// --interaction also runs check-interaction.mjs on the same views (menus, dialogs, tooltips, press,
// drag and zoom answered as a person would use them); it clicks the app's triggers and types into
// its search box, so it runs on this test server only. --a11y also runs check-a11y.mjs (an axe WCAG
// A/AA scan in light and dark with reduced motion, and no console errors); it needs axe-core in the
// project (`npm i -D axe-core`) or --axe. --elements also runs check-elements.mjs (the element
// contracts) when the config names its elements under "elements"; without them it says so and skips.
//
// Exit: the largest of the checks' codes (0 pass, 1 a rule broken, 2 setup). Pick debug ports
// apart from the checks' defaults (9558, 9559) when another project may run its checks at the same
// time. From a PowerShell bridge with a React UI (`npm run check:design`), 16 Nov 2026.
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { answer } from './api-stubs.mjs';

const here = import.meta.dirname;
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png', '.woff2': 'font/woff2', '.json': 'application/json', '.ico': 'image/x-icon' };

// The flags: a value flag names its option and how to read the value; a switch sets its option.
const VALUES = { '--config': ['config', String], '--root': ['root', String], '--widths': ['widths', String], '--axe': ['axe', String],
  '--design-port': ['designPort', Number], '--rows-port': ['rowsPort', Number], '--interaction-port': ['interactionPort', Number],
  '--a11y-port': ['a11yPort', Number], '--elements-port': ['elementsPort', Number] };
const SWITCHES = { '--interaction': 'interaction', '--a11y': 'a11y', '--elements': 'elements' };

function parseArgs(argv) {
  const o = { config: 'design-check.json', root: '', widths: '1440,720,390', designPort: 9571, rowsPort: 9572, interaction: false, interactionPort: 9573, a11y: false, a11yPort: 9574, axe: '', elements: false, elementsPort: 9575 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (SWITCHES[a]) o[SWITCHES[a]] = true;
    else if (VALUES[a]) { const [key, read] = VALUES[a]; o[key] = read(argv[++i]); }
    else { console.error(`Unknown argument: ${a}`); process.exit(2); }
  }
  if (!o.root) { console.error('Give --root <the built app folder>.'); process.exit(2); }
  return o;
}

/** The test server's requests: any path the config's "api" lists (/api/status, /data/demo.json)
 *  answered from it, a write to any other path refused (405), other /api/* a 404, and files from the
 *  build folder `root` (normalized and absolute), anything outside it refused. Only /api/* was
 *  stubbed, so an app whose data is static JSON under /data/ could not be checked here. */
export const staticHandler = (root, cfg) => async (req, res) => {
  const path = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  const a = answer(cfg.api, req.method, req.url) ?? (path.startsWith('/api/') ? { status: 404, body: { error: 'not in the design config "api"' } } : null);
  if (a) {
    res.writeHead(a.status, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(a.body));
    return;
  }
  const file = normalize(join(root, path === '/' ? 'index.html' : path));
  if (!file.startsWith(root)) { res.writeHead(403); res.end(); return; }
  const send = async (f) => { const b = await readFile(f); res.writeHead(200, { 'Content-Type': types[extname(f)] || 'application/octet-stream' }); res.end(b); };
  // A missing file falls back to index.html (the app's own routes); without one it is a 404, not a crash.
  try { await send(file); } catch { try { await send(join(root, 'index.html')); } catch { res.writeHead(404); res.end(); } }
};

const run = (args) => new Promise((done) => {
  const p = spawn(process.execPath, args, { stdio: 'inherit' });
  p.on('exit', (code) => done(code ?? 2));
  p.on('error', () => done(2));
});

function main() {
  const o = parseArgs(process.argv.slice(2));
  const configPath = resolve(o.config);
  const cfg = JSON.parse(readFileSync(configPath, 'utf8'));
  const base = new URL(cfg.base);
  const server = createServer(staticHandler(normalize(resolve(o.root)), cfg));
  server.on('error', (e) => { console.error(`design-checks: the test port ${base.port} is not free (${e.message})`); process.exit(2); });
  server.listen(Number(base.port), base.hostname, async () => {
    const design = await run([join(here, 'check-design-rules.mjs'), '--config', configPath, '--port', String(o.designPort)]);
    // "rowsIgnore" in the config: controls the row check leaves out, such as the parts of a composite
    // field (an input with its own small button) that are one control to the eye.
    const ignore = cfg.rowsIgnore ? ['--ignore', cfg.rowsIgnore] : [];
    const rows = await run([join(here, 'check-control-rows.mjs'), cfg.base + '/', '--widths', o.widths, '--port', String(o.rowsPort), '--config', configPath, ...ignore]);
    const interaction = o.interaction ? await run([join(here, 'check-interaction.mjs'), '--config', configPath, '--port', String(o.interactionPort)]) : 0;
    const axe = o.axe ? ['--axe', o.axe] : [];
    const a11y = o.a11y ? await run([join(here, 'check-a11y.mjs'), '--config', configPath, '--port', String(o.a11yPort), ...axe]) : 0;
    const named = o.elements && Object.keys(cfg.elements ?? {}).length;
    if (o.elements && !named) console.log('check-elements: skipped, the config names no "elements" (e.g. "el-button": ".btn")');
    const elements = named ? await run([join(here, 'check-elements.mjs'), '--config', configPath, '--port', String(o.elementsPort)]) : 0;
    server.close();
    process.exit(Math.max(design, rows, interaction, a11y, elements));
  });
}

// Runs only as a program: the test imports staticHandler.
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
