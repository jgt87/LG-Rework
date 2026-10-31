param([ValidateSet('apply','verify','restore')][string]$Action='verify')
$ErrorActionPreference='Stop'
$backgroundTV='192.168.1.44'
& scp -O (Join-Path $PSScriptRoot 'no-signal-background.py') "root@${backgroundTV}:/tmp/lg-no-signal-background.py"
if($LASTEXITCODE -ne 0){throw 'Upload failed. No background setting changed.'}
& ssh "root@$backgroundTV" "python3 /tmp/lg-no-signal-background.py $Action 2>&1" | Tee-Object -FilePath (Join-Path $PSScriptRoot "no-signal-background-$Action.txt")
$backgroundExit=$LASTEXITCODE
if($Action -in @('apply','restore')){
    & scp -O "root@${backgroundTV}:/var/lib/lg-no-signal-background/original-state.json" (Join-Path $PSScriptRoot 'no-signal-background-original-state.json')
    if($LASTEXITCODE -ne 0){Write-Warning 'Local backup copy failed; retain the original-state file on the TV.'}
}
if($backgroundExit -ne 0){throw "No Signal background $Action failed; retain the report."}
