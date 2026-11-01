param([ValidateSet('install','verify','launch')][string]$Action='install')
$ErrorActionPreference='Stop'
$dashboardRoot=Join-Path $PSScriptRoot 'dashboard'
$dashboardManifest=Get-Content -LiteralPath (Join-Path $dashboardRoot 'dist\build-manifest.json') -Raw | ConvertFrom-Json
$dashboardTV=(& (Join-Path $PSScriptRoot 'tv-address.ps1'))
$dashboardPackage=Join-Path (Join-Path $dashboardRoot 'dist') $dashboardManifest.ipk
if ((Get-FileHash -LiteralPath $dashboardPackage -Algorithm SHA256).Hash.ToLowerInvariant() -ne $dashboardManifest.sha256) { throw 'Local package hash does not match build manifest.' }
& scp -O (Join-Path $dashboardRoot 'dashboard-tv.py') (Join-Path $PSScriptRoot 'profiles\lg-reviewed-profiles.json') "root@${dashboardTV}:/tmp/"
if($LASTEXITCODE -ne 0){throw 'Could not upload installer. No TV command executed.'}
if($Action -eq 'install') {
    & scp -O $dashboardPackage "root@${dashboardTV}:/tmp/lg-hdmi-home.ipk"
    if($LASTEXITCODE -ne 0){throw 'Package upload failed. Installation not started.'}
}
$dashboardCommand="python3 /tmp/dashboard-tv.py $Action --version $($dashboardManifest.version) --ipk-sha $($dashboardManifest.sha256) --js-sha $($dashboardManifest.appjs_sha256)"
& ssh "root@$dashboardTV" $dashboardCommand | Tee-Object -FilePath (Join-Path $PSScriptRoot "dashboard-$Action.txt")
if($LASTEXITCODE -ne 0){throw "Dashboard $Action failed. Keep the report before retrying."}
if($Action -eq 'install'){Write-Host 'To open the dashboard: .\dashboard.ps1 -Action launch'}
