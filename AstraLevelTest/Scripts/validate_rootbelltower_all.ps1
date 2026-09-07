param([switch]$SkipReviews)
$ErrorActionPreference = 'Stop'
$rbProjectDir = Split-Path -Parent $PSScriptRoot
$rbExe = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
function Invoke-RootBelltowerCheck([string[]]$Arguments, [string]$Report) {
    $rbStarted = Get-Date
    $rbProcess = Start-Process -FilePath $rbExe -ArgumentList $Arguments -WindowStyle Hidden -PassThru
    $rbProcess.WaitForExit()
    if ($rbProcess.ExitCode -ne 0) { throw "Unreal validation exited with $($rbProcess.ExitCode): $Report" }
    $rbReportPath = Join-Path $rbProjectDir "ArtSource/Previews/$Report"
    if (!(Test-Path -LiteralPath $rbReportPath) -or (Get-Item -LiteralPath $rbReportPath).LastWriteTime -lt $rbStarted) { throw "Validation did not produce a fresh report: $Report" }
    $rbResult = Get-Content -Raw -LiteralPath $rbReportPath | ConvertFrom-Json
    if (!$rbResult.passed) { throw "Validation failed: $Report ($($rbResult.failed_checks))" }
    return $rbResult
}
$rbImport = Get-Content -Raw (Join-Path $rbProjectDir 'ArtSource/Previews/UE_RootBelltowerImportValidation.json') | ConvertFrom-Json
if (!$rbImport.passed) { throw 'Root Belltower import must pass first.' }
$rbArgs = @((Join-Path $rbProjectDir 'AstraLevelTest.uproject'), '/Engine/Maps/Entry',
    "-ExecutePythonScript=$rbProjectDir/Scripts/validate_rootbelltower_level.py", '-unattended', '-nosplash', '-nosound',
    '-NoLiveCoding', '-RenderOffscreen', '-ini:Engine:[ConsoleVariables]:r.NGX.Enable=0',
    "-abslog=$rbProjectDir/Saved/RootBelltowerSavedValidation.log")
$rbSaved = Invoke-RootBelltowerCheck $rbArgs 'UE_RootBelltowerSavedValidation.json'
Write-Output "Saved-map validation passed ($($rbSaved.check_count) checks)."
foreach ($rbTest in @(@('AstraRootBelltowerTest','UE_RootBelltowerRuntimeValidation.json','RootBelltowerRuntime'), @('AstraDemoTest','UE_RBDemoValidation.json','RootBelltowerDemoValidation'))) {
    $rbArgs = @((Join-Path $rbProjectDir 'AstraLevelTest.uproject'), '/Game/Astra/Maps/L_AstraRootBelltower',
        '-game', "-$($rbTest[0])", '-AstraRenderProfile=Native1080', '-windowed', '-ForceRes', '-ResX=1600', '-ResY=1000',
        '-NoVSync', '-unattended', '-RenderOffscreen', '-ini:Engine:[ConsoleVariables]:r.NGX.Enable=0',
        "-abslog=$rbProjectDir/Saved/$($rbTest[2]).log")
    $null = Invoke-RootBelltowerCheck $rbArgs $rbTest[1]
    Write-Output "$($rbTest[0]) passed."
}
if (!$SkipReviews) { & (Join-Path $PSScriptRoot 'render_rootbelltower_reviews.ps1') }
