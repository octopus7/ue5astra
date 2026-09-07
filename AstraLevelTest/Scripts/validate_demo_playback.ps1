param(
    [string]$Editor = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
)
$ErrorActionPreference = 'Stop'
$astraDemoProject = Split-Path -Parent $PSScriptRoot
$astraDemoLog = Join-Path $astraDemoProject 'Saved\DemoValidation.log'
$astraDemoReport = Join-Path $astraDemoProject 'ArtSource\Previews\UE_DemoValidation.json'
New-Item -ItemType Directory -Path (Join-Path $astraDemoProject 'Saved') -Force | Out-Null
$astraDemoStarted = Get-Date
$astraDemoArgs = @(
    ('"' + (Join-Path $astraDemoProject 'AstraLevelTest.uproject') + '"'),
    '/Game/Astra/Maps/L_AstraWoodland', '-game', '-AstraDemoTest',
    '-windowed', '-ResX=1600', '-ResY=900', '-NoVSync', '-unattended', '-nosplash',
    ('-abslog="' + $astraDemoLog + '"')
)
$astraDemoProcess = Start-Process -FilePath $Editor -ArgumentList $astraDemoArgs -WindowStyle Hidden -PassThru
$astraDemoDeadline = (Get-Date).AddMinutes(12)
while (-not $astraDemoProcess.WaitForExit(1000)) {
    if ((Get-Date) -gt $astraDemoDeadline) {
        # This is the process created by this script, never another open editor.
        $astraDemoProcess.Kill()
        throw "Demo validation exceeded 12 minutes. See $astraDemoLog"
    }
}
if ($astraDemoProcess.ExitCode -ne 0) { throw "Demo validation exited with $($astraDemoProcess.ExitCode). See $astraDemoLog" }
if (-not (Test-Path -LiteralPath $astraDemoReport)) { throw 'Demo validation did not produce a report.' }
if ((Get-Item -LiteralPath $astraDemoReport).LastWriteTime -lt $astraDemoStarted) { throw 'Demo validation report is stale.' }
$astraDemoResult = Get-Content -LiteralPath $astraDemoReport -Raw | ConvertFrom-Json
if (-not $astraDemoResult.passed) { throw "Demo validation failed. See $astraDemoReport" }
$astraDemoErrors = Select-String -LiteralPath $astraDemoLog -Pattern 'Fatal error:|Assertion failed:|Failed to compile Material|LogShaderCompilers: Error|LogMaterial: Error|missing bUsedWith'
if ($astraDemoErrors) { throw "Demo validation contains engine or shader errors. See $astraDemoLog" }
foreach ($astraDemoShot in @('Clearing','Bridge','PinkHouse','Camp','Ruins','FishingDock','BrokenBridge')) {
    $astraDemoImage = Join-Path $astraDemoProject "ArtSource\Previews\UE_Demo_$astraDemoShot.png"
    if (-not (Test-Path -LiteralPath $astraDemoImage) -or (Get-Item -LiteralPath $astraDemoImage).LastWriteTime -lt $astraDemoStarted) {
        throw "Missing or stale screenshot for $astraDemoShot"
    }
}
Write-Output "P toggle, seven shots, loop, restoration and WASD validation passed: $astraDemoReport"
