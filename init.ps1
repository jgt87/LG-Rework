<#
.SYNOPSIS
Onboard a TV: connect, run the read-only compatibility check, and bundle the result for review.

.DESCRIPTION
  connect  Saves the TV address in device.local.json and checks root SSH, python3 and Homebrew.
  check    Runs init-tv.py on the TV (read only) and writes profiles/<model>_<firmware>/compatibility-report.json.
  bundle   Zips that report with a summary, ready to attach to a "Device profile" issue or pull request.

Nothing here changes the TV. Components only run on a TV listed in profiles/lg-reviewed-profiles.json,
and entries are only added there after a maintainer reviews the report. See profiles/README.md.
#>
param(
    [ValidateSet('connect', 'check', 'bundle')][string]$Action = 'connect',
    [string]$Address,
    [string]$ProfileId
)
$ErrorActionPreference = 'Stop'
$configFile = Join-Path $PSScriptRoot 'device.local.json'
$registryFile = Join-Path $PSScriptRoot 'profiles\lg-reviewed-profiles.json'
$utf8 = New-Object System.Text.UTF8Encoding $false

function Save-Text([string]$Path, [string]$Text) {
    [System.IO.File]::WriteAllText($Path, $Text, $utf8)
}

function Get-Registry {
    Get-Content -LiteralPath $registryFile -Raw | ConvertFrom-Json
}

function Find-Profile($Registry, $Tv) {
    $Registry.profiles | Where-Object {
        $_.modelName -eq $Tv.modelName -and $_.firmwareVersion -eq $Tv.firmwareVersion -and $_.sdkVersion -eq $Tv.sdkVersion
    } | Select-Object -First 1
}

function Show-Status($Tv) {
    $match = Find-Profile (Get-Registry) $Tv
    if ($match) {
        Write-Host "Reviewed profile found: $($match.id). Components allowed: $($match.components -join ', ')"
    } else {
        Write-Host 'This model/firmware has no reviewed profile yet, so every component will refuse to run.' -ForegroundColor Yellow
        Write-Host 'Next: .\init.ps1 -Action check'
    }
}

if ($Action -eq 'connect') {
    if (-not $Address) { $Address = Read-Host 'TV IP address or host name' }
    $Address = $Address.Trim()
    if ($Address -notmatch '^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$') { throw "Not a valid IP address or host name: $Address" }
    Save-Text $configFile ((@{ address = $Address } | ConvertTo-Json) + "`n")
    Write-Host "Saved $Address to device.local.json. All launchers now use this address."
    Write-Host 'Checking root SSH access. Enter the TV root password when asked (twice: upload, then check).'
    & scp -O (Join-Path $PSScriptRoot 'init-tv.py') "root@${Address}:/tmp/"
    if ($LASTEXITCODE -ne 0) { throw 'SSH upload failed. Enable SSH in Homebrew Channel settings and check the address.' }
    $output = & ssh "root@$Address" 'python3 /tmp/init-tv.py probe'
    if ($LASTEXITCODE -ne 0) { throw 'Connected, but python3 /tmp/init-tv.py did not run. The scripts need python3 on the TV.' }
    $probe = ($output -join "`n") | ConvertFrom-Json
    $tv = $probe.tv
    $report = @(
        "Address: $Address"
        "Root: $(if ($probe.uid -eq 0) { 'yes' } else { 'NO (uid ' + $probe.uid + ')' })"
        "python3: $($probe.python)"
        "Homebrew startup hooks: $(if ($probe.homebrewInit) { 'yes' } else { 'no' })"
        "TV: $($tv.modelName) / firmware $($tv.firmwareVersion) / SDK $($tv.sdkVersion)"
    )
    $report | Tee-Object -FilePath (Join-Path $PSScriptRoot 'init-connect.txt')
    if ($probe.uid -ne 0) { throw 'Connect as root. The scripts need the Homebrew Channel root shell.' }
    if (-not $tv) { throw "The TV did not report its model and firmware: $($probe.error)" }
    Show-Status $tv
    return
}

