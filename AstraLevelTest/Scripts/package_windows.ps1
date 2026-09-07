param(
    [ValidateSet('Shipping','Development')][string]$Configuration = 'Shipping',
    [string]$Engine = 'C:\Program Files\Epic Games\UE_5.7',
    [string]$OutputDirectory,
    [switch]$SkipEditorBuild
)
$ErrorActionPreference = 'Stop'
$astraPackageProject = Split-Path -Parent $PSScriptRoot
$astraPackageRepo = Split-Path -Parent $astraPackageProject
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $astraPackageRepo 'Builds\AstraLevelTest_Win64' }
$astraPackageOutput = [IO.Path]::GetFullPath($OutputDirectory)
$astraPackageUAT = Join-Path $Engine 'Engine\Build\BatchFiles\RunUAT.bat'
$astraPackageDLSS = Join-Path $Engine 'Engine\Plugins\Marketplace\DLSS\DLSS.uplugin'
if (-not (Test-Path -LiteralPath $astraPackageDLSS)) { throw 'Install the NVIDIA DLSS plugin for UE 5.7 in Engine/Plugins/Marketplace first.' }
New-Item -ItemType Directory -Path $astraPackageOutput -Force | Out-Null
$astraPackageArgs = @(
    'BuildCookRun', '-nop4', '-unattended', '-utf8output',
    "-project=$astraPackageProject\AstraLevelTest.uproject",
    '-platform=Win64', '-architecture=x64', "-clientconfig=$Configuration",
    '-build', '-cook', '-stage', '-package', '-archive',
    '-pak', '-iostore', '-compressed', '-prereqs', '-nodebuginfo',
    '-map=/Game/Astra/Maps/L_AstraWoodland',
    "-archivedirectory=$astraPackageOutput", '-ubtargs=-NoUBA'
)
if ($SkipEditorBuild) { $astraPackageArgs += '-nocompileeditor' }
& $astraPackageUAT @astraPackageArgs
if ($LASTEXITCODE -ne 0) { throw "Windows x64 packaging failed with exit code $LASTEXITCODE" }
$astraPackageWindows = Join-Path $astraPackageOutput 'Windows'
$astraPackageExe = Join-Path $astraPackageWindows 'AstraLevelTest.exe'
if (-not (Test-Path -LiteralPath $astraPackageExe)) { throw "Packaged launcher missing: $astraPackageExe" }
$astraPackageLaunchers = @{
    'Play_4K_DLSS.cmd' = 'start "" /D "%~dp0" "%~dp0AstraLevelTest.exe" -AstraRenderProfile=DLSS4K -fullscreen'
    'Play_1080p_Native.cmd' = 'start "" /D "%~dp0" "%~dp0AstraLevelTest.exe" -AstraRenderProfile=Native1080 -fullscreen'
    'Play_4K_Native.cmd' = 'start "" /D "%~dp0" "%~dp0AstraLevelTest.exe" -AstraRenderProfile=Native4K -fullscreen'
}
foreach ($astraPackageLauncher in $astraPackageLaunchers.GetEnumerator()) {
    [IO.File]::WriteAllText((Join-Path $astraPackageWindows $astraPackageLauncher.Key), "@echo off`r`n$($astraPackageLauncher.Value)`r`n", [Text.Encoding]::ASCII)
}
$astraPackageReadme = @'
AstraLevelTest — Windows x64

실행: AstraLevelTest.exe 또는 원하는 해상도의 Play_*.cmd

Play_4K_DLSS.cmd: 3840x2160 출력, DLSS Performance, 내부 1920x1080.
Play_1080p_Native.cmd: 1920x1080 네이티브 렌더링.
Play_4K_Native.cmd: 3840x2160 네이티브 렌더링.
DLSS를 지원하지 않는 GPU에서는 1080p 네이티브로 실행합니다.

WASD: 이동
P: 7개 장소 자동 산책 영상 모드 / 원래 플레이 상태로 복귀
Alt+F4: 종료

실행 파일과 함께 Engine, AstraLevelTest 폴더를 모두 보관하세요.
처음 실행하는 PC에 필수 런타임이 없으면
Engine\Extras\Redist\en-us\vc_redist.x64.exe를 실행하세요.
DX12/Shader Model 6을 지원하는 Windows 환경이 필요합니다.
'@
[IO.File]::WriteAllText((Join-Path $astraPackageWindows 'README_KO.txt'), $astraPackageReadme, [Text.UTF8Encoding]::new($true))
Write-Output "Windows x64 $Configuration package: $astraPackageExe"
