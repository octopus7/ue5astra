$ErrorActionPreference = 'Stop'
$spProjectDir = Split-Path -Parent $PSScriptRoot
$spExe = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
if (!(Test-Path -LiteralPath $spExe)) { throw 'Unreal Engine 5.7 is required.' }
$spArgs = @((Join-Path $spProjectDir 'AstraLevelTest.uproject'), '/Game/Astra/Maps/L_AstraStarPond',
    '-game', '-AstraRenderProfile=Native1080', '-windowed', '-ResX=1600', '-ResY=1000')
# This launcher is explicitly for the user's interactive play window.
Start-Process -FilePath $spExe -ArgumentList $spArgs
