param([ValidateSet('apply','verify','restore','install-startup')][string]$Action='verify')
$ErrorActionPreference='Stop'
$alexaTV=(& (Join-Path $PSScriptRoot 'tv-address.ps1'))
& scp -O (Join-Path $PSScriptRoot 'alexa-tiles.py') (Join-Path $PSScriptRoot 'profiles\lg-reviewed-profiles.json') "root@${alexaTV}:/tmp/"
if($LASTEXITCODE -ne 0){throw 'Upload failed; no Alexa cleanup executed.'}
& ssh "root@$alexaTV" "python3 /tmp/alexa-tiles.py $Action" | Tee-Object -FilePath (Join-Path $PSScriptRoot "alexa-tiles-$Action.txt")
if($LASTEXITCODE -ne 0){throw "Alexa tile $Action failed; retain the report."}
