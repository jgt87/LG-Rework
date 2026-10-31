# LG TV dashboard and cleanup tools

A custom HDMI input dashboard (`dashboard/`) and reversible webOS cleanup scripts for a rooted LG TV.

## Tested hardware

This was built for and used on an **LG OLED C2 (2022)**:

| Item | Value |
|---|---|
| Model | LG OLED48C24LA (48" C2) |
| Firmware | 33.31.68 |
| webOS SDK | 10.3.1 |
| Root | Homebrew Channel |

The scripts check the model, firmware and SDK before they change anything, and refuse to run on any other combination. Using them on another model or firmware means reviewing the TV inventory again first.

## Documentation

- [dashboard/README.md](dashboard/README.md): HDMI Home app, build and install
- [tv-cleanup-runbook.md](tv-cleanup-runbook.md): step-by-step apply, verify and rollback
- [DEBLOAT.md](DEBLOAT.md): service cleanup scope and protections
