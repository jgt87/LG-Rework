# LG HDMI dashboard and debloat runbook

Updated: 2026-10-30

| Item | Value |
|---|---|
| TV | LG OLED48C24LA |
| Address | `192.168.1.44` |
| Reviewed firmware / SDK | `33.31.68` / `10.3.1` |
| Local working folder | `C:\Files\Apps\LG` |
| Custom dashboard | HDMI Home, `com.local.hdmihome`; 1.0.3 previously installed, 1.0.4 review design built locally pending installation |
| Primary input | HDMI2, Xbox Series X |
| Explicit exclusion | **Keep SDX enabled and running.** |

## Current state and where to resume

| Component | Recorded state |
|---|---|
| Dashboard | Version 1.0.3 installed and launch accepted. |
| Physical Home button | Input Hook saved ID `773` → Launch App → `com.local.hdmihome`. |
| Dashboard-first router | Older router left HDMI No Signal open. Updated local helper adds one dashboard launch at worker startup and each wake; deployment and reboot test pending. Run `dashboard-home.ps1 -Action enable` to update it. |
| Tile hiding / preload / promotion cleanup | Startup helper updated successfully; `sportsAlarm` restored to off. |
| LG Home layout | Trial applied successfully; rows removed and banner hidden. Visual check still required. |
| Additional service cleanup | Latest trial succeeded: selected units stopped/masked, executable overrides verified, no target processes running. SDX hash unchanged and process running; previously active core services remain active. Nudge remains excluded. **Resume at step 3: physical validation before persistence.** |
| Layout/service startup persistence | Not yet confirmed installed. |

Commands below run in PowerShell from the working folder. SSH/SCP will ask for the TV root password; enter it interactively. Do not put passwords in scripts or reports.

```powershell
Set-Location C:\Files\Apps\LG
```

## 1. Check the LG Home layout trial

Open **LG Home** using its button in our dashboard, since the physical Home button is mapped to the custom dashboard.

- Sports and other Quick Cards should be absent.
- The recommendation/Device Function shelf should be absent.
- Banner artwork should be hidden. Blank space above the app row is expected.
- The app row and native navigation should remain usable.

Check the mounted file:

```powershell
.\lg-home-layout.ps1 -Action verify
```

Expected: `Verified mounted layout` followed by the removed-row/banner summary. File verification does not prove that the visible TV UI looks correct.

If a full reboot has occurred since the trial, reapply it first:

```powershell
.\lg-home-layout.ps1 -Action apply
```

## 2. Apply the additional service cleanup trial

After the reported stop/rollback failures, perform a full reboot first. Check normal HDMI picture/sound, Settings and Home before retrying. Reboot removes trial runtime masks/mounts and pending jobs. The layout trial will also disappear unless its startup hook was installed; reapply it using step 1. The updated script leaves `nudge` enabled, queues rollback restarts without blocking, and preserves the primary failure if rollback also fails.

```powershell
.\debloat-tv.ps1 -Action apply
```

Expected:

- Regression checks pass.
- Selected services are stopped/masked and executable overrides are present.
- No target processes remain running.
- SDX executable is unchanged and its process is running.
- Previously active protected core units remain active.

The wrapper saves `debloat-tv-apply.txt` and attempts to copy the original-state backup locally. If the command prints `STOP`, throws an error, or reports failed checks, retain the report and stop this sequence. Do not install startup persistence to work around a failure. Apply attempts rollback on mutation failures; confirm recovery before retrying.

## 3. Validate the TV before persistence

Test these on the physical TV:

- Home opens our dashboard.
- The Xbox tile opens HDMI2 with normal picture and sound.
- Volume and remote navigation work.
- Settings and Game Optimizer open normally.
- The dashboard's LG Home button still provides the stock interface.
- Standby/wake works, and Xbox HDMI-CEC can switch to HDMI2.

Then run:

```powershell
.\hdmi-cleanup.ps1 -Action verify
.\lg-home-layout.ps1 -Action verify
.\debloat-tv.ps1 -Action verify
.\dashboard-home.ps1 -Action status
```

The router status should show `Enabled: True`, a running process and `Startup hook: True`. Check `lastError` and subscription status. If firmware identity, dependency or SDX checks fail, stop and inspect the report; do not weaken the guards.

## 4. Make the successful trials persistent

Only proceed after step 3 passes:

