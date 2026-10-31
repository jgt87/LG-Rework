$ErrorActionPreference = 'Stop'
$tvAddress = '192.168.1.44'
$report = Join-Path $PSScriptRoot 'home-layout-inventory.txt'
$remoteCommand = @'
echo '=== Home layout (read only) ==='
for f in /usr/palm/applications/com.webos.app.home/data/flutter_assets/assets/home.xml /usr/palm/applications/com.webos.app.home/appinfo.json; do
  echo "$f"
  if [ -f "$f" ]; then sha256sum "$f"; cat "$f"; else echo 'NOT FOUND'; fi
done
echo '=== Mount support ==='
cat /proc/filesystems
echo '=== Existing Home mounts ==='
awk '/com.webos.app.home|glasshouse-home|lg-home/ { print }' /proc/mounts
echo '=== End; no TV settings changed ==='
'@
& ssh "root@$tvAddress" $remoteCommand | Tee-Object -FilePath $report
if ($LASTEXITCODE -ne 0) { throw 'Read-only Home layout inventory failed.' }
Write-Host "Report saved: $report"
