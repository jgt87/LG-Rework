# AGENTS.md

Guidance for coding agents working in this repository. Canonical agent notes (D-007); a
tool-specific agent file only imports this one.

## What this is

Tooling for one rooted LG OLED48C24LA TV (firmware `33.31.68`, webOS SDK `10.3.1`, IP `192.168.1.44`, Homebrew Channel root). The workspace has two parts:

1. **HDMI Home dashboard** (`dashboard/`): a packaged webOS web app (`com.local.hdmihome`) that replaces LG Home with a local input selector. The Xbox Series X on HDMI2 is the primary tile.
2. **TV-side maintenance scripts** (repo root): reversible cleanup, debloat, layout and settings changes applied over SSH.

`tv-cleanup-runbook.md` is the operator runbook and the record of current deployment state. Update its "Current state" table when a component's status changes. `PRODUCT.md` and `DESIGN.md` hold the product and design specs (impeccable format; the `.impeccable/` folders are that tool's state). `DEBLOAT.md` and `debloat-research.md` cover the service-cleanup rationale. `DECISIONS.md` holds the settled decisions and every deviation from a shared rule; cite its ids, never restate them.

Third-party upstream sources are kept for reference only and are not part of the project: `homebrew-channel-source/`, `slopbro/`, `webos-debloat-upstream/`. `slopbro/` contains a TV key file, so never publish it.

## Commands

"Done" means all of these pass.

The shipped dashboard has no npm dependencies; `axe-core` is a dev-only dependency for the rendered checks (D-008). Run these from `dashboard/`:

```powershell
node build.mjs                      # or npm run build → dist/<id>_<version>_all.ipk + dist/build-manifest.json
node --test tests/dashboard.test.mjs  # or npm test
node --test --test-name-pattern "Unused ports" tests/dashboard.test.mjs   # single test
npm run lint                        # size ratchet for the JS files (scripts/check-code-size.mjs)
npm run check:design                # rendered design checks + axe scan on a test port (npm install first)
node preview.mjs                    # http://127.0.0.1:8787/?preview=1 (simulated launches, never touches the TV)
```

From the repo root, profile/guard/onboarding, launcher and Python size-ratchet tests: `python -m unittest discover tests`; the injection-sink check (a CommonShared copy, pytest style): `python -I -m pytest -q -p no:cacheprovider tests/test_injection.py`. Onboarding for other TVs: `.\init.ps1 -Action connect|check|bundle` (see `profiles/README.md`).

Install or verify on the TV from the repo root: `.\dashboard.ps1 -Action install|verify|launch`.

### Dashboard architecture

- Plain ES5-style IIFE in `app.js`. There is no framework and no bundler. `index.html`, `style.css`, `app.js`, `ports.js` and `xsx.png` ship as-is. The `preview.mjs` allowlist and the `build.mjs` asset list name these files explicitly, so update both lists when you add a shipped file.
- `ports.js` sets `window.HDMI_PORTS`, the user config for HDMI1/3/4 (name, icon, unused). HDMI2 is always the Xbox tile.
- Launches go through `PalmServiceBridge` to `applicationManager`. The LG Home escape runs a fixed shell command through the Homebrew Channel exec service, which calls the router's `stock-home`. Preview mode (`?preview=1`), or a missing bridge, must never claim to switch a physical TV.
- `build.mjs` is a hand-written IPK builder (ar + gzip tar, generated PNG icons). It reads the version from `appinfo.json` and writes the IPK SHA-256 and `app.js` SHA-256 into `build-manifest.json`. `dashboard.ps1` and `dashboard-tv.py` check both hashes on install.
- Tests run `app.js` in a `vm` context with a fake DOM, timers and bridge. They cover focus/D-pad navigation, launch gating, busy/failure states, idle dim and cover, and IPK structure.
- Releasing a version: bump `version` in both `appinfo.json` and `package.json`, rebuild, and add a "Version 1.0.N …" paragraph to `dashboard/README.md`. If the visual spec changed, update `DESIGN.md` too. Old IPKs in `dist/` are kept.
- `dashboard/home-router.py` is deployed separately by `dashboard-home.ps1`. It is a Python daemon on the TV that subscribes to foreground and power Luna events. It redirects stock Home to the dashboard and runs a one-shot launch at startup and on wake.
- `dashboard/scripts/` and `scripts/check-code-size.mjs`, `scripts/code-size-reader.mjs` are copies of CommonShared templates: refresh by copying over them and keep only their CONFIG block. `dashboard/design-check.json` configures the rendered checks and lists the audit's accepted deviations by decision id.

