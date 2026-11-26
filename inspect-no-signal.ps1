$ErrorActionPreference='Stop'
$signalTV=(& (Join-Path $PSScriptRoot 'tv-address.ps1'))
& scp -O (Join-Path $PSScriptRoot 'inspect-no-signal.py') "root@${signalTV}:/tmp/lg-inspect-no-signal.py"
if($LASTEXITCODE -ne 0){throw 'Inspection upload failed. No inspection executed.'}
& ssh "root@$signalTV" 'python3 -I /tmp/lg-inspect-no-signal.py' | & (Join-Path $PSScriptRoot 'tv-report.ps1') -Path (Join-Path $PSScriptRoot 'no-signal-inventory.json')
if($LASTEXITCODE -ne 0){throw 'Read-only No Signal inspection failed.'}
Write-Host 'Report saved: no-signal-inventory.json. No TV settings changed.'