```powershell
.\lg-home-layout.ps1 -Action install-startup
.\debloat-tv.ps1 -Action install-startup
```

The existing preload/tile/promotion startup helper was already updated. To reinstall that helper after a future script update:

```powershell
.\hdmi-cleanup.ps1 -Action install-startup
```

Its repair now restores backed-up promotional settings as well as missing tile blocks. It retains the original backup and does not change Home Auto Launch.

### Hide the two built-in Alexa apps

```powershell
.\alexa-tiles.ps1 -Action apply
```

This blocks only `amazon.alexa.view` and `amazon.alexapr` from the launcher and retains the built-in packages. Reopen LG Home and inspect the tiles. If correct, use `.\alexa-tiles.ps1 -Action install-startup`; check after reboot with `.\alexa-tiles.ps1 -Action verify`. Undo independently with `.\alexa-tiles.ps1 -Action restore`. This does not change SDX or services; the service cleanup separately targets the observed Alexa trigger. Its snapshot is `/var/lib/lg-alexa-tiles/original-state.json`, and its hook is `/var/lib/webosbrew/init.d/91-lg-alexa-tiles`. It shares the older cleanup lock to prevent competing block-list writes.

## 5. Reboot and check persistence

To update the dashboard router for the reported No Signal startup issue:

```powershell
.\dashboard-home.ps1 -Action enable
```

The updated router opens the dashboard once from LG Home or the initial HDMI app at startup/wake. Later foreground changes cancel the queued launch; it does not continuously take over HDMI. It cannot distinguish live HDMI from No Signal, so an already-running Xbox may be covered once by the dashboard. Restarting/enabling the worker also triggers this one-shot. Original settings backup is retained. Physical startup/wake validation remains required.

Use a **full reboot**, such as Homebrew Channel's reboot option. A remote off/on cycle with Quick Start+ can retain the current session and does not establish cold-boot persistence.

For the dashboard-first test, initially leave the Xbox off. After startup, allow at least **75 seconds** for the background cleanup worker; if it is still running, wait for its log to finish. Then rerun:

```powershell
.\hdmi-cleanup.ps1 -Action verify
.\lg-home-layout.ps1 -Action verify
.\debloat-tv.ps1 -Action verify
.\dashboard-home.ps1 -Action status
```

Repeat the physical checks from step 3. Start the Xbox and confirm CEC switches to HDMI2. LG Home may briefly appear during startup before dashboard routing takes effect.

## Recovery and rollback

### Plain black HDMI No Signal background

The owner chose plain black in place of the gallery artwork. Apply the native persistent setting (no QML patch or startup hook):

```powershell
.\no-signal-background.ps1 -Action apply
```

This changes only `general.noSignalScreenSaver` to `off`, with readback verification. It keeps the No Signal message, automatic power-off, HDMI/CEC, OLED protection and SDX unchanged. If the artwork remains visible, switch away from the HDMI input and back. Check later with `.\no-signal-background.ps1 -Action verify`; undo with `.\no-signal-background.ps1 -Action restore`. Original value is retained at `/var/lib/lg-no-signal-background/original-state.json` and copied to `no-signal-background-original-state.json` locally. Deployment/visual result is pending the owner's run.

### Undo the new service and layout cleanup

```powershell
.\debloat-tv.ps1 -Action restore
.\lg-home-layout.ps1 -Action restore
```

Then reboot normally to initialize on-demand services again. Restore removes the owned masks, mounts and startup hooks while retaining backups. If service cleanup was never applied and has no state file, skip its restore command.

Before persistence is installed, a full reboot also removes the new layout/service runtime trial. This does not undo the older persistent preload/promotion cleanup or the dashboard router.

### Stop dashboard redirection temporarily

```powershell
.\dashboard-home.ps1 -Action disable
```

To remove its startup routing and restore the saved original Home Auto Launch setting:

```powershell
.\dashboard-home.ps1 -Action uninstall
```

The Input Hook Home-button binding is separate. Remove only ID `773` in Input Hook and save changes if you also want the physical Home button restored to LG Home. Do this before uninstalling the custom dashboard app.

### Undo the earlier preload/tile/promotion cleanup

```powershell
.\hdmi-cleanup.ps1 -Action restore
```

This uses its own original backup and removes its startup repair. It does not remove the dashboard, router, layout hook or service hook.

If SSH is refused, open Homebrew Channel on the TV and check its SSH server is running before attempting another command.

