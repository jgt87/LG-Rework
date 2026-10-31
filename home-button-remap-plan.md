# Home button remap plan

## Intended behavior

- Power-on: open our HDMI Home dashboard. The owner explicitly changed the earlier Xbox-first preference to dashboard-first.
- Home button: open our HDMI Home dashboard (`com.local.hdmihome`).
- Dashboard Back button: return to HDMI2.
- Dashboard LG Home control: open the original LG interface.

The dashboard installer alone does not enable automatic dashboard startup or remap Home. The separate `dashboard-home.ps1 -Action enable` helper switches Home Auto Launch on and redirects system LG Home to our dashboard. Remapping the physical Home button is still handled by LG Input Hook. HDMI-CEC settings remain unchanged so the Xbox can take the input when it starts.

## Prerequisites

- Rooted LG OLED48C24LA with Homebrew Channel showing Root status OK.
- HDMI Home installed, with its HDMI2 and LG Home controls tested on the TV.
- SSH access retained as a recovery route.

## Remap Home

1. In Homebrew Channel, install **LG Input Hook** and open it once. The project documents that its setup persists across reboots after the first launch.
2. In LG Input Hook, view the appropriate input log for the remote and webOS version.
3. Press the physical **Home** button and note its detected ID. **773** is commonly reported; use the ID observed on this TV rather than assuming it.
4. Select **Add keybind** and enter the detected ID. If Home already has a custom mapping, record it before changing it.
5. If **Launch App** is available, choose **HDMI Home**, app ID `com.local.hdmihome`.
6. If the interface instead offers **Execute**, enter:

   ```sh
   luna-send -n 1 luna://com.webos.applicationManager/launch '{"id":"com.local.hdmihome"}'
   ```

7. Select **Save changes**. The project's instructions say changes normally apply automatically.

## Verify

1. View the Xbox on HDMI2, press Home, and confirm HDMI Home appears.
2. Select Xbox Series X and confirm it returns to HDMI2.
3. Open the dashboard again and select LG Home; confirm the original interface remains available.
4. Test volume, Settings and input switching.
5. Reboot through Homebrew Channel and verify that startup opens our dashboard. Start the Xbox and verify that its CEC input switch is not reversed by the helper. Confirm Home still opens the dashboard. Allow the input hook to initialize before testing Home.

If Home does not work, inspect Input Hook's logs and confirm the actual button ID, saved action and app ID before changing anything else. Compatibility depends on the installed Input Hook build and TV firmware.

## Undo

Open LG Input Hook, remove only the Home mapping created here (or restore the previously recorded mapping), then save changes. Test that Home opens LG's original interface again. Remove this mapping before uninstalling HDMI Home.

Do not overwrite the entire Input Hook configuration: other button mappings may exist. This plan leaves the debloat settings and their startup repair untouched.

## Sources

- [LG Input Hook catalogue and instructions](https://repo.webosbrew.org/apps/org.webosbrew.inputhook/)
- [LG Input Hook upstream project](https://github.com/Simon34545/lginputhook)
- [Hearth's Input Hook notes and reported Home code](https://github.com/rudra-avatar/Hearth#replacing-lg-home-rooted-tvs)

## Status

LG Input Hook is installed. On 2026-10-30, the physical Home button produced `uinput_code=773` in its Magic Remote log. Saved one binding: ID `773`, action `Launch App`, target `HDMI Home (com.local.hdmihome)`. The interface reported `Successfully saved to /config/keybinds.json`. Physical launch and reboot persistence still need testing. The dashboard-first helper is prepared but has not been installed by the agent.

## Making HDMI Home the main interface

These are separate behaviors:

1. **Physical Home button:** LG Input Hook launches `com.local.hdmihome` before the stock Home screen opens, if the hook works on this firmware.
2. **Power-on:** the owner requests dashboard-first behavior. The helper changes Home Auto Launch to on, with a saved original value, and redirects system Home events. After the reported No Signal startup gap, it also queues one dashboard launch from the initial Home/HDMI app at worker startup and wake; later foreground changes cancel it. This may cover an already-live HDMI source once. Deploy with `dashboard-home.ps1 -Action enable` and verify physically.
3. **LG Home opened by the system:** a foreground-event helper can redirect stock Home to the dashboard. This may briefly show LG Home. Such a helper needs a deliberate bypass for the dashboard's LG Home recovery control, must not take over HDMI while the Xbox is active, and needs start/stop/status/uninstall commands before installation.

Rooted projects also replace LG Home through a temporary bind mount and app-manager restart. That is a more intrusive approach with firmware-specific behavior; Hearth documents aspect-ratio and stock-Home escape limitations. It is not installed by this project.

The owner selected dashboard-first startup. Implementation: update the dashboard using `.\dashboard.ps1 -Action install`, then enable the helper using `.\dashboard-home.ps1 -Action enable`. Check it with `.\dashboard-home.ps1 -Action status`. Undo it with `.\dashboard-home.ps1 -Action uninstall`; remove the Input Hook mapping separately. Full instructions are in `dashboard/README.md`.
