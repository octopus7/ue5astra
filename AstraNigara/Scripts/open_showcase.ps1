[CmdletBinding()]
param(
    [string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.7',
    [switch]$RebuildAssets
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$ProjectFile = Join-Path $ProjectRoot 'AstraNigara.uproject'
$Editor = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$SessionLog = Join-Path $ProjectRoot ('Saved\Logs\AstraNigara_Bridge_{0}.log' -f [DateTime]::Now.ToString('yyyyMMdd_HHmmss_fff'))
if (-not (Test-Path -LiteralPath $Editor)) { throw "Unreal Editor not found: $Editor" }
$LaunchArguments = @(
    ('"{0}"' -f $ProjectFile),
    '/Game/Maps/L_SmallDestructionShowcase',
    '-d3d11', '-DDC=NoZenLocalFallback',
    ('-abslog="{0}"' -f $SessionLog),
    ('-LocalDataCachePath="{0}"' -f (Join-Path $ProjectRoot 'DerivedDataCache'))
)
if ($RebuildAssets) {
    $LaunchArguments += '-AstraKeepEditorOpen'
    $LaunchArguments += ('-ExecutePythonScript="{0}"' -f (Join-Path $PSScriptRoot 'build_small_destruction.py'))
}
# This is the visible interactive editor requested by the user.
Start-Process -FilePath $Editor -ArgumentList $LaunchArguments -PassThru | Select-Object Id, ProcessName
