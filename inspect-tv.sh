#!/bin/sh
# Read-only inventory for OLED48C24LA, firmware 33.31.68 / webOS 10.3.1.
# Does not change settings, apps, preloads, services, or boot hooks.
set -u
section() { printf '\n=== %s ===\n' "$1"; }
section 'Root identity'
id
section 'Memory'
sed -n '/^MemTotal:/p; /^MemAvailable:/p' /proc/meminfo
section 'System version'
luna-send -w 5000 -n 1 luna://com.webos.service.tv.systemproperty/getSystemInfo '{"keys":["modelName","firmwareVersion","sdkVersion","boardType","otaId"]}' 2>&1
section 'Regional block lists (all candidates; no automatic region selection)'
for f in /var/preferences/com.webos.applicationManager/blockedSystemAppList/*.json; do
    [ -f "$f" ] || continue
    printf '\n%s\n' "$f"
    cat "$f"
done
section 'Current preload policy'
luna-send -w 5000 -n 1 luna://com.webos.service.preloadmanager/getPreloadPolicy '{}' 2>&1
section 'Persistent preload configuration'
if [ -f /var/preferences/webos-preload-manager-conf.json ]; then
    cat /var/preferences/webos-preload-manager-conf.json
fi
section 'Relevant current settings'
for pair in general:homePromotion general:homeAutoLaunch general:quickStartMode general:sportsAlarm option:livePromotion option:webOSPromotionVideo option:promotionStreamer option:livePlus other:contentRecommendation; do
    category=${pair%%:*}
    key=${pair#*:}
    printf '\n%s\n' "$pair"
    luna-send -w 5000 -n 1 luna://com.webos.settingsservice/getSystemSettings "{\"category\":\"$category\",\"keys\":[\"$key\"]}" 2>&1
done
section 'Installed app identifiers and titles'
for base in /media/system/apps/usr/palm/applications /usr/palm/applications /mnt/otncabi/usr/palm/applications /mnt/otycabi/usr/palm/applications /media/cryptofs/apps/usr/palm/applications /media/developer/apps/usr/palm/applications; do
    [ -d "$base" ] || continue
    for dir in "$base"/*; do
        [ -f "$dir/appinfo.json" ] || continue
        printf '\n%s\n' "$dir"
        sed -n 's/.*"title"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/title: \1/p' "$dir/appinfo.json"
    done
done
section 'Inventory complete; no TV settings were changed'
