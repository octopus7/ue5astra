param([string[]]$Views = @('RBTower','RBBell','RBRoots','RBArch','RBCloister','RBOverview','RBTowerLater'))
$ErrorActionPreference = 'Stop'
$rbProjectDir = Split-Path -Parent $PSScriptRoot
$rbExe = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
foreach ($rbView in $Views) {
    if ($rbView -notin @('RBTower','RBBell','RBRoots','RBArch','RBCloister','RBOverview','RBTowerLater')) { throw 'Unknown Root Belltower review camera.' }
    $rbOutput = Join-Path $rbProjectDir "ArtSource/Previews/UE_$rbView.png"
    $rbStarted = Get-Date
    $rbSeconds = if ($rbView -eq 'RBTowerLater') { 17 } else { 13 }
    $rbArgs = @((Join-Path $rbProjectDir 'AstraLevelTest.uproject'), '/Game/Astra/Maps/L_AstraRootBelltower',
        '-game', "-AstraReview=$rbView", "-AstraReviewCaptureSeconds=$rbSeconds", '-AstraRenderProfile=Native1080',
        '-windowed', '-RenderOffscreen', '-ForceRes', '-ResX=1600', '-ResY=1000', '-NoVSync', '-unattended',
        '-ini:Engine:[ConsoleVariables]:r.NGX.Enable=0', "-abslog=$rbProjectDir\Saved\Review_$rbView.log")
    $rbProcess = Start-Process -FilePath $rbExe -ArgumentList $rbArgs -WindowStyle Hidden -PassThru
    $rbProcess.WaitForExit()
    if ($rbProcess.ExitCode -ne 0) { throw "$rbView failed; see Saved/Review_$rbView.log" }
    if (!(Test-Path -LiteralPath $rbOutput) -or (Get-Item -LiteralPath $rbOutput).LastWriteTime -lt $rbStarted) { throw "$rbView did not produce a fresh screenshot." }
    $rbErrors = Select-String -LiteralPath "$rbProjectDir\Saved\Review_$rbView.log" -Pattern 'Failed to compile Material|LogShaderCompilers: Error|LogMaterial: Error|missing bUsedWith'
    if ($rbErrors) { throw "$rbView has shader errors; see Saved/Review_$rbView.log" }
    Write-Output "$rbView captured successfully."
}
