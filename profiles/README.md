# Device profiles

Every component checks the TV's exact model, firmware and webOS SDK before it changes anything. It runs only when that combination is the reference TV, or when it appears in [`lg-reviewed-profiles.json`](lg-reviewed-profiles.json) with that component listed. A firmware update counts as a new combination and needs a new review.

Profiles are added only by a maintainer, after reviewing a compatibility report from the TV. You can't unlock a component on your own TV by running a command.

## Onboarding your TV

You need root through [Homebrew Channel](https://github.com/webosbrew/webos-homebrew-channel) with SSH enabled, `python3` on the TV, and Windows PowerShell 5.1 or PowerShell 7 on your computer. Each command asks for the TV root password.

```powershell
.\init.ps1 -Action connect      # asks for the TV address, saves it in device.local.json, checks root access
.\init.ps1 -Action check        # read-only compatibility check -> profiles\<model>_<firmware>\compatibility-report.json
.\init.ps1 -Action bundle       # zips the report and a summary for review
```

The check changes nothing on the TV. It imports the target lists from the component scripts and checks each target on your TV:

| Component | What is checked |
|---|---|
| `dashboard` | HDMI input apps (the Xbox tile uses HDMI2), developer app directory, Homebrew Channel |
| `home-router` | Foreground and power-state APIs, the `homeAutoLaunch` setting, the stock Home app, Homebrew startup hooks |
| `hdmi-cleanup` | The region's launcher block list, the preload configuration and API, the promotional settings, which tile targets and protected apps exist |
| `alexa-tiles` | The launcher block list and both Alexa app IDs |
| `home-layout` | The LG Home layout file and its SHA-256 against the reviewed file |
| `no-signal-background` | The `noSignalScreenSaver` setting |
| `debloat` | Each target unit's definition SHA-256 against the reviewed one, reverse dependencies, target executables, protected core units, SDX present (SDX is never a target) |

Each component comes out as one of:
- **matches**: everything it touches looks the same as on a reviewed TV.
- **differs**: something changed, so a maintainer has to review it.
- **missing**: something it needs isn't there, so it can't run without a script change.

The launcher block list is chosen by region, for example `NLD.json`, so TVs from other regions show `hdmi-cleanup` and `alexa-tiles` as missing until the scripts support that region.

The report contains names, paths, SHA-256 hashes and statuses only. It has no unit-file text, serial numbers, network details or account data. `bundle` refuses to package anything that looks like a MAC or email address.

## Submitting a profile

Open a **Device profile** issue and attach the zip, or open a pull request that adds `profiles/<model>_<firmware>/compatibility-report.json` and `submission.md`. Don't edit `lg-reviewed-profiles.json` in your pull request. The maintainer adds the entry.

## Review checklist (maintainers)

A component may be added to a profile only when all of these hold:

1. The report was produced by the current `init-tv.py`, and the model, firmware and SDK in it match the profile entry exactly.
2. Every check for that component is **matches**. Anything else means changing the script for that firmware first, in a separate pull request with its own review.
3. `debloat` only: every unit hash matches, with no reverse dependencies, all protected core units load, and SDX is present. Never add a unit without reviewing it against `debloat-reviewed-units.json` and `DEBLOAT.md`.
4. `home-layout` only: the layout hash equals the reviewed hash. A different file means a new reviewed patch, never a looser check.
5. The submitter has confirmed the physical checks in `submission.md`.

Then add the entry with `id`, `modelName`, `firmwareVersion`, `sdkVersion`, `reviewedBy`, `reviewedOn` and only the approved `components`, and run `python -m unittest discover tests`. Reviewing component by component is normal. A profile can list `dashboard` and `home-router` long before `debloat`.

## How the guard reads profiles

Each launcher uploads `lg-reviewed-profiles.json` next to its script, and startup installs copy it next to the persistent script. The reference TV (`OLED48C24LA / 33.31.68 / 10.3.1`) is also built into every script, so it keeps working even if the file is missing. The dashboard installer checks the model only, because it installs nothing but a web app.
