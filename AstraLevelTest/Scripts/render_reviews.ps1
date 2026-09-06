param([string[]]$Views = @('Gameplay','Overview','Lake','Cabin','Puddle'))
$ErrorActionPreference = 'Stop'
$astraProjectDir = Split-Path -Parent $PSScriptRoot
$astraExe = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
foreach ($astraView in $Views) {
    $astraArgs = @((Join-Path $astraProjectDir 'AstraLevelTest.uproject'), '/Game/Astra/Maps/L_AstraWoodland', '-game', "-AstraReview=$astraView", '-windowed', '-ResX=1600', '-ResY=1000', '-NoVSync', '-unattended', "-abslog=$astraProjectDir\Saved\Review_$astraView.log")
    if ($astraView -eq 'Gameplay') { $astraArgs += '-AstraSmokeTest' }
    if ($astraView -eq 'Bridge') { $astraArgs += '-AstraBridgeTest' }
    if ($astraView -eq 'Camp') { $astraArgs += '-AstraCampTest' }
    $astraProcess = Start-Process -FilePath $astraExe -ArgumentList $astraArgs -WindowStyle Hidden -PassThru
    $astraProcess.WaitForExit()
    Write-Output "$astraView review finished (exit $($astraProcess.ExitCode))"
    if ($astraProcess.ExitCode -ne 0) { throw "$astraView review failed. See Saved\Review_$astraView.log" }
    $astraShaderErrors = Select-String -LiteralPath "$astraProjectDir\Saved\Review_$astraView.log" -Pattern 'Failed to compile Material|LogShaderCompilers: Error|LogMaterial: Error|missing bUsedWith'
    if ($astraShaderErrors) { throw "$astraView contains material compilation errors. See Saved\Review_$astraView.log" }
}