## TV maintenance scripts (repo root)

Every component is a pair: `<name>.ps1` (Windows launcher) and `<name>.py` (runs on the TV with `python3`). The `.ps1` launcher:
1. `scp -O` uploads the `.py` to `/tmp` on the TV.
2. Runs `self-test && <action>` over `ssh root@192.168.1.44` for mutating actions.
3. Shows the output and saves it to `<name>-<action>.txt` in the repo root through `tv-report.ps1` (UTF-8, no BOM). These `.txt` files are run reports, not source.
4. On apply/enable/restore, copies the TV-side `original-state.json` back to `<name>-original-state.json`.

Actions are usually `apply | verify | restore | install-startup | self-test`, with some per-script extras (see each `param(ValidateSet…)`). Startup persistence uses Homebrew init hooks in `/var/lib/webosbrew/init.d/NN-…`. State and backups live in `/var/lib/lg-*/`. The runbook has a table mapping each component to its paths.

The agent shell cannot reach the TV. The user runs the `.ps1` launchers themselves and types the root password interactively. Never put credentials in scripts. Give the user the exact commands and read back the `.txt` reports they produce.

### Invariants the scripts enforce. Keep them.

- **Firmware identity guard**: scripts refuse to run unless the model, firmware and SDK match `OLED48C24LA / 33.31.68 / 10.3.1` (built in as `REFERENCE_TV`) or an exact entry in `profiles/lg-reviewed-profiles.json` that lists the component. Do not weaken it. The six `reviewed_tv`/`keep_profiles` copies must stay identical (tested). Profiles are added only by the maintainer after reviewing an `init.ps1 -Action check` report (see `profiles/README.md`); never add one from a local override. `init-tv.py` must stay read-only.
- **SDX is never a target.** It runs as `/usr/sbin/sdx` with no unit file. Verification checks its executable hash and its live process.
- `nudge`, Always Ready, tvdataexchanger, network/discovery, Settings/SAM, compositor, input, audio, panel and OLED protection are excluded. Target units must match `debloat-reviewed-units.json`.
- Everything must be reversible. Never overwrite an `original-state.json` with a post-change snapshot. Do not delete app packages or firmware files.
- Do not change picture, audio, HDMI-CEC or OLED-care settings.
- Never fabricate HDMI signal or connection status in the UI. Never present a browser preview, a successful build or a Luna "launched" reply as physical-TV verification.
- Inventory and report files (`*-inventory.json/txt`, `tv-memory-report.json`, `lg-home-original.xml`, the `*-<action>.txt` reports) are captured TV data. Treat them as read-only reference (D-001).

## Gotchas

- Launchers write reports through `tv-report.ps1`, never `Tee-Object` or `Set-Content -Encoding utf8` — Windows PowerShell 5.1 wrote every report as UTF-16 or with a BOM (audit, 2026-11-26); `tests/test_profiles.py` fails on either.
- Long TV-side functions are held by the size ratchet, not refactored blind (D-006) — the agent shell cannot re-verify them on the TV (audit, 2026-11-26).

<!-- commonshared:begin (managed by __CommonShared/sync; edit it there, not here) -->
## Shared practices
This project follows the generic best practices in `C:/Files/Apps/__CommonShared`. This file
and the project's own DESIGN.md / PRODUCT.md win where they are more specific.
- Conventions: its `docs/` (visual design 01, interaction 02, testing 04, structure and
  release 05, code organisation 08, change management 09, gitignore 11, line endings 12,
  agent workflow 14, lessons learned 15, UI fixes 17).
- Rules: `.claude/rules/commonshared-*.md` are managed copies of its `rules/` (loaded by
  file type; refreshed at session start and by its sync). Do not edit them: put this
  project's own rules in `.claude/rules/project-<area>.md`, which win on conflict.
- Starters: its `templates/` (tokens, gitignore, gitattributes, editorconfig, check scripts,
  design-rule tests). Copy in; do not link.
- Decisions: the operator's settled decisions and every deviation from a shared rule are
  entries in `DECISIONS.md` (its docs/09 §8); elsewhere cite the id (`D-001`), never restate it.
- Audit: `python -I C:/Files/Apps/__CommonShared/.claude/skills/new-project/scripts/check_project.py .`
- A lesson learned here that would hold in any project goes in `tasks/lessons.md` (rule,
  Why with date, check). It is pulled upstream into the shared lessons, which load at every
  session start through the shared-lessons hook.
<!-- commonshared:end -->
