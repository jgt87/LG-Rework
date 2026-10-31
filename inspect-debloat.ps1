$ErrorActionPreference='Stop'
$debloatTV='192.168.1.44'
& scp -O (Join-Path $PSScriptRoot 'inspect-debloat.py') "root@${debloatTV}:/tmp/lg-inspect-debloat.py"
if($LASTEXITCODE -ne 0){throw 'Inventory upload failed; no inspection executed.'}
& ssh "root@$debloatTV" 'python3 /tmp/lg-inspect-debloat.py' | Tee-Object -FilePath (Join-Path $PSScriptRoot 'debloat-inventory.json')
if($LASTEXITCODE -ne 0){throw 'Read-only inventory failed. Retain output for diagnosis.'}
Write-Host 'Read-only report saved: debloat-inventory.json. No services or settings changed. SDX is protected.'
