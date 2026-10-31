# LG HDMI Home
<!-- impeccable:product-schema 1 -->

## Platform
web

## Stack
Packaged webOS TV web app. Implementation choice: local HTML, CSS and JavaScript with no runtime dependencies, suitable for the user's lightweight TV dashboard request.

## Users
One owner using a rooted LG OLED48C24LA primarily as an Xbox Series X display on HDMI2. The owner now also requests direct launch tiles for the installed Apple TV, YouTube and Browser apps.

## Product Purpose
Select HDMI inputs quickly from a clean local dashboard. The owner now requests dashboard-first startup, replacing the earlier Xbox-first preference. HDMI-CEC may switch to the Xbox when it starts, and the dashboard must not reclaim focus from an HDMI source.

## Operating Context
Firmware 33.31.68, webOS SDK 10.3.1, IP 192.168.1.44, Homebrew Channel root status OK. The TV has a separate reversible debloat configuration. Direct agent-shell TV networking is blocked; installation is performed by a user-run PowerShell/SSH launcher.

## Capabilities and Constraints
HDMI1-4, Apple TV, YouTube, Browser, TV Settings, Game Optimizer, an escape to LG Home; Magic Remote and D-pad support. Dashboard assets remain local; launching an app may use that app's normal internet access. Do not change picture, audio, HDMI-CEC, OLED care or the established debloat backup. Dashboard-first startup and system-Home routing must be reversible. HDMI No Signal customization is an additional request; a supported plain-black setting is documented separately.

## Product Principles
One click to the Xbox; predictable focus; minimal background work; preserve stock recovery paths. Never fabricate HDMI signal/connection status.