if ($Action -eq 'check') {
    $tvAddress = & (Join-Path $PSScriptRoot 'tv-address.ps1')
    $upload = @(
        (Join-Path $PSScriptRoot 'init-tv.py'),
        (Join-Path $PSScriptRoot 'debloat-tv.py'),
        (Join-Path $PSScriptRoot 'debloat-reviewed-units.json'),
        (Join-Path $PSScriptRoot 'hdmi-cleanup.py'),
        (Join-Path $PSScriptRoot 'alexa-tiles.py'),
        (Join-Path $PSScriptRoot 'lg-home-layout.py'),
        (Join-Path $PSScriptRoot 'no-signal-background.py'),
        (Join-Path $PSScriptRoot 'dashboard\home-router.py'),
        $registryFile
    )
    Write-Host "Uploading the read-only check to $tvAddress (nothing on the TV is changed)."
    & scp -O @upload "root@${tvAddress}:/tmp/"
    if ($LASTEXITCODE -ne 0) { throw 'Upload failed. Run .\init.ps1 -Action connect first.' }
    $output = & ssh "root@$tvAddress" 'python3 /tmp/init-tv.py'
    if ($LASTEXITCODE -ne 0) { throw 'The compatibility check failed on the TV; see the message above.' }
    $text = ($output -join "`n") + "`n"
    $result = $text | ConvertFrom-Json
    if ($result.profileId -notmatch '^[A-Za-z0-9._-]+$') { throw "Unexpected profile id: $($result.profileId)" }
    $folder = Join-Path $PSScriptRoot (Join-Path 'profiles' $result.profileId)
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    $reportFile = Join-Path $folder 'compatibility-report.json'
    Save-Text $reportFile $text
    Write-Host ''
    Write-Host "TV: $($result.tv.modelName) / firmware $($result.tv.firmwareVersion) / SDK $($result.tv.sdkVersion)"
    $rows = foreach ($name in $result.components.PSObject.Properties.Name) {
        $component = $result.components.$name
        $notMatching = @($component.checks | Where-Object { $_.status -ne 'matches' })
        [pscustomobject]@{
            Component = $name
            Status    = $component.status
            Reviewed  = if ($result.reviewedComponents -contains $name) { 'yes' } else { 'no' }
            Notes     = if ($notMatching.Count) { ($notMatching | ForEach-Object { $_.check }) -join '; ' } else { '' }
        }
    }
    $rows | Format-Table -AutoSize -Wrap | Out-String -Width 200 | Tee-Object -FilePath (Join-Path $PSScriptRoot 'init-check.txt')
    Write-Host "Report saved: profiles\$($result.profileId)\compatibility-report.json"
    Write-Host 'matches = everything this component touches looks the same as on the reviewed TV.'
    Write-Host 'differs/missing = a maintainer has to review it, and may need to change the script, before it can run.'
    Show-Status $result.tv
    if (-not (Find-Profile (Get-Registry) $result.tv)) { Write-Host 'Then: .\init.ps1 -Action bundle' }
    return
}

if ($Action -eq 'bundle') {
    if ($ProfileId) {
        $reportFile = Join-Path $PSScriptRoot "profiles\$ProfileId\compatibility-report.json"
    } else {
        $reportFile = Get-ChildItem -Path (Join-Path $PSScriptRoot 'profiles') -Filter 'compatibility-report.json' -Recurse |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
    }
    if (-not $reportFile -or -not (Test-Path -LiteralPath $reportFile)) { throw 'No compatibility report found. Run .\init.ps1 -Action check first.' }
    $text = Get-Content -LiteralPath $reportFile -Raw
    if ($text -match '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' -or $text -match '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}') {
        throw 'The report contains something that looks like a MAC or email address. Remove it before sharing.'
    }
    $result = $text | ConvertFrom-Json
    $id = $result.profileId
    # Read the timestamp as text: PowerShell 7 would convert it to local time.
    $checked = if ($text -match '"generatedUtc"\s*:\s*"([^"]+)"') { $Matches[1] } else { 'unknown' }
    $lines = @(
        "# Device profile: $id", '',
        '| Item | Value |', '|---|---|',
        "| Model | $($result.tv.modelName) |",
        "| Firmware | $($result.tv.firmwareVersion) |",
        "| webOS SDK | $($result.tv.sdkVersion) |",
        "| Checked (UTC) | $checked |", '',
        '| Component | Status |', '|---|---|'
    )
    foreach ($name in $result.components.PSObject.Properties.Name) { $lines += "| $name | $($result.components.$name.status) |" }
    $lines += @('', 'Physical checks I have done on this TV (edit before submitting):', '', '- [ ] Remote, volume, Settings and input switching work normally')
    $folder = Split-Path -Parent $reportFile
    $summaryFile = Join-Path $folder 'submission.md'
    Save-Text $summaryFile (($lines -join "`n") + "`n")
    $zip = Join-Path $PSScriptRoot "$id-profile-submission.zip"
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip }
    Compress-Archive -Path $reportFile, $summaryFile -DestinationPath $zip
    Write-Host "Bundle saved: $zip"
    Write-Host 'It holds only the compatibility report and summary: names, paths, hashes and statuses.'
    Write-Host 'Submit it for review: https://github.com/jgt87/LG-Rework/issues/new?template=device-profile.yml'
    Write-Host "Or open a pull request that adds profiles\$id\compatibility-report.json and submission.md."
}
