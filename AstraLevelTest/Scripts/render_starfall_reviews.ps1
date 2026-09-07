param([string[]]$Views = @('SFOverview','SFSpaceship','SFMushrooms','SFGlow','SFSpring','SFPuddles','SFBrokenTrees'))
$ErrorActionPreference = 'Stop'
$sfProjectDir = Split-Path -Parent $PSScriptRoot
$sfExe = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
foreach ($sfView in $Views) {
    if ($sfView -notmatch '^SF\w+$') { throw 'Starfall review names must begin with SF.' }
    $sfOutput = Join-Path $sfProjectDir "ArtSource/Previews/UE_$sfView.png"
    $sfStarted = Get-Date
    $sfHeight = if ($sfView -eq 'SFOverview') { 1300 } else { 1000 }
    $sfArgs = @((Join-Path $sfProjectDir 'AstraLevelTest.uproject'), '/Game/Astra/Maps/L_AstraStarfall',
        '-game', "-AstraReview=$sfView", '-AstraRenderProfile=Native1080', '-windowed',
        '-ResX=1600', "-ResY=$sfHeight", '-NoVSync', '-unattended', "-abslog=$sfProjectDir\Saved\Review_$sfView.log")
    $sfProcess = Start-Process -FilePath $sfExe -ArgumentList $sfArgs -WindowStyle Hidden -PassThru
    $sfProcess.WaitForExit()
    if ($sfProcess.ExitCode -ne 0) { throw "$sfView failed; see Saved/Review_$sfView.log" }
    if (!(Test-Path -LiteralPath $sfOutput) -or (Get-Item -LiteralPath $sfOutput).LastWriteTime -lt $sfStarted) {
        throw "$sfView did not produce a fresh screenshot."
    }
    $sfErrors = Select-String -LiteralPath "$sfProjectDir\Saved\Review_$sfView.log" -Pattern 'Failed to compile Material|LogShaderCompilers: Error|LogMaterial: Error|missing bUsedWith'
    if ($sfErrors) { throw "$sfView has shader errors; see Saved/Review_$sfView.log" }
    Write-Output "$sfView captured successfully."
}
