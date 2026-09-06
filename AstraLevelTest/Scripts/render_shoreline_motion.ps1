param([string]$EditorExe = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$captures = @()
foreach ($seconds in @(13, 18)) {
    $log = Join-Path $projectRoot ('Saved\Shoreline\ShorelineMotionT' + $seconds + '.log')
    $arguments = @((Join-Path $projectRoot 'AstraLevelTest.uproject'),
        '/Game/Astra/Maps/L_AstraShorelinePolishModuleReview', '-game',
        '-AstraReview=ShorelinePolish', ('-AstraReviewCaptureSeconds=' + $seconds),
        '-windowed', '-ResX=1600', '-ResY=1000', '-NoVSync', '-unattended', '-nosplash', '-nosound', ('-abslog=' + $log))
    $process = Start-Process -FilePath $EditorExe -ArgumentList $arguments -WindowStyle Hidden -PassThru
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw ('Game capture failed with exit ' + $process.ExitCode) }
    $logText = Get-Content -LiteralPath $log -Raw
    if ($logText -match 'Error:|Failed to compile') { throw ('Game capture errors: ' + $log) }
    $timing = [regex]::Match($logText, 'ASTRA REVIEW capture ShorelinePolish at world ([\d.]+)s, validation ([\d.]+)s')
    if (-not $timing.Success) { throw 'No actual game-world capture time recorded' }
    $output = Join-Path $projectRoot ('ArtSource\Previews\UE_ShorelineMotionT' + $seconds + '.png')
    Copy-Item -LiteralPath (Join-Path $projectRoot 'ArtSource\Previews\UE_ShorelinePolish.png') -Destination $output -Force
    $captures += @{file=('ArtSource/Previews/UE_ShorelineMotionT' + $seconds + '.png');
        world_seconds=[double]::Parse($timing.Groups[1].Value, [cultureinfo]::InvariantCulture);
        validation_seconds=[double]::Parse($timing.Groups[2].Value, [cultureinfo]::InvariantCulture);
        exit_code=$process.ExitCode; shader_errors=0; sha256=(Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash}
}
Copy-Item -LiteralPath (Join-Path $projectRoot 'ArtSource\Previews\UE_ShorelineMotionT13.png') -Destination (Join-Path $projectRoot 'ArtSource\Previews\UE_ShorelinePolish.png') -Force
@{scope='Two actual UE game frames at recorded world times, saved orthographic camera'; captures=$captures; passed=$true} |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $projectRoot 'Saved\Shoreline\GameMotionCaptures.json') -Encoding UTF8
