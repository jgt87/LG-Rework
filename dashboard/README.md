# HDMI Home

A local source selector for the rooted LG OLED48C24LA on firmware 33.31.68 / webOS 10.3.1. Xbox Series X on HDMI2 is the default focus. No ads, accounts, network requests, or online assets.

Version 1.0.1 replaces the console illustration with the owner's supplied transparent `downloads/xsx.png`, bundled unchanged as `xsx.png`, and centers the settings gear outline and circle at (24,24).

Version 1.0.2 gives the right-side HDMI tiles neutral charcoal backgrounds, grayscale labels/icons and a white focus outline. The Xbox tile keeps its green palette.

Version 1.0.3 adds an LG Home recovery action compatible with the optional foreground router described below. The visual layout is unchanged.

Version 1.0.4 implements the approved `review/` design: a local date/24-hour clock, taller source tiles, white focus rings, launch feedback on the activated control, blue/yellow shortcut dots, and configurable alternate HDMI ports. The Xbox tile retains its green surface and supplied photograph; other controls are neutral. Physical-TV validation of this update is pending installation.

Edit `ports.js` to name HDMI1/3/4, select a `port`, `pc`, `controller` or `media` icon, or hide an unused port. The defaults keep all three visible with their port numbers. Hidden ports are skipped by remote navigation; HDMI2 stays the Xbox tile. Run `npm run build` in `dashboard` and reinstall after changing the configuration.

## Install and trial

Version 1.0.6 moves LG Home, Game Optimizer and TV Settings to the upper-left masthead, in that order. Header controls and date/time share font size, line height and control height. D-pad navigation follows the new placement; Xbox remains the initial focus.

Version 1.0.7 offsets the tool group's outer padding, border and home-icon inset so the visible LG Home icon aligns with the source grid's left edge. The date/time remains aligned to the right edge.

Version 1.0.8 normalizes the gear artwork to the home/controller icon footprint, preserving its stroke weight and centered circle. All three icons share the same CSS frame and vertical alignment.

Version 1.0.9 reduces the HDMI source area to 51vh and adds a row of Apple TV (`com.apple.appletv`), YouTube (`youtube.leanback.v4`) and Browser (`com.webos.app.browser`) launch tiles. These IDs are recorded in the TV inventory; the row is static, not a live installed-app catalog. Down from Xbox reaches Apple TV; Left/Right moves across apps; Up returns to sources. Existing preloading/debloat settings are not changed. If an app is later removed, its launch reports failure through the normal notice.

Version 1.0.10 replaces the generic Apple TV/YouTube symbols with their recognizable brand geometry, adapted to monochrome outlines. Source provenance is recorded in `BRAND-ASSETS.md`.

Version 1.0.11 gives the focused green Xbox tile an explicit light-to-dark gradient, with stronger contrast so it remains visible while selected. The resting gradient is unchanged.

Version 1.0.12 darkens the focused Xbox tile and replaces its broad gradient with a lighter green wash fading from the top-right corner. Resting styling remains unchanged.

Version 1.0.13 reduces focus expansion from 160ms to 80ms with a faster-start easing curve. Borders, fills, action text and icons now change immediately on focus, avoiding continuous color repainting across the large Xbox surface. Idle dimming and busy feedback remain unchanged. This is a configured animation reduction, not a measured physical-TV frame-rate claim.

Version 1.0.5 applies `font-variant-numeric: tabular-nums` to the entire date/time group, so both the date and clock inherit equal-width digits.

In PowerShell on the computer, with the TV awake and Homebrew Channel SSH enabled:

```powershell
cd C:\Files\Apps\LG
.\dashboard.ps1 -Action install
```

The script verifies the package hash, installs only `com.local.hdmihome`, verifies the installed version and JavaScript hash, and requests launch. Confirm that the TV displays the dashboard, arrows/OK and the Magic Remote pointer work, HDMI2 returns to the Xbox, and Settings/Game Optimizer open correctly. A successful Luna launch response is not a physical TV test.

Reopen or verify:

```powershell
.\dashboard.ps1 -Action launch
.\dashboard.ps1 -Action verify
```

Installing the app alone does not change startup or remap buttons. The optional router below preserves direct HDMI startup/wake while providing dashboard access through Home.

## Controls

