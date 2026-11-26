# Shows pipeline output on the console and saves it to -Path as UTF-8 without a BOM.
# Used in place of Tee-Object: Windows PowerShell 5.1's Tee-Object writes UTF-16, which
# other tools and the agent misread. Use: & <remote command> | & (Join-Path $PSScriptRoot 'tv-report.ps1') -Path $report
# A native command's $LASTEXITCODE is kept: this script does not set it.
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(ValueFromPipeline = $true)]$InputObject
)
begin { $reportLines = New-Object System.Collections.Generic.List[string] }
process {
    $InputObject
    $reportLines.Add([string]$InputObject)
}
end {
    $reportText = ($reportLines -join "`n").TrimEnd("`r", "`n") + "`n"
    [IO.File]::WriteAllText($Path, $reportText, (New-Object Text.UTF8Encoding $false))
}
