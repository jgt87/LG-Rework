# Reviewed HDMI-only cleanup

Prepared for OLED48C24LA firmware 33.31.68 / SDK 10.3.1 from `debloat-inventory.json`.
The owner authorized Home, preloads, unused features and telemetry cleanup and explicitly excluded SDX.

## Apply a reversible trial

Run from `C:\Files\Apps\LG`:

```powershell
.\hdmi-cleanup.ps1 -Action repair
.\lg-home-layout.ps1 -Action apply
.\debloat-tv.ps1 -Action apply
```

The first command maintains the previously backed-up preload/promotion settings. The second hides Quick Cards, the recommendation/device shelf and banner artwork in LG Home. Native navigation and the app row remain, with space above them. The third disables the reviewed services and on-demand native programs below. No app packages or LG firmware files are deleted. A full reboot removes the layout/service trial unless their startup hooks are subsequently installed. The existing preload-cleanup startup repair remains independent.

Check HDMI2 video, sound, Game Optimizer, Settings, volume, the remote, standby/wake and Xbox CEC. Open the dashboard's LG Home escape to inspect the stock layout. Service verification can establish process/override state, but cannot validate picture, sound, CEC or visible layout.

```powershell
.\debloat-tv.ps1 -Action verify
.\lg-home-layout.ps1 -Action verify
```

Only after the TV works correctly, persist these changes:

```powershell
.\lg-home-layout.ps1 -Action install-startup
.\debloat-tv.ps1 -Action install-startup
```

After a full reboot, allow at least 75 seconds for the service worker, then run verify again. Boot workers run in the background and do not block the dashboard hook. The service worker sleeps 45 seconds before acting; its log is `/var/lib/lg-reviewed-debloat/startup.log`.

## Scope and checks

- Systemd units: car integration, camera activation, family care, buddy/phone connector, content miner, LG Channels dmost, diagnostics rdxd/remotediag, remote logger, service logger, uploader, voice input/conductor. Nudge is excluded following a failed stop/restart trial; promotional settings and layout cleanup remain.
- Native executable overrides: the exact observed voice pipeline, Alexa trigger, voice NLP/performer, sports alerts, iconnectivity and the native service executables. Binds `/dev/null` over their executable paths, then signals exact matching processes. Missing executables are skipped. Generic `node` processes are never killed.
- SDX is running as `/usr/sbin/sdx` despite having no systemd unit. Its executable hash and running process are checked before and after; it is excluded from all target sets. No SDX executable, LS2 definition, mask or setting is modified.
- Before mutation, every target unit definition must match the reviewed inventory. Live `RequiredBy`, `BoundBy` and `ConsistsOf` must be empty to avoid stop propagation. Reverse-dependency tree queries timed out for some units in the initial inventory; the direct stop-propagation properties did succeed and are rechecked live.
- Runtime masks under `/run/systemd/transient` prevent systemd reactivation. Native bind mounts prevent direct LS2 respawn for the targeted executable paths. Every change is journaled for rollback. Existing foreign overrides cause an error.
- Always Ready, tvdataexchanger, PAC runner, discovery/network services, SDX, Settings/SAM, compositor, input, audio, panel and OLED protection are preserved. The inventory's `acr` substring accidentally matched PAC runner; it is explicitly excluded. No claim of complete telemetry elimination is made: this targets observed optional components, not every network endpoint.
- Following the nudge failure, reboot and check the TV before retrying. Restore recognizes historical nudge masks/mounts only to remove them. Rollback queues starts without waiting and explicitly requires reboot/recovery checks. Apply failures retain the original exception even if rollback also fails. SSH reports now capture remote stderr as well as stdout.
- Family Care's observed systemd activation is masked; a generic Node runtime is not neutralized. No installed streaming apps are deleted; their background preloading is disabled by the existing cleanup. Alexa's observed trigger is blocked, but no unobserved account/integration state is altered.

The trial has not yet been executed by the agent on the TV. PowerShell syntax is checked locally. Python regression checks execute on the TV before service actions, covering SDX/core exclusions, precise process matches and dependency guards. Local Python runtime is unavailable. Visual layout and Home reload remain on-TV checks.

Compatibility update: the TV lacks Python's `xml` package. Layout transformation now uses four exact byte replacements guarded by the captured original SHA256, with no XML package dependency. The patch fragments were applied locally to the captured fixture; independent .NET XML parsing confirmed valid XML, absent target rows, unchanged app/navigation nodes, and preserved total page height. The TV self-test still runs before mounting anything.

## Restore

```powershell
.\debloat-tv.ps1 -Action restore
.\lg-home-layout.ps1 -Action restore
```

Then reboot normally to reinitialize on-demand services. Restore removes only owned masks, executable mounts and hooks and retains original-state files. Core application/HDMI routing remains unchanged. To additionally undo the older preload/tile/promotion cleanup, use its separate `.\hdmi-cleanup.ps1 -Action restore`.

## Source evidence

- [Glasshouse service catalog and transient masks](https://github.com/rorygallagher2024/glasshouse/blob/main/server/lib/services.js)
- [Own-your-glass optional feature targets](https://github.com/JulioFerrero/own-your-glass/blob/main/modules/debloat.sh)
- [Own-your-glass ACR/ad targets](https://github.com/JulioFerrero/own-your-glass/blob/main/modules/services.sh)
- [Glasshouse service dependency failures](https://rorygallagher2024.github.io/glasshouse/IMPLEMENTATION/#background-services-debloating-safety)

Catalog names are informed by those sources; actual units and executable paths come from this TV's captured inventory. No upstream installer or blanket blacklist is run.
