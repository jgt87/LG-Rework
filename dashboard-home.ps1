param([ValidateSet('enable','status','disable','uninstall','stock-home','self-test')][string]$Action='status')
$ErrorActionPreference='Stop'
$homeTV='192.168.1.44'
$homeScript=Join-Path $PSScriptRoot 'dashboard\home-router.py'
& scp -O $homeScript "root@${homeTV}:/tmp/lg-home-router.py"
if($LASTEXITCODE -ne 0){throw 'Router upload failed. No TV command executed.'}
$homeCommand=if($Action -eq 'enable'){'install'}else{$Action}
$homeRemote="python3 /tmp/lg-home-router.py self-test && python3 /tmp/lg-home-router.py $homeCommand 2>&1"
& ssh "root@$homeTV" $homeRemote | Tee-Object -FilePath (Join-Path $PSScriptRoot "dashboard-home-$Action.txt")
$homeExit=$LASTEXITCODE
if($Action -in @('enable','uninstall')){
    & scp -O "root@${homeTV}:/var/lib/lg-hdmi-home-router/original-state.json" (Join-Path $PSScriptRoot 'dashboard-home-original-state.json')
    if($LASTEXITCODE -ne 0){Write-Warning 'Could not copy the original startup setting backup; retain the TV backup.'}
}
if($homeExit -ne 0){throw "Home routing $Action failed. Keep the report before retrying."}
