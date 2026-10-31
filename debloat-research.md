# LG Home cleanup and further debloating

Reviewed 2026-10-30 for OLED48C24LA, firmware 33.31.68 / SDK 10.3.1.

Owner authorized the four cleanup categories and explicitly requires `sdx` to remain enabled. SDX must never be stopped, masked, bind-neutralised, or indirectly stopped through a dependency operation. Inventory has now been reviewed; the implementation and trial/restore commands are in `DEBLOAT.md`. No service cleanup has yet been executed by the agent on the TV.

## Immediate layout cleanup

The owner's read-only inventory matches SHA256 `8f0bf119efe54285c44e15ed9f608da9f38dd94178e73ec5441f22df3d5aa9d7`.
`lg-home-layout.py` removes `qcardList` and `recommendedShelf`. These are the intended Quick Cards (including Sports) and recommendation/device-function shelf. Exact displayed contents must be checked on this TV. The app row and side navigation remain. Removed row height is assigned to the container to preserve vertical positioning. The banner item remains instantiated at zero width/height with focus disabled, hiding its artwork; the space above apps remains.

The implementation uses a bind mount over just `home.xml`, an adaptation of the community overlay approach. It has not yet been tested on the TV. LG's on-disk file remains untouched. Exact model/firmware and original-file checks reject unknown versions or conflicting mounts. Only the exact LG Home Flutter process is asked to reload; neither SAM nor other apps are restarted. The existing dashboard router may bring the custom dashboard forward; use its LG Home escape to inspect the result.

1. Trial: `.\lg-home-layout.ps1 -Action apply`
2. Open LG Home using the dashboard's LG Home button and check the missing rows, navigation and app launches.
3. If correct, persist: `.\lg-home-layout.ps1 -Action install-startup`
4. After a full reboot: `.\lg-home-layout.ps1 -Action verify`
5. Undo: `.\lg-home-layout.ps1 -Action restore`

A trial without the startup hook goes away on a full reboot. Restore removes the owned startup hook and mount; backups remain in `/var/lib/lg-home-layout`. It does not remove Input Hook bindings, change CEC, or alter the dashboard router/debloat scripts. Automatic checks run on the TV before every action. Local Python execution was unavailable; no on-TV result is claimed yet.

## What other projects do

| Layer | Examples | Assessment for this HDMI-only TV |
|---|---|---|
| Home layout | Quick Cards, recommendation/device shelf, promotional banner, side buttons | Start with the requested two rows; side navigation is useful for LG Home fallback. |
| Launcher | Hide LG Channels, Sports, Gallery, music, camera and guides | Existing cleanup already targets many of these. Hiding is cosmetic. |
| Preloads | Stop streaming apps, voice/browser and LG Channels preloading | Already largely covered by existing cleanup. |
| Optional services | Camera watcher, car integration, family care, voice/Alexa, phone connectivity | Candidates for a read-only installed/running/dependency inventory; not disabled here. |
| Telemetry/privacy | ACR, ad overlays, usage logger, crash reporting, endpoint blocking | Separate from layout; needs dependency review and functional checks. |

Do not import an entire service blacklist. Keep picture/audio/input/power paths, OLED care, Settings, root startup and remote handling intact. Own-your-glass documents that `sdx` removal broke Settings and withdrew a mistaken classification of `ss.gateway`. Discovery services such as Avahi can support casting/integration even if their names look unrelated. Claimed savings on other televisions are not measurements on this one.

## Sources

- [Glasshouse layout implementation](https://rorygallagher2024.github.io/glasshouse/IMPLEMENTATION/#home-screen-layout): version-specific layout overrides and restore.
- [Glasshouse TV research](https://rorygallagher2024.github.io/glasshouse/development/TV-RESEARCH/#home-screen-webos-10-and-11): Flutter asset layout and C2 evidence.
- [Own-your-glass](https://github.com/JulioFerrero/own-your-glass): optional feature and telemetry service targets.
- [Own-your-glass findings](https://github.com/JulioFerrero/own-your-glass/blob/main/docs/FINDINGS.md): dependency failures and corrections.
- [LG webOS dashboard](https://github.com/gnacho/lg-webos-dashboard): app hiding, preload and optional-service controls.
