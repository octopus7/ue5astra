param(
    [string]$PackageRoot,
    [string]$ValidationRoot,
    [ValidateRange(1, 600)][int]$TimeoutSeconds = 600
)
$ErrorActionPreference = 'Stop'
$astraValidationRepo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $PackageRoot) { $PackageRoot = Join-Path $astraValidationRepo 'Builds\AstraLevelTest_Win64\Windows' }
if (-not $ValidationRoot) { $ValidationRoot = Join-Path $astraValidationRepo 'Builds\Validation' }
$PackageRoot = [IO.Path]::GetFullPath($PackageRoot)
$ValidationRoot = [IO.Path]::GetFullPath($ValidationRoot)
$astraValidationExe = Join-Path $PackageRoot 'AstraLevelTest\Binaries\Win64\AstraLevelTest-Win64-Shipping.exe'
$astraValidationSummaryPath = Join-Path $ValidationRoot 'WindowsPackageValidation.json'
New-Item -ItemType Directory -Path $ValidationRoot -Force | Out-Null

function Assert-AstraFreshFile {
    param([string]$Path, [datetime]$StartedUtc)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Missing output: $Path" }
    $astraFile = Get-Item -LiteralPath $Path
    if ($astraFile.LastWriteTimeUtc -lt $StartedUtc) { throw "Stale output: $Path" }
    if ($astraFile.Length -eq 0) { throw "Empty output: $Path" }
}

function Assert-AstraPng {
    param([string]$Path, [datetime]$StartedUtc, [int]$Width, [int]$Height)
    Assert-AstraFreshFile $Path $StartedUtc
    $astraStream = [IO.File]::OpenRead($Path)
    try {
        $astraHeader = New-Object byte[] 24
        if ($astraStream.Read($astraHeader, 0, 24) -ne 24) { throw "Truncated PNG: $Path" }
    }
    finally { $astraStream.Dispose() }
    if ([BitConverter]::ToString($astraHeader, 0, 8) -ne '89-50-4E-47-0D-0A-1A-0A' -or
        [Text.Encoding]::ASCII.GetString($astraHeader, 12, 4) -ne 'IHDR') { throw "Invalid PNG header: $Path" }
    $astraPngWidth = [long]$astraHeader[16] * 16777216 + [long]$astraHeader[17] * 65536 + [long]$astraHeader[18] * 256 + $astraHeader[19]
    $astraPngHeight = [long]$astraHeader[20] * 16777216 + [long]$astraHeader[21] * 65536 + [long]$astraHeader[22] * 256 + $astraHeader[23]
    if ($astraPngWidth -ne $Width -or $astraPngHeight -ne $Height) {
        throw "PNG size ${astraPngWidth}x${astraPngHeight}, expected ${Width}x${Height}: $Path"
    }
}

