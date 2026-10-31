param([ValidateSet('apply','verify','restore','install-startup')][string]$Action='verify')
$ErrorActionPreference='Stop'
$alexaTV='192.168.1.44'
& scp -O (Join-Path $PSScriptRoot 'alexa-tiles.py') "root@${alexaTV}:/tmp/lg-alexa-tiles.py"
if($LASTEXITCODE -ne 0){throw 'Upload failed; no Alexa cleanup executed.'}
& ssh "root@$alexaTV" "python3 /tmp/lg-alexa-tiles.py $Action" | Tee-Object -FilePath (Join-Path $PSScriptRoot "alexa-tiles-$Action.txt")
if($LASTEXITCODE -ne 0){throw "Alexa tile $Action failed; retain the report."}
