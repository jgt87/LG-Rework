# Returns the TV address used by every launcher.
# init.ps1 -Action connect saves it in device.local.json (not committed). Without that file
# the launchers keep using the reference TV's address.
$tvConfigFile = Join-Path $PSScriptRoot 'device.local.json'
$tvResolved = '192.168.1.44'
if (Test-Path -LiteralPath $tvConfigFile) {
    $tvSaved = (Get-Content -LiteralPath $tvConfigFile -Raw | ConvertFrom-Json).address
    if ($tvSaved) { $tvResolved = [string]$tvSaved }
}
if ($tvResolved -notmatch '^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$') {
    throw "Invalid TV address '$tvResolved' in device.local.json. Run .\init.ps1 -Action connect again."
}
$tvResolved
