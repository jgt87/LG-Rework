# No Signal screen investigation

TV: OLED48C24LA, firmware 33.31.68 / SDK 10.3.1. Read-only inventory reviewed 2026-10-31.

## Observed on this TV

- `general.noSignalScreenSaver` currently returns `on`.
- HDMI1–4 launch the shared native executable `/usr/bin/com.webos.app.inputcommon`; their per-port folders mostly contain metadata, icons and splash images. A splash image is not established as the No Signal background.
- InputCommon contains readable QML presentation code under `/usr/palm/applications/com.webos.app.inputcommon/qml`.
- `Interfaces/ScreensaverInterfaces/NoSignalPhotoModel.qml` gates photo enablement on `systemProperties.noSignalScreenSaver` and No Signal state.
- `UserInterfaceLayer/Containers/BgViewLayer/Screensaver.qml` refers to the photo model and `noSignalGuideAreaVisible`; it creates the photo view.
- `PhotoSlide.qml`, `ScreensaverMainText.qml`, `ScreensaverSubText.qml` and `RandomMoveItem.qml` are present in that presentation directory.
- The separate `com.webos.app.screensaver` application is Flutter. Replacing that app is not established as replacing HDMI No Signal.

## Assessment

Hiding the gallery via its native setting is supported by the observed code. Text/guide visibility has a separate presentation path. Custom artwork/text is a plausible targeted QML override, but complete source and an on-TV trial are still required before claiming replacement works. Source files alone do not establish that a mounted modification will be read rather than a cached/embedded component.

The next read-only inspection captures the seven exact presentation files with SHA256. Run `inspect-no-signal.ps1` again to refresh `no-signal-inventory.json` with `presentation_sources`. It does not change settings, mount files, restart HDMI, or alter SDX.

Any later implementation should change presentation only, preserve No Signal auto-off/DPMS logic and signal recovery, keep originals, and provide an owned removable mount and rollback. No such replacement has been installed.

## Complete presentation-source findings

The second inventory captured the full components. No further discovery is needed to propose the initial image/text patch.

- `NoSignalPhotoModel.qml` builds the photo array in `setImgArray()` using `defaultList.concat(updateList)`. Its default gallery comes from `ScreensaverPhotoList.js`; downloaded gallery images are found under `/mnt/lg/appstore/preload/igallery/files/download` using attachedstoragemanager. A targeted replacement of the array assignment can supply local file URLs while retaining the existing model's enable/disable state and timers.
- `PhotoSlide.qml` reads `photoModel.imgArray` and `currentIdx`; `img.setSource()` assigns that array entry to a QML Image. Current fill mode is `Image.Stretch`, which means any prepared replacement should match the screen aspect ratio or explicitly change the fit mode. It includes an image-load error/recovery path that should remain intact.
- `Screensaver.qml` provides the full-screen photo view separately from its message boxes. Its background is black when the photo is not running. Photo-box visibility is gated by `guideAreaVisible` and the photo model state. Header/body bindings are distinct, so artwork and text can be changed separately.
- Message generation in `_setMessage()` handles several warning types, not only No Signal. A text override must be conditional on `currentKey === "noSignal"`; replacing shared Text components globally would also affect other input warnings.
- The normal moving text uses `RandomMoveItem`; leave its positioning behavior in place rather than introducing a bright stationary message.

Conclusion: custom local artwork and No Signal-specific message styling have concrete source-level patch points on this firmware. An owned bind mount is a plausible reversible deployment mechanism, as with the Home layout; it remains untested for these components. QML cache/loading behavior, file readability, image recovery, live HDMI return and CEC must be validated on the TV. This is not yet a claim of an installed/working custom screen.

The owner selected a plain black background. Prepared `no-signal-background.ps1` with apply/verify/restore actions using only the native persistent `general.noSignalScreenSaver=off` setting. No QML override or startup hook is needed for this choice. The original value is backed up before change; text/guide and auto-off settings are not modified. Execution and physical result are still pending. SDX remains untouched.
