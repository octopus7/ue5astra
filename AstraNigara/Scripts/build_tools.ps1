[CmdletBinding()]
param([string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.7')
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$ProjectFile = Join-Path $ProjectRoot 'AstraNigara.uproject'
$BuildScript = Join-Path $EngineRoot 'Engine\Build\BatchFiles\Build.bat'
if (-not (Test-Path -LiteralPath $BuildScript)) { throw "UE build script not found: $BuildScript" }
& $BuildScript AstraNigaraEditor Win64 Development "-Project=$ProjectFile" -WaitMutex -NoHotReloadFromIDE
if ($LASTEXITCODE -ne 0) { throw "Editor tools build failed ($LASTEXITCODE)" }
