param([int]$ImportProcessId = 0)
$ErrorActionPreference = 'Stop'
$spProjectDir = Split-Path -Parent $PSScriptRoot
$spExe = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
function Invoke-StarPondCheck([string[]]$Arguments, [string]$Report) {
    $spStarted = Get-Date
    $spProcess = Start-Process -FilePath $spExe -ArgumentList $Arguments -WindowStyle Hidden -PassThru
    $spProcess.WaitForExit()
    if ($spProcess.ExitCode -ne 0) { throw "Unreal validation exited with $($spProcess.ExitCode): $Report" }
    $spReportPath = Join-Path $spProjectDir "ArtSource/Previews/$Report"
    if (!(Test-Path -LiteralPath $spReportPath) -or (Get-Item -LiteralPath $spReportPath).LastWriteTime -lt $spStarted) {
        throw "Validation did not produce a fresh report: $Report"
    }
    $spResult = Get-Content -Raw -LiteralPath $spReportPath | ConvertFrom-Json
    if (!$spResult.passed) { throw "Validation failed: $Report ($($spResult.failed_checks))" }
    return $spResult
}
if ($ImportProcessId -gt 0 -and (Get-Process -Id $ImportProcessId -ErrorAction SilentlyContinue)) {
    Wait-Process -Id $ImportProcessId
}
$spImport = Get-Content -Raw (Join-Path $spProjectDir 'ArtSource/Previews/UE_StarPondImportValidation.json') | ConvertFrom-Json
if (!$spImport.passed) { throw "Import failed: $($spImport.error)" }
$spArgs = @((Join-Path $spProjectDir 'AstraLevelTest.uproject'), '/Engine/Maps/Entry',
    "-ExecutePythonScript=$spProjectDir/Scripts/validate_starpond_level.py", '-unattended', '-nosplash', '-nosound',
    '-NoLiveCoding', '-RenderOffscreen', '-ini:Engine:[ConsoleVariables]:r.NGX.Enable=0',
    "-abslog=$spProjectDir/Saved/StarPondValidation.log")
$spValidation = Invoke-StarPondCheck $spArgs 'UE_StarPondValidation.json'
Write-Output "Saved-map validation passed ($($spValidation.check_count) checks)."
$spArgs = @((Join-Path $spProjectDir 'AstraLevelTest.uproject'), '/Game/Astra/Maps/L_AstraStarPond',
    '-game', '-AstraStarPondTest', '-AstraRenderProfile=Native1080', '-windowed', '-ResX=1280', '-ResY=800',
    '-NoVSync', '-unattended', '-RenderOffscreen', '-ini:Engine:[ConsoleVariables]:r.NGX.Enable=0',
    "-abslog=$spProjectDir/Saved/StarPondRuntime.log")
$spRuntime = Invoke-StarPondCheck $spArgs 'UE_StarPondRuntimeValidation.json'
Write-Output 'Actual WASD, observatory, shoreline collision and skeletal idle test passed.'
$spArgs = @((Join-Path $spProjectDir 'AstraLevelTest.uproject'), '/Game/Astra/Maps/L_AstraStarPond',
    '-game', '-AstraDemoTest', '-AstraRenderProfile=Native1080', '-windowed', '-ResX=1280', '-ResY=800',
    '-NoVSync', '-unattended', '-RenderOffscreen', '-ini:Engine:[ConsoleVariables]:r.NGX.Enable=0',
    "-abslog=$spProjectDir/Saved/StarPondDemoValidation.log")
$spDemo = Invoke-StarPondCheck $spArgs 'UE_SPDemoValidation.json'
Write-Output "P demo, seven routes and restored WASD passed ($($spDemo.elapsed_world_seconds) world seconds)."
& (Join-Path $PSScriptRoot 'render_starpond_reviews.ps1')
