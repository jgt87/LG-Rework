param([ValidateRange(1,10)][int]$Samples=3,[ValidateRange(1,60)][int]$IntervalSeconds=10)
$ErrorActionPreference='Stop'
$memoryTV='192.168.1.44'
$memoryReport=Join-Path $PSScriptRoot 'tv-memory-report.json'
& scp -O (Join-Path $PSScriptRoot 'measure-tv-memory.py') "root@${memoryTV}:/tmp/lg-measure-memory.py"
if($LASTEXITCODE -ne 0){throw 'Memory script upload failed.'}
Write-Host "Taking $Samples read-only samples, $IntervalSeconds seconds apart. Leave the dashboard open."
$memoryOutput=& ssh "root@$memoryTV" "python3 /tmp/lg-measure-memory.py --samples $Samples --interval $IntervalSeconds"
if($LASTEXITCODE -ne 0){throw 'Memory measurement failed.'}
$memoryText=$memoryOutput -join "`n"
$memoryData=$memoryText | ConvertFrom-Json
$memoryText | Set-Content -LiteralPath $memoryReport -Encoding utf8
$memorySummary=foreach($memorySample in $memoryData.samples){
    [pscustomobject]@{
        UptimeSeconds=[Math]::Round($memorySample.uptime_seconds)
        Dashboard=$memorySample.dashboard_foreground
        TotalMiB=[Math]::Round($memorySample.meminfo_kib.MemTotal/1024,1)
        AvailableMiB=if($null -ne $memorySample.meminfo_kib.MemAvailable){[Math]::Round($memorySample.meminfo_kib.MemAvailable/1024,1)}else{'unknown'}
        UsedMiB=if($null -ne $memorySample.used_excluding_available_kib){[Math]::Round($memorySample.used_excluding_available_kib/1024,1)}else{'unknown'}
        SwapUsedMiB=[Math]::Round($memorySample.swap_used_kib/1024,1)
    }
}
$memorySummary | Format-Table -AutoSize
Write-Host "Report saved: $memoryReport"
Write-Host 'Dashboard=False means the foreground API did not identify our dashboard; inspect the saved reply before attributing usage.'
