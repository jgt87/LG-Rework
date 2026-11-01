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

The scripts check the model, firmware and SDK before they change anything, and refuse to run on any combination that hasn't been reviewed.

## Using another TV

Other models and firmware versions are onboarded with a read-only compatibility check and a maintainer review:

```powershell
.\init.ps1 -Action connect   # save your TV's address, check root SSH and python3
.\init.ps1 -Action check     # read-only: compares your TV with what each component touches
.\init.ps1 -Action bundle    # package the report for a "Device profile" issue
```

Nothing runs on your TV until its exact model, firmware and SDK appear in `profiles/lg-reviewed-profiles.json`, one component at a time. See [profiles/README.md](profiles/README.md) for what is checked and how reviews work. After `connect`, every launcher uses your saved address.

## Documentation

- [dashboard/README.md](dashboard/README.md): HDMI Home app, build and install
- [tv-cleanup-runbook.md](tv-cleanup-runbook.md): step-by-step apply, verify and rollback
- [DEBLOAT.md](DEBLOAT.md): service cleanup scope and protections
