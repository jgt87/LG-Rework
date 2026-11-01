param([ValidateSet('apply','verify','restore','install-startup','self-test')][string]$Action='verify')
$ErrorActionPreference='Stop'
$debloatTV=(& (Join-Path $PSScriptRoot 'tv-address.ps1'))
& scp -O (Join-Path $PSScriptRoot 'debloat-tv.py') (Join-Path $PSScriptRoot 'debloat-reviewed-units.json') (Join-Path $PSScriptRoot 'profiles\lg-reviewed-profiles.json') "root@${debloatTV}:/tmp/"
if($LASTEXITCODE -ne 0){throw 'Upload failed. No service cleanup executed.'}
& ssh "root@$debloatTV" "python3 /tmp/debloat-tv.py $Action --review /tmp/debloat-reviewed-units.json 2>&1" | Tee-Object -FilePath (Join-Path $PSScriptRoot "debloat-tv-$Action.txt")
$debloatExit=$LASTEXITCODE
if($Action -in @('apply','install-startup','restore')){
    & scp -O "root@${debloatTV}:/var/lib/lg-reviewed-debloat/original-state.json" (Join-Path $PSScriptRoot 'debloat-tv-original-state.json')
    if($LASTEXITCODE -ne 0){Write-Warning 'Local backup copy failed; retain /var/lib/lg-reviewed-debloat/original-state.json on TV.'}
}
if($debloatExit -ne 0){throw "Service cleanup $Action failed; retain debloat-tv-$Action.txt. Do not install startup yet."}
