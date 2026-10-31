param([ValidateSet('plan','apply','verify','restore','diagnose','repair','self-test','install-startup','uninstall-startup')][string]$Action = 'plan')
$ErrorActionPreference = 'Stop'
$tvAddress = '192.168.1.44'
$cleanupScript = Join-Path $PSScriptRoot 'hdmi-cleanup.py'
$cleanupReport = Join-Path $PSScriptRoot "hdmi-cleanup-$Action.txt"
& scp -O $cleanupScript "root@${tvAddress}:/tmp/lg-hdmi-cleanup.py"
if ($LASTEXITCODE -ne 0) { throw 'Upload failed. No cleanup command was executed.' }
if ($Action -in @('apply','repair','restore','install-startup','uninstall-startup')) {
    $remoteCommand = "python3 /tmp/lg-hdmi-cleanup.py self-test && python3 /tmp/lg-hdmi-cleanup.py $Action"
} else {
    $remoteCommand = "python3 /tmp/lg-hdmi-cleanup.py $Action"
}
& ssh "root@$tvAddress" $remoteCommand | Tee-Object -FilePath $cleanupReport
$cleanupExitCode = $LASTEXITCODE
if ($Action -eq 'apply' -or $Action -eq 'restore') {
    $backupPath = Join-Path $PSScriptRoot 'hdmi-cleanup-original-state.json'
    & scp -O "root@${tvAddress}:/var/lib/lg-hdmi-cleanup/original-state.json" $backupPath
    if ($LASTEXITCODE -ne 0) { Write-Warning 'Could not copy the TV backup to this computer. Retain the backup on the TV.' }
}
if ($cleanupExitCode -ne 0) { throw "Cleanup $Action failed. Read $cleanupReport before retrying." }
Write-Host "Report saved: $cleanupReport"
