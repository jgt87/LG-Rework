# Build validation: HDMI Home 1.0.4

Latest package/render: version 1.0.13 reduces configured source expansion from 160ms to 80ms with faster-start easing, and makes focus colors/borders immediate across controls. This avoids animated large-surface color repainting; it is not a measured physical-TV FPS/latency improvement. All 14 behavior/package tests pass. TV/narrow settled renders were captured with reduced motion disabled and returned no browser errors. Package built (496916 bytes); physical interaction timing still needs checking after installation.

Latest package/render: version 1.0.12 darkens the selected Xbox base and limits the lighter-green wash to the top-right corner. Resting styling and behavior are unchanged. TV/narrow screenshots and evidence refreshed without browser errors. Package built successfully (496920 bytes); physical TV installation remains pending.

Latest package/render: version 1.0.11 adds an explicit, higher-contrast light-to-dark gradient to the focused green Xbox tile. Resting styling and app behavior are unchanged. TV and narrow render/evidence refreshed without browser errors. Package built successfully (496894 bytes); TV installation is pending.

Latest package/render: version 1.0.10 uses Apple TV and YouTube brand path geometry as monochrome outline adaptations. TV and narrow renders/evidence are refreshed with no browser errors. Package rebuilt successfully (496872 bytes). Launch behavior is unchanged from the 14-test 1.0.9 baseline. Physical-TV installation remains pending.

Latest package/render: version 1.0.9 reduces the source grid to 51vh and adds Apple TV, YouTube and Browser tiles below it. Fourteen behavior/package tests pass, including app launch IDs, row navigation and hidden-port fallback. Current TV/narrow screenshots and evidence reflect 1.0.9; captures reported no browser errors, and the mechanical detector returned no findings. Package built successfully (496054 bytes). App availability is based on the saved inventory; on-TV launches for this version remain pending.

Independent finish review for the 1.0.9 extension: **ship**; material fixes: **none**. Preserve Xbox-first focus, understated app tiles, aligned header, visible white focus, shared launch feedback and OLED idle behavior.

Latest package/render: version 1.0.8 normalizes toolbar icon artwork sizing while retaining stroke weight. Both current TV and narrow renders were refreshed without browser errors. Package built successfully (495578 bytes); physical TV installation remains pending.

Latest render update: version 1.0.7 aligns the visible LG Home mark with the source grid's left edge. TV and narrow screenshots/evidence were refreshed; both captures reported no browser errors. Version 1.0.7 package built successfully; previous behavior tests remain unchanged. Physical-TV installation is pending.

Implemented the user's supplied `dashboard/review` design in the main TV application. Production HTML, CSS and app behavior were promoted from the reference; `ports.js` is included in both preview and IPK. The supplied Xbox PNG matches the reference asset byte-for-byte.

## Checks

- All 13 Node behavior/package tests passed: native launch allowlist and recovery, duplicate gating, busy labels, navigation, Back, error/timeout recovery, OLED wake consumption, visibility timers, local clock, port configuration/hidden navigation, and IPK structure/assets.
- JavaScript syntax checks passed. Mechanical design detector returned no findings.
- REA captured 1920x1080 TV and 390x844 narrow renders, locale en-GB/timezone Europe/Amsterdam, reduced motion. Neither capture reported console/page errors. Both owned Chrome processes were terminated after capture.
- Screenshot artifacts: `tv.png`, `tv-final.png`, `mobile.png`, `mobile-final.png`. Evidence metadata is in matching `*-evidence.json` files; screenshot base64 is omitted because PNGs are stored separately.
- TV evidence: `ev_58d7b37deb0bd39d8b4fe2d9159ca769ce7117f27db750dac35f4784fec6a680`.
- Narrow evidence: `ev_4171c105c502c2a21521851ced33886ddead0e1a66aaba80fa3f3eabc0b4203e`.
- Compared with `review/screenshots/review-default.png`. Reduced motion disables focus scaling in the capture; local date/time formatting varies. Source geometry, imagery, neutral controls, white ring and utility navigation match the approved source.

## Package

`dist/com.local.hdmihome_1.0.4_all.ipk` (495466 bytes).
SHA256: `17aa6dd9a66628662f915177227afc9ef52b7974810b6e61d3e215f4d927d12c`.

## Independent finish review

Disposition: **ship**.

| Material finding | Score |
|---|---|
| Stale design persistence | Resolved: DESIGN.md and .impeccable/design.json now match the implemented review design. |

No remaining material findings. Physical TV deployment and native behavior for version 1.0.4 remain pending.

## Installation

Version 1.0.4 is built locally, not yet installed on the physical TV. Install with `..\dashboard.ps1 -Action install` from this directory, or `.\dashboard.ps1 -Action install` from `C:\Files\Apps\LG`. Native TV operation must be checked after installation. This package does not alter existing root/debloat settings, Home-button bindings or startup hooks.

## Version 1.0.6 header update

Current `tv.png` / `tv-final.png` and `mobile.png` / `mobile-final.png` now show the 1.0.6 header. LG Home, Game Optimizer and TV Settings appear top left; date/time appears right. Header controls and clock inherit the same font, line-height and explicit height. Narrow layout wraps without clipping. Updated remote navigation is covered by all 13 passing behavior/package tests. The build package is `dist/com.local.hdmihome_1.0.6_all.ipk` (495484 bytes). No on-TV installation is claimed.

REA TV evidence: `ev_0232e598655cba35502a1db683aab014f365d3cebbfee610b442b739a449909f`. Narrow evidence: `ev_ce985c34b3e8a0e93ab1518f81c1b902ddffb7526155a90b6efc1ac7806a6187`. Captures returned no browser errors and terminated their owned processes. Mechanical layout detector returned no findings. Earlier 1.0.4 validation and finish-review verdict above are historical, not a separate finish-review claim for 1.0.6.
