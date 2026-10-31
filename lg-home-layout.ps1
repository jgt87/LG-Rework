param([ValidateSet('apply','verify','restore','install-startup')][string]$Action='verify')
$ErrorActionPreference='Stop'
$layoutTV='192.168.1.44'
& scp -O (Join-Path $PSScriptRoot 'lg-home-layout.py') (Join-Path $PSScriptRoot 'lg-home-original.xml') "root@${layoutTV}:/tmp/"
if($LASTEXITCODE -ne 0){throw 'Upload failed; no layout action executed.'}
& ssh "root@$layoutTV" "python3 /tmp/lg-home-layout.py self-test --fixture /tmp/lg-home-original.xml && python3 /tmp/lg-home-layout.py $Action" | Tee-Object -FilePath (Join-Path $PSScriptRoot "lg-home-layout-$Action.txt")
if($LASTEXITCODE -ne 0){throw "Layout $Action failed. Retain the report; use restore if needed."}
