param(
    [ValidateSet('Build','Scene','Appearance','Test','Validate','Open','Play','Demo')][string]$Mode = 'Play',
    [string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.7'
)
$ErrorActionPreference = 'Stop'
$softProject = Split-Path -Parent $PSScriptRoot
$softProjectFile = Join-Path $softProject 'softbody.uproject'
$softSaved = Join-Path $softProject 'Saved'
New-Item -ItemType Directory -Path $softSaved,(Join-Path $softSaved 'ShaderWorkingDirectory') -Force | Out-Null
[Environment]::SetEnvironmentVariable('UE-LocalDataCachePath', (Join-Path $softProject 'DerivedDataCache'), 'Process')
if ($Mode -eq 'Build') {
    $softBuild = Join-Path $EngineRoot 'Engine\Build\BatchFiles\Build.bat'
    $softBuildArgs = @('SoftbodyEditor','Win64','Development',"`"-Project=$softProjectFile`"",'-WaitMutex','-NoHotReloadFromIDE','-NoUBA','-MaxParallelActions=4',"`"-Log=$softSaved\Build.log`"")
    $softProcess = Start-Process -FilePath $softBuild -ArgumentList $softBuildArgs -WorkingDirectory $softProject -WindowStyle Hidden -Wait -PassThru
    if ($softProcess.ExitCode -ne 0) { throw "Build failed ($($softProcess.ExitCode)). See $softSaved\Build.log" }
    Write-Output "Build succeeded. $softSaved\Build.log"
    return
}
$softEditor = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$softArgs = @("`"$softProjectFile`"",'-NoSplash','-NoSourceControl','-NoLiveCoding','-ddc=InstalledNoZenLocalFallback',"`"-ShaderWorkingDir=$softSaved\ShaderWorkingDirectory`"","`"-abslog=$softSaved\$Mode.log`"")
if ($Mode -in @('Scene','Appearance')) {
    $softEditor = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
    $softPythonScript = if ($Mode -eq 'Appearance') { 'update_appearance.py' } else { 'create_scene.py' }
    $softArgs += @('/Engine/Maps/Entry','-run=pythonscript',"`"-script=$PSScriptRoot\$softPythonScript`"",'-unattended','-nullrhi','-nosound')
} elseif ($Mode -eq 'Test') {
    $softEditor = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
    $softArgs += @('/Engine/Maps/Entry','-unattended','-nullrhi','-nosound','-ExecCmds="Automation RunTests Softbody.Solver"','-TestExit="Automation Test Queue Empty"',"`"-ReportExportPath=$softSaved\Automation`"")
} else {
    $softArgs += '/Game/Softbody/Maps/L_SoftbodyLab'
    if ($Mode -ne 'Open') { $softArgs += @('-game','-windowed','-ForceRes','-ResX=1600','-ResY=1000','-NoVSync') }
    if ($Mode -eq 'Validate') { $softArgs += @('-SoftbodyValidate','-unattended','-RenderOffscreen','-nosound','-UseFixedTimeStep','-FPS=60') }
    if ($Mode -eq 'Demo') { $softArgs += '-SoftbodyDemo' }
}
$softOptions = @{FilePath=$softEditor;ArgumentList=$softArgs;WorkingDirectory=$softProject;PassThru=$true;WindowStyle='Hidden'}
if ($Mode -in @('Open','Play','Demo')) { $softOptions.WindowStyle='Normal' }
$softStarted = Get-Date
$softProcess = Start-Process @softOptions
$softProcess.Id | Set-Content -LiteralPath (Join-Path $softSaved "$Mode.pid")
Write-Output "Started Softbody $Mode PID $($softProcess.Id)"
if ($Mode -in @('Open','Play','Demo')) { return }
$softProcess.WaitForExit()
$softProcess.Refresh()
if ($softProcess.ExitCode -ne 0) { throw "Unreal $Mode failed ($($softProcess.ExitCode)). See $softSaved\$Mode.log" }
$softErrors = @(Select-String -LiteralPath (Join-Path $softSaved "$Mode.log") -Pattern 'Failed to compile Material|Log(?:Python|Material|ShaderCompilers): Error:|Fatal error:|Assertion failed:')
if ($softErrors.Count -gt 0) { throw "Unreal $Mode reported rendering or script errors. See $softSaved\$Mode.log" }
if ($Mode -eq 'Scene') { $softReport = Join-Path $softSaved 'SceneBuild.json' }
if ($Mode -eq 'Appearance') { $softReport = Join-Path $softSaved 'AppearanceUpdate.json' }
if ($Mode -eq 'Validate') { $softReport = Join-Path $softSaved 'RuntimeValidation.json' }
if ($softReport) {
    if (-not (Test-Path -LiteralPath $softReport)) { throw "Missing $softReport" }
    if ((Get-Item -LiteralPath $softReport).LastWriteTime -lt $softStarted) { throw "Stale $softReport" }
    $softResult = Get-Content -LiteralPath $softReport -Raw | ConvertFrom-Json
    if ($softResult.passed -ne $true) { throw "Validation failed: $softReport" }
    if ($Mode -eq 'Scene') { Write-Output "Scene passed: $($softResult.actor_count) actors, 3 balls. $softReport" }
    else { Get-Content -LiteralPath $softReport }
}
if ($Mode -eq 'Test') {
    $softTestLog = Get-Content -LiteralPath (Join-Path $softSaved 'Test.log') -Raw
    if ($softTestLog -match 'Result=\{Fail\}' -or $softTestLog -notmatch 'Result=\{Success\}') { throw 'Automation tests failed or did not run.' }
    Select-String -LiteralPath (Join-Path $softSaved 'Test.log') -Pattern 'Test Completed.*Result='
}
