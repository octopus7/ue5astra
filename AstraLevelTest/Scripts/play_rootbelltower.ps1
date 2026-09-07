$ErrorActionPreference = 'Stop'
$rbProjectDir = Split-Path -Parent $PSScriptRoot
$rbExe = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
if (!(Test-Path -LiteralPath $rbExe)) { throw 'Unreal Engine 5.7 is required.' }
$rbArgs = @((Join-Path $rbProjectDir 'AstraLevelTest.uproject'), '/Game/Astra/Maps/L_AstraRootBelltower',
    '-game', '-AstraRenderProfile=Native1080', '-windowed', '-ResX=1600', '-ResY=1000')
# This launcher opens the user's interactive game window.
Start-Process -FilePath $rbExe -ArgumentList $rbArgs
