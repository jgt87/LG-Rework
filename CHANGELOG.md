# Changelog

Notable changes to the LG TV tooling. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Dashboard versions are described in `dashboard/README.md`.

## [Unreleased]

## [1.0.15] - 2026-11-26

### Added
- Rendered design and accessibility checks for the dashboard (`npm run check:design`), and a size check for the scripts (`npm run lint`, `python -m unittest discover tests`).
- `DECISIONS.md` records the dashboard's TV-specific design choices and other settled decisions.

### Changed
- Agent notes are now kept in `AGENTS.md` in the repository.
- Fixed layers on the dashboard (preview banner, status notice, sleep cover) use named z-index tokens; nothing looks different.

### Fixed
- Launcher reports (`*-<action>.txt`, inventories, `init-check.txt`) are now saved as UTF-8 instead of UTF-16, and a new `tv-memory-report.json` no longer starts with a byte-order mark (reports already saved stay as they are).
- The launchers start the TV-side Python scripts with `python3 -I`, so a stray file in the TV's `/tmp` can no longer be imported in place of a standard module.
- `dashboard.ps1` checks the package hash without `Get-FileHash`, so it also works when PowerShell 7 started it.
- `init.ps1 -Action bundle` builds the submission zip with forward-slash entry names.
- An interrupted dashboard build can no longer leave a partial IPK or a manifest that does not match it.
