$ErrorActionPreference='Stop'
$debloatTV=(& (Join-Path $PSScriptRoot 'tv-address.ps1'))
& scp -O (Join-Path $PSScriptRoot 'inspect-debloat.py') "root@${debloatTV}:/tmp/lg-inspect-debloat.py"
if($LASTEXITCODE -ne 0){throw 'Inventory upload failed; no inspection executed.'}
& ssh "root@$debloatTV" 'python3 -I /tmp/lg-inspect-debloat.py' | & (Join-Path $PSScriptRoot 'tv-report.ps1') -Path (Join-Path $PSScriptRoot 'debloat-inventory.json')
if($LASTEXITCODE -ne 0){throw 'Read-only inventory failed. Retain output for diagnosis.'}
Write-Host 'Read-only report saved: debloat-inventory.json. No services or settings changed. SDX is protected.'