## Scope and protections

The new cleanup targets observed optional voice/Alexa programs, camera activation, car/phone/buddy integration, family-care activation, LG Channels helpers, promotions, content mining, diagnostic upload and logging. The older cleanup disables selected streaming/browser/voice preloads and hides selected built-in app tiles. App packages and firmware files are not deleted.

**SDX is never a target.** It runs as `/usr/sbin/sdx` on this TV without a corresponding installed `sdx.service`. Verification checks the executable hash and actual running process, not just systemd status. Target-unit definitions must match the reviewed inventory; live stop-propagation checks reject unsafe dependencies.

The scripts exclude Always Ready, tvdataexchanger, PAC runner, network/discovery services, Settings/SAM, compositor, input, audio, panel and OLED protection. Process checks do not establish complete telemetry elimination or measured RAM savings.

`nudge` is also excluded following its stop/restart failure. Promotions remain suppressed through the existing settings and Home layout. Historical nudge overrides are accepted only for removal during restore; the old snapshot is archived before the revised catalog is saved.

## Reports, backups and startup hooks

### Measure RAM after dashboard startup

Perform a full reboot, leave the Xbox off and allow about 90 seconds for startup cleanup. Confirm our dashboard is open (press Home if needed), then run:

```powershell
.\measure-tv-memory.ps1
```

This takes three read-only samples ten seconds apart and saves `tv-memory-report.json`. It prints total/available/used RAM and swap in MiB, records boot uptime and the foreground reply, and collects per-process RSS/PSS/private memory when readable. Used RAM is `MemTotal - MemAvailable`, not total minus free; reclaimable caches should not be counted as permanently consumed memory. PSS apportions shared mappings, while RSS can double-count them.

The report includes dashboard candidates found by app ID in process arguments, but shared browser helpers may not be uniquely attributable to the app. `Dashboard=False` is not proof that the app is closed; inspect the raw foreground reply. Python and SSH consume some RAM while measuring, and the observer PID is recorded. No cache dropping, service stops or persistent changes are performed. For comparisons use the same reboot delay, open app and Xbox state. Do not infer saved memory from unmatched historical snapshots.

| Component | Local report | TV backup/state | Startup hook |
|---|---|---|---|
| Earlier cleanup | `hdmi-cleanup-<action>.txt` | `/var/lib/lg-hdmi-cleanup/original-state.json` | `/var/lib/webosbrew/init.d/90-lg-hdmi-cleanup` |
| LG Home layout | `lg-home-layout-<action>.txt` | `/var/lib/lg-home-layout/original-home.xml` | `/var/lib/webosbrew/init.d/84-lg-home-layout` |
| Service cleanup | `debloat-tv-<action>.txt` | `/var/lib/lg-reviewed-debloat/original-state.json` | `/var/lib/webosbrew/init.d/88-lg-reviewed-debloat` |
| Dashboard router | `dashboard-home-<action>.txt` | `/var/lib/lg-hdmi-home-router/original-state.json` | `/var/lib/webosbrew/init.d/85-lg-hdmi-home` |

Boot logs live in each component's `/var/lib/.../startup.log`, except that the dashboard router's recent log is included by its status command. Preserve original-state files; do not replace them with a post-cleanup snapshot.

## Known failures already fixed

| Symptom | Resolution |
|---|---|
| `setting still enabled: sportsAlarm` during repair | Updated repair restores backed-up promotional settings to off. Run `hdmi-cleanup.ps1 -Action install-startup` to refresh the persistent copy. |
| `ModuleNotFoundError: No module named 'xml'` | Layout script now patches only the checksum-locked captured file without Python's XML module. That failed import changed nothing. The revised layout trial subsequently succeeded. |
| `systemctl stop service-logger.service` timeout | Failed trial reported rollback. Updated script queues nonblocking stops and polls actual state. Its fallback checks the exact logger main PID/executable before SIGKILL; other processes, including SDX, cannot use that fallback. Reboot before retrying. |
| Rollback timed out on `systemctl start nudge.service` | Recovery is unconfirmed. Full reboot and physical checks first. Updated catalog preserves nudge, rollback starts are nonblocking, and logs retain both primary and rollback failures. |

Do not reuse these scripts on a different model or firmware without reviewing the new inventory. Further implementation details and source links are in [DEBLOAT.md](DEBLOAT.md) and [debloat-research.md](debloat-research.md).