function Invoke-AstraPackageProcess {
    param([string]$TestSwitch, [string]$Profile, [int]$Width, [int]$Height, [string]$UserDirectory)
    New-Item -ItemType Directory -Path $UserDirectory -Force | Out-Null
    # Forward slashes avoid an escaped closing quote after a trailing Windows separator.
    $astraUserArgument = $UserDirectory.Replace('\', '/').TrimEnd('/') + '/'
    $astraArguments = @(
        $TestSwitch, "-AstraRenderProfile=$Profile", '-windowed', '-ForceRes',
        "-ResX=$Width", "-ResY=$Height", '-NoVSync', '-unattended', '-nosplash',
        ('-UserDir="' + $astraUserArgument + '"')
    )
    $astraStarted = [datetime]::UtcNow
    Write-Host "Validating $TestSwitch / $Profile (${Width}x${Height})"
    $astraProcess = Start-Process -FilePath $astraValidationExe -ArgumentList $astraArguments -WorkingDirectory $PackageRoot -WindowStyle Hidden -PassThru
    try {
        $astraDeadline = $astraStarted.AddSeconds($TimeoutSeconds)
        while (-not $astraProcess.WaitForExit(1000)) {
            if ([datetime]::UtcNow -ge $astraDeadline) {
                # The handle belongs only to this invocation's directly launched game.
                $astraProcess.Kill()
                $astraProcess.WaitForExit()
                throw "$TestSwitch / $Profile exceeded $TimeoutSeconds seconds."
            }
        }
        $astraProcess.Refresh()
        return [pscustomobject]@{
            startedUtc = $astraStarted
            completedUtc = [datetime]::UtcNow
            exitCode = $astraProcess.ExitCode
            processId = $astraProcess.Id
        }
    }
    finally { $astraProcess.Dispose() }
}

$astraValidationSummary = [ordered]@{
    passed = $false
    startedUtc = [datetime]::UtcNow.ToString('o')
    completedUtc = $null
    packageRoot = $PackageRoot
    executable = $astraValidationExe
    profiles = @()
    demo = $null
    failure = $null
}
try {
    if (-not (Test-Path -LiteralPath $astraValidationExe -PathType Leaf)) { throw "Shipping executable missing: $astraValidationExe" }
    $astraProfiles = @(
        @{ name = 'DLSS4K'; width = 3840; height = 2160; internalWidth = 1920; internalHeight = 1080; dlss = $true },
        @{ name = 'Native1080'; width = 1920; height = 1080; internalWidth = 1920; internalHeight = 1080; dlss = $false },
        @{ name = 'Native4K'; width = 3840; height = 2160; internalWidth = 3840; internalHeight = 2160; dlss = $false }
    )
    # GPU tests intentionally run one after another, never in parallel.
    foreach ($astraProfile in $astraProfiles) {
        $astraCaseDirectory = Join-Path $ValidationRoot $astraProfile.name
        $astraCase = [ordered]@{ requestedProfile = $astraProfile.name; passed = $false; process = $null; report = $null; screenshot = $null; result = $null; failure = $null }
        try {
            $astraRun = Invoke-AstraPackageProcess '-AstraGraphicsTest' $astraProfile.name $astraProfile.width $astraProfile.height $astraCaseDirectory
            $astraCase.process = $astraRun
            $astraCase.report = Join-Path $astraCaseDirectory 'Saved\GraphicsValidation.json'
            $astraCase.screenshot = Join-Path $astraCaseDirectory 'Saved\GraphicsValidation.png'
            Assert-AstraFreshFile $astraCase.report $astraRun.startedUtc
            $astraGraphics = Get-Content -LiteralPath $astraCase.report -Raw | ConvertFrom-Json
            $astraCase.result = $astraGraphics
            if ($astraRun.exitCode -ne 0) { throw "Graphics process exited with $($astraRun.exitCode)." }
            if ($astraGraphics.passed -ne $true) { throw "Graphics validation failed: $($astraGraphics.failure)" }
            if ($astraGraphics.requestedProfile -cne $astraProfile.name -or $astraGraphics.actualProfile -cne $astraProfile.name) {
                throw "Profile mismatch or fallback: requested=$($astraGraphics.requestedProfile), actual=$($astraGraphics.actualProfile), reason=$($astraGraphics.fallbackReason)"
            }
            if ($astraGraphics.actualOutputWidth -ne $astraProfile.width -or $astraGraphics.actualOutputHeight -ne $astraProfile.height -or
                $astraGraphics.actualInternalWidth -ne $astraProfile.internalWidth -or $astraGraphics.actualInternalHeight -ne $astraProfile.internalHeight) {
                throw 'Actual output or internal render resolution did not match the requested profile.'
            }
            if ($astraGraphics.actualDLSSEnabled -ne $astraProfile.dlss) { throw 'Actual DLSS activation did not match the requested profile.' }
            if ($astraGraphics.screenshotSaved -ne $true -or $astraGraphics.screenshotHasDetail -ne $true) { throw 'Graphics screenshot was not saved with visible detail.' }
            Assert-AstraPng $astraCase.screenshot $astraRun.startedUtc $astraProfile.width $astraProfile.height
            $astraCase.passed = $true
        }
        catch { $astraCase.failure = $_.Exception.Message; Write-Warning "$($astraProfile.name): $($astraCase.failure)" }
        $astraValidationSummary.profiles += [pscustomobject]$astraCase
    }

    $astraDemoDirectory = Join-Path $ValidationRoot 'Demo'
    $astraDemoCase = [ordered]@{ passed = $false; process = $null; sourceReport = $null; report = $null; screenshots = @(); result = $null; graphicsSettings = $null; failure = $null }
    try {
        $astraRun = Invoke-AstraPackageProcess '-AstraDemoTest' 'DLSS4K' 3840 2160 $astraDemoDirectory
        $astraDemoCase.process = $astraRun
        $astraDemoCandidatePaths = @(
            (Join-Path $PackageRoot 'AstraLevelTest\ArtSource\Previews\UE_DemoValidation.json'),
            (Join-Path $astraDemoDirectory 'ArtSource\Previews\UE_DemoValidation.json'),
            (Join-Path $astraDemoDirectory 'Saved\ArtSource\Previews\UE_DemoValidation.json')
        )
        # Some packaged platform file layers redirect ProjectDir writes under UserDir.
        $astraDemoCandidatePaths += @(Get-ChildItem -LiteralPath $astraDemoDirectory -Filter 'UE_DemoValidation.json' -File -Recurse | Select-Object -ExpandProperty FullName)
        $astraDemoCandidates = @($astraDemoCandidatePaths | Select-Object -Unique | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
            ForEach-Object { Get-Item -LiteralPath $_ } | Where-Object { $_.LastWriteTimeUtc -ge $astraRun.startedUtc } | Sort-Object LastWriteTimeUtc -Descending)
        if ($astraDemoCandidates.Count -eq 0) { throw 'No fresh demo report in the package project or Demo UserDir.' }
        $astraDemoSource = $astraDemoCandidates[0].FullName
        $astraDemoSourceDirectory = Split-Path -Parent $astraDemoSource
        $astraDemoCase.sourceReport = $astraDemoSource
        $astraDemoCollected = Join-Path $astraDemoDirectory 'Artifacts'
        New-Item -ItemType Directory -Path $astraDemoCollected -Force | Out-Null
        $astraDemoCase.report = Join-Path $astraDemoCollected 'UE_DemoValidation.json'
        Copy-Item -LiteralPath $astraDemoSource -Destination $astraDemoCase.report -Force
        $astraDemoResult = Get-Content -LiteralPath $astraDemoCase.report -Raw | ConvertFrom-Json
        $astraDemoCase.result = $astraDemoResult
        if ($astraRun.exitCode -ne 0) { throw "Demo process exited with $($astraRun.exitCode)." }
        if ($astraDemoResult.test -cne 'AstraDemoTest' -or $astraDemoResult.passed -ne $true -or $astraDemoResult.failed_checks -ne 0) { throw 'Demo validation reported failure.' }
        $astraShotNames = @('Clearing', 'Bridge', 'PinkHouse', 'Camp', 'Ruins', 'FishingDock', 'BrokenBridge')
        if (@($astraDemoResult.shots).Count -ne 7) { throw 'Demo did not report exactly seven shots.' }
        foreach ($astraShotName in $astraShotNames) {
            $astraShot = @($astraDemoResult.shots | Where-Object { $_.name -ceq $astraShotName })
            if ($astraShot.Count -ne 1 -or $astraShot[0].pass -ne $true -or $astraShot[0].completed -ne $true) { throw "Missing or failed demo shot: $astraShotName" }
            $astraShotSource = Join-Path $astraDemoSourceDirectory "UE_Demo_$astraShotName.png"
            Assert-AstraPng $astraShotSource $astraRun.startedUtc 3840 2160
            $astraShotTarget = Join-Path $astraDemoCollected "UE_Demo_$astraShotName.png"
            Copy-Item -LiteralPath $astraShotSource -Destination $astraShotTarget -Force
            $astraDemoCase.screenshots += $astraShotTarget
        }
        if (@($astraDemoResult.checks).Count -eq 0 -or @($astraDemoResult.checks | Where-Object { $_.pass -ne $true }).Count -ne 0) { throw 'Demo P toggle or restoration checks are missing or failed.' }
        if (@($astraDemoResult.post_demo_movement).Count -ne 4) { throw 'Demo did not report all four WASD movement checks.' }
        foreach ($astraKey in @('W', 'A', 'S', 'D')) {
            $astraMovement = @($astraDemoResult.post_demo_movement | Where-Object { $_.key -ceq $astraKey })
            if ($astraMovement.Count -ne 1 -or $astraMovement[0].pass -ne $true) { throw "Post-demo movement failed: $astraKey" }
        }
        $astraDemoSettingsPath = Join-Path $astraDemoDirectory 'Saved\GraphicsSettings.json'
        Assert-AstraFreshFile $astraDemoSettingsPath $astraRun.startedUtc
        $astraDemoSettings = Get-Content -LiteralPath $astraDemoSettingsPath -Raw | ConvertFrom-Json
        $astraDemoCase.graphicsSettings = $astraDemoSettings
        if ($astraDemoSettings.actualProfile -cne 'DLSS4K' -or $astraDemoSettings.dlssEnabled -ne $true -or
            $astraDemoSettings.outputWidth -ne 3840 -or $astraDemoSettings.outputHeight -ne 2160) { throw 'Demo did not run with the DLSS4K profile.' }
        $astraDemoCase.passed = $true
    }
    catch { $astraDemoCase.failure = $_.Exception.Message; Write-Warning "Demo: $($astraDemoCase.failure)" }
    $astraValidationSummary.demo = [pscustomobject]$astraDemoCase
    $astraValidationSummary.passed = @($astraValidationSummary.profiles).Count -eq 3 -and
        @($astraValidationSummary.profiles | Where-Object { $_.passed -ne $true }).Count -eq 0 -and $astraDemoCase.passed
}
catch { $astraValidationSummary.failure = $_.Exception.Message }
finally {
    $astraValidationSummary.completedUtc = [datetime]::UtcNow.ToString('o')
    $astraSummaryJson = $astraValidationSummary | ConvertTo-Json -Depth 30
    [IO.File]::WriteAllText($astraValidationSummaryPath, $astraSummaryJson, [Text.UTF8Encoding]::new($false))
}
if (-not $astraValidationSummary.passed) { throw "Windows package validation failed. See $astraValidationSummaryPath" }
Write-Output "Windows package graphics profiles, P demo, restoration and WASD passed: $astraValidationSummaryPath"
