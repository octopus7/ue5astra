param([string[]]$Views = @('SPPond','SPElephant','SPGate','SPConstellation','SPLilies','SPOverview','SPElephantLater'))
$ErrorActionPreference = 'Stop'
$spProjectDir = Split-Path -Parent $PSScriptRoot
$spExe = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
foreach ($spView in $Views) {
    if ($spView -notmatch '^SP\w+$') { throw 'Star Pond review names must begin with SP.' }
    $spOutput = Join-Path $spProjectDir "ArtSource/Previews/UE_$spView.png"
    $spStarted = Get-Date
    $spSeconds = if ($spView -eq 'SPElephantLater') { 17 } else { 13 }
    $spArgs = @((Join-Path $spProjectDir 'AstraLevelTest.uproject'), '/Game/Astra/Maps/L_AstraStarPond',
        '-game', "-AstraReview=$spView", "-AstraReviewCaptureSeconds=$spSeconds", '-AstraRenderProfile=Native1080',
        '-windowed', '-RenderOffscreen', '-ForceRes', '-ResX=1600', '-ResY=1000', '-NoVSync', '-unattended',
        '-ini:Engine:[ConsoleVariables]:r.NGX.Enable=0', "-abslog=$spProjectDir\Saved\Review_$spView.log")
    $spProcess = Start-Process -FilePath $spExe -ArgumentList $spArgs -WindowStyle Hidden -PassThru
    $spProcess.WaitForExit()
    if ($spProcess.ExitCode -ne 0) { throw "$spView failed; see Saved/Review_$spView.log" }
    if (!(Test-Path -LiteralPath $spOutput) -or (Get-Item -LiteralPath $spOutput).LastWriteTime -lt $spStarted) {
        throw "$spView did not produce a fresh screenshot."
    }
    $spErrors = Select-String -LiteralPath "$spProjectDir\Saved\Review_$spView.log" -Pattern 'Failed to compile Material|LogShaderCompilers: Error|LogMaterial: Error|missing bUsedWith'
    if ($spErrors) { throw "$spView has shader errors; see Saved/Review_$spView.log" }
    Write-Output "$spView captured successfully."
}
