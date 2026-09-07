param(
    [ValidateSet('Import','Relight','Review','Movement','Open')][string]$Mode='Open',
    [ValidateSet('CaveOverview','CaveFork1','CaveFork2','CaveHeart','CaveGameplay')][string]$View='CaveOverview',
    [switch]$LightsOff
)
$ErrorActionPreference='Stop'
$caveProject=Split-Path -Parent $PSScriptRoot
$caveEditor='C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor.exe'
$caveMap='/Game/Astra/Maps/L_AstraCrystalCave'
[Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',"$caveProject/DerivedDataCache",'Process')
$caveArgs=@("`"$caveProject/AstraLevelTest.uproject`"",'-NoSplash','-unattended','-NoSourceControl','-NoLiveCoding','-nosound','-ddc=InstalledNoZenLocalFallback','-ini:Engine:[ConsoleVariables]:r.NGX.Enable=0')
if($Mode -eq 'Import' -or $Mode -eq 'Relight') {
    $caveScript=if($Mode -eq 'Import'){'import_cave_scene.py'}else{'tune_cave_lighting.py'}
    $caveArgs+=@('/Engine/Maps/Entry',"`"-ExecutePythonScript=$PSScriptRoot/$caveScript`"",'-RenderOffscreen',"`"-abslog=$caveProject/Saved/Cave$Mode.log`"",'-ExecCmds="t.MaxFPS 20"')
} elseif($Mode -eq 'Open') {
    $caveArgs+=@($caveMap,"`"-abslog=$caveProject/Saved/CaveEditor.log`"")
} else {
    $caveArgs+=@($caveMap,'-game','-RenderOffscreen','-windowed','-ForceRes','-ResX=1600','-ResY=1000','-AstraRenderProfile=Native1080','-NoVSync','-ExecCmds="t.MaxFPS 30"')
    if($Mode -eq 'Movement') { $caveArgs+=@('-AstraCaveTest',"`"-abslog=$caveProject/Saved/CaveMovement.log`"") }
    else { $caveArgs+=@("-AstraReview=$View",'-AstraReviewCaptureSeconds=18',"`"-abslog=$caveProject/Saved/CaveReview_$View.log`"") }
    if($LightsOff) {$caveArgs+='-AstraCaveLightsOff'}
}
$caveStarted=Get-Date
$caveProcess=Start-Process -FilePath $caveEditor -ArgumentList $caveArgs -WindowStyle Hidden -PassThru
Write-Output "Started only this cave worktree process: PID $($caveProcess.Id) ($Mode)"
$caveProcess.Id | Set-Content -LiteralPath "$caveProject/Saved/CaveOwnedProcess.pid"
if($Mode -ne 'Open') {
    $caveProcess.WaitForExit()
    if($caveProcess.ExitCode -ne 0) {throw "Cave $Mode exited $($caveProcess.ExitCode); see Saved/Cave*.log"}
    if($Mode -eq 'Import') {
        if((Get-Item "$caveProject/ArtSource/Previews/CrystalCave/UE_CaveImport.json").LastWriteTime -lt $caveStarted) {throw 'Cave import report is stale'}
        $caveResult=Get-Content "$caveProject/ArtSource/Previews/CrystalCave/UE_CaveImport.json" -Raw | ConvertFrom-Json
        if($caveResult.status -ne 'success') {throw 'Cave import report failed'}
    }
    if($Mode -eq 'Movement') {
        if((Get-Item "$caveProject/ArtSource/Previews/CrystalCave/UE_CaveMovementValidation.json").LastWriteTime -lt $caveStarted) {throw 'Cave movement report is stale'}
        $caveTest=Get-Content "$caveProject/ArtSource/Previews/CrystalCave/UE_CaveMovementValidation.json" -Raw | ConvertFrom-Json
        if(-not $caveTest.passed) {throw "Cave movement report failed: $($caveTest.failed_checks) checks"}
    }
    if($Mode -eq 'Relight') {
        $caveSavedPath="$caveProject/ArtSource/Previews/CrystalCave/UE_CaveSavedValidation.json"
        if((Get-Item $caveSavedPath).LastWriteTime -lt $caveStarted) {throw 'Cave saved-map report is stale'}
        if(-not (Get-Content $caveSavedPath -Raw | ConvertFrom-Json).passed) {throw 'Cave saved-map validation failed'}
    }
    if($Mode -eq 'Review') {
        $caveSource="$caveProject/ArtSource/Previews/UE_$View.png"
        if((Get-Item $caveSource).LastWriteTime -lt $caveStarted) {throw 'Cave screenshot is stale'}
        $caveSuffix=if($LightsOff){'_LightsOff'}else{''}
        Copy-Item -LiteralPath $caveSource -Destination "$caveProject/ArtSource/Previews/CrystalCave/UE_$View$caveSuffix.png" -Force
        Remove-Item -LiteralPath $caveSource
    }
    Write-Output "Cave $Mode complete"
}
