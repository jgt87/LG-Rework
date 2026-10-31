$ErrorActionPreference = 'Stop'
$tvAddress = '192.168.1.44'
$inventoryScript = Join-Path $PSScriptRoot 'inspect-tv.sh'
$inventoryReport = Join-Path $PSScriptRoot 'tv-inventory.txt'
Write-Host 'Copying the read-only inventory script to the TV temporary directory.'
& scp -O $inventoryScript "root@${tvAddress}:/tmp/lg-inspect-tv.sh"
if ($LASTEXITCODE -ne 0) { throw 'Upload failed. Check Homebrew Channel SSH access.' }
Write-Host 'Reading TV configuration; no debloat changes will be applied.'
& ssh "root@$tvAddress" 'sh /tmp/lg-inspect-tv.sh' | Tee-Object -FilePath $inventoryReport
if ($LASTEXITCODE -ne 0) { throw 'Inventory failed; retain the report for diagnosis.' }
Write-Host "Saved report: $inventoryReport"
