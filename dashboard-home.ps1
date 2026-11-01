param([ValidateSet('enable','status','disable','uninstall','stock-home','self-test')][string]$Action='status')
$ErrorActionPreference='Stop'
$homeTV=(& (Join-Path $PSScriptRoot 'tv-address.ps1'))
$homeScript=Join-Path $PSScriptRoot 'dashboard\home-router.py'
& scp -O $homeScript (Join-Path $PSScriptRoot 'profiles\lg-reviewed-profiles.json') "root@${homeTV}:/tmp/"
if($LASTEXITCODE -ne 0){throw 'Router upload failed. No TV command executed.'}
$homeCommand=if($Action -eq 'enable'){'install'}else{$Action}
$homeRemote="python3 /tmp/home-router.py self-test && python3 /tmp/home-router.py $homeCommand 2>&1"
& ssh "root@$homeTV" $homeRemote | Tee-Object -FilePath (Join-Path $PSScriptRoot "dashboard-home-$Action.txt")
$homeExit=$LASTEXITCODE
if($Action -in @('enable','uninstall')){
    & scp -O "root@${homeTV}:/var/lib/lg-hdmi-home-router/original-state.json" (Join-Path $PSScriptRoot 'dashboard-home-original-state.json')
    if($LASTEXITCODE -ne 0){Write-Warning 'Could not copy the original startup setting backup; retain the TV backup.'}
}
if($homeExit -ne 0){throw "Home routing $Action failed. Keep the report before retrying."}