- Arrows and OK: choose/open controls. Xbox is focused when opening or returning to the dashboard.
- Back: open HDMI2.
- Yellow: Game Optimizer; Blue: TV Settings.
- LG Home: open the original home screen.
- After 45 seconds idle the dashboard dims; after two minutes it becomes black. The first key/click wakes it without launching a source.

No HDMI connected/disconnected state is displayed: hardware detection is not implemented. The dashboard makes explicit launch requests, without polling or retry loops.

## Open it from the remote

For the first trial, use the app tile. In LG Input Hook, open its logs, press Home and confirm the detected button ID (often 773). Add a binding that launches `com.local.hdmihome`. If the interface only offers Execute, use `luna-send -n 1 luna://com.webos.applicationManager/launch '{"id":"com.local.hdmihome"}'`. Save changes. An ordinary web app does not receive the Home key.

## HDMI-preserving startup and system Home routing

Install app version 1.0.3 or later first, then run from `C:\Files\Apps\LG`:

```powershell
.\dashboard-home.ps1 -Action enable
```

This runs router regression checks, backs up the original `homeAutoLaunch` setting, switches it off, and installs `/var/lib/webosbrew/init.d/85-lg-hdmi-home`. The helper redirects stock LG Home to the dashboard, but never launches a dashboard from HDMI or on startup/wake. CEC and all HDMI settings remain unchanged. The physical Home button mapping remains available.

HDMI-CEC startup/wake must go straight to the HDMI source. The router leaves every HDMI source alone, including No Signal, and does not schedule a startup dashboard launch. Re-enable the helper to deploy this change, then verify physically with the Xbox.

The dashboard's LG Home control uses a fixed Homebrew Channel execution request to open stock Home with a temporary bypass. It requires the rooted Homebrew service. If that request is denied, use the recovery command below and send the error before changing Luna permissions.

After enabling, restart using Homebrew Channel, then run:

```powershell
.\dashboard-home.ps1 -Action status
```

Test CEC startup directly to HDMI, Home from HDMI2, Xbox/CEC switching without a dashboard takeover, and the dashboard's LG Home escape. A process reported as running does not establish physical remote or wake behavior.

Recovery commands:

```powershell
# Open stock LG Home with a temporary bypass.
.\dashboard-home.ps1 -Action stock-home
# Stop redirection immediately, leaving its hook disabled.
.\dashboard-home.ps1 -Action disable
# Remove the router hook and restore the original Home Auto Launch setting.
.\dashboard-home.ps1 -Action uninstall
```

The original setting is retained in `/var/lib/lg-hdmi-home-router/original-state.json` and copied to `dashboard-home-original-state.json` on this computer. The router log is `/var/lib/lg-hdmi-home-router/router.log`. The helper refuses unreviewed firmware and never modifies stock Home files or mounts over system paths. Uninstalling this helper does not remove any Input Hook binding; remove that separately.

## HDMI No Signal screen

For a plain black screen, LG documents:

1. While an HDMI input shows No Signal, press Mute three times.
2. Turn No Signal Image off if that option is present.
3. Press the red button while No Signal is displayed to hide the message.

Availability varies by TV/firmware. See [LG's instructions](https://www.lg.com/us/support/help-library/lg-webos-tv-how-to-hide-the-no-signal-text-and-background-image--20153903661648). These changes are separate from this app; the package does not edit the HDMI compositor, patch firmware, or substitute a screen over a returning Xbox signal. A custom standby image is not implemented.

## Build and local checks

Node.js is the only build prerequisite; there are no package dependencies.

```powershell
cd C:\Files\Apps\LG\dashboard
node build.mjs
node --test tests/dashboard.test.mjs
node preview.mjs
```

Browser preview: http://127.0.0.1:8787/?preview=1. Preview messages simulate launches; they never connect to a TV. TV-size and narrow screenshots plus REA capture evidence are in `artifacts/`.

The custom builder creates a standard IPK (ar + control/data gzip tar members), includes PNG icons, and emits `dist/build-manifest.json`. Unit tests check archive checksums/members, focus/navigation, launch gating, failure states, Back routing, background suspension and idle protection. The installer must still be tested on the real TV.

## Remove

Before removing HDMI Home, uninstall the optional router with `dashboard-home.ps1 -Action uninstall` and remove its Home binding in LG Input Hook, if configured. Then remove HDMI Home normally from the TV app list. The separate debloat backup and startup repair remain untouched.
