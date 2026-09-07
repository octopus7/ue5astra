param(
    [ValidateSet('Import','Review','Movement','Open')][string]$Mode='Open',
    [string]$View='CaveOverview',
    [switch]$LightsOff
)
$ErrorActionPreference='Stop'
$caveProject=Split-Path -Parent $PSScriptRoot
$caveEditor='C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor.exe'
$caveMap='/Game/Astra/Maps/L_AstraCrystalCave'
$caveArgs=@("`"$caveProject/AstraLevelTest.uproject`"",'-NoSplash','-unattended','-NoSourceControl','-NoLiveCoding','-nosound')
if($Mode -eq 'Import') {
    $caveArgs+=@("`"-ExecutePythonScript=$PSScriptRoot/import_cave_scene.py`"",'-RenderOffscreen',"`"-abslog=$caveProject/Saved/CaveImport.log`"",'-ExecCmds="t.MaxFPS 20"')
} elseif($Mode -eq 'Open') {
    $caveArgs+=@($caveMap,"`"-abslog=$caveProject/Saved/CaveEditor.log`"")
} else {
    $caveArgs+=@($caveMap,'-game','-RenderOffscreen','-windowed','-ResX=1600','-ResY=1000','-AstraRenderProfile=Native1080','-NoVSync','-ExecCmds="t.MaxFPS 30"')
    if($Mode -eq 'Movement') { $caveArgs+=@('-AstraCaveTest',"`"-abslog=$caveProject/Saved/CaveMovement.log`"") }
    else { $caveArgs+=@("-AstraReview=$View",'-AstraReviewCaptureSeconds=18',"`"-abslog=$caveProject/Saved/CaveReview_$View.log`"") }
    if($LightsOff) {$caveArgs+='-AstraCaveLightsOff'}
}
$caveProcess=Start-Process -FilePath $caveEditor -ArgumentList $caveArgs -WindowStyle Hidden -PassThru
Write-Output "Started only this cave worktree process: PID $($caveProcess.Id) ($Mode)"
$caveProcess.Id | Set-Content -LiteralPath "$caveProject/Saved/CaveOwnedProcess.pid"
if($Mode -ne 'Open') {
    $caveProcess.WaitForExit()
    if($caveProcess.ExitCode -ne 0) {throw "Cave $Mode exited $($caveProcess.ExitCode); see Saved/Cave*.log"}
    if($Mode -eq 'Import') {
        $caveResult=Get-Content "$caveProject/ArtSource/Previews/CrystalCave/UE_CaveImport.json" -Raw | ConvertFrom-Json
        if($caveResult.status -ne 'success') {throw 'Cave import report failed'}
    }
    if($Mode -eq 'Review') {
        $caveSource="$caveProject/ArtSource/Previews/UE_$View.png"
        $caveSuffix=if($LightsOff){'_LightsOff'}else{''}
        Copy-Item -LiteralPath $caveSource -Destination "$caveProject/ArtSource/Previews/CrystalCave/UE_$View$caveSuffix.png" -Force
    }
    Write-Output "Cave $Mode complete"
}

