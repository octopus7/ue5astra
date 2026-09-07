[CmdletBinding()]
param(
    [switch]$Screenshot,
    [switch]$Refresh,
    [switch]$RebuildAssets,
    [switch]$CloseEditor,
    [switch]$AsJson,
    [ValidateRange(1, 60)][int]$WaitSeconds = 30,
    [ValidateRange(3, 300)][int]$StaleSeconds = 15,
    [ValidateRange(64, 3840)][int]$Width = 1280,
    [ValidateRange(64, 2160)][int]$Height = 720,
    [ValidateRange(0.0, 3.0)][double]$NiagaraAgeSeconds,
    [string]$NiagaraActorLabel,
    [ValidateRange(0, 100)][int]$LogTail = 12
)

$ErrorActionPreference = 'Stop'
if (([int][bool]$Screenshot + [int][bool]$Refresh + [int][bool]$RebuildAssets + [int][bool]$CloseEditor) -gt 1) {
    throw 'Choose only one request switch: -Screenshot, -Refresh, -RebuildAssets or -CloseEditor.'
}
$projectDirectory = Split-Path -Parent $PSScriptRoot
$projectFile = Join-Path $projectDirectory 'AstraNigara.uproject'
$bridgeDirectory = Join-Path $projectDirectory 'Saved\EditorBridge'
$statusPath = Join-Path $bridgeDirectory 'status.json'
$processQueryError = $null
$engineProcesses = @()
try {
    $engineProcesses = @(Get-CimInstance Win32_Process -Filter "Name LIKE 'UnrealEditor%'" | ForEach-Object {
        $engineProcess = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
        [pscustomobject]@{
            pid = $_.ProcessId
            name = $_.Name
            project_match = [bool]($_.CommandLine -and ($_.CommandLine -like '*AstraNigara.uproject*'))
            responding = if ($engineProcess) { $engineProcess.Responding } else { $null }
            window_title = if ($engineProcess) { $engineProcess.MainWindowTitle } else { $null }
        }
    })
} catch {
    $processQueryError = $_.Exception.Message
    $engineProcesses = @(Get-Process -Name 'UnrealEditor*' -ErrorAction SilentlyContinue | ForEach-Object {
        [pscustomobject]@{ pid = $_.Id; name = $_.ProcessName; project_match = $null; responding = $_.Responding; window_title = $_.MainWindowTitle }
    })
}

$status = $null
$statusError = $null
if (Test-Path -LiteralPath $statusPath) {
    try { $status = Get-Content -LiteralPath $statusPath -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { $statusError = $_.Exception.Message }
}
$age = $null
$state = 'NO_HEARTBEAT'
if ($status) {
    try {
        $age = [Math]::Round(([DateTimeOffset]::UtcNow - [DateTimeOffset]::Parse($status.timestamp_utc)).TotalSeconds, 1)
        $writerAlive = @(Get-Process -Id $status.pid -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like 'UnrealEditor*' }).Count -gt 0
        $state = if (-not $writerAlive) { 'EDITOR_EXITED' } elseif ($age -lt -5) { 'CLOCK_MISMATCH' } elseif ($age -gt $StaleSeconds) { 'STALE' } else { 'LIVE' }
    } catch { $state = 'INVALID_STATUS'; $statusError = $_.Exception.Message }
} elseif ($statusError) { $state = 'INVALID_STATUS' }

$response = $null
if ($Screenshot -or $Refresh -or $RebuildAssets -or $CloseEditor) {
    if ($state -ne 'LIVE') {
        $response = [pscustomobject]@{ state = 'error'; error = "Cannot request an editor action while heartbeat is $state. Start the project with editor_status.py loaded." }
    } else {
        $requestId = [Guid]::NewGuid().ToString('D')
        $requestsDirectory = Join-Path $bridgeDirectory 'requests'
        New-Item -ItemType Directory -Path $requestsDirectory -Force | Out-Null
        $requestPath = Join-Path $requestsDirectory ($requestId + '.json')
        $temporaryPath = Join-Path $requestsDirectory ($requestId + '.tmp')
        $responsePath = Join-Path (Join-Path $bridgeDirectory 'responses') ($requestId + '.json')
        $request = [ordered]@{
            action = if ($Screenshot) { 'screenshot' } elseif ($RebuildAssets) { 'rebuild_small_destruction' } elseif ($CloseEditor) { 'close_editor' } else { 'status' }
            session_id = $status.session_id
            requested_utc = [DateTimeOffset]::UtcNow.ToString('o')
            width = $Width
            height = $Height
        }
        if ($PSBoundParameters.ContainsKey('NiagaraAgeSeconds')) { $request.niagara_age_seconds = $NiagaraAgeSeconds }
        if ($NiagaraActorLabel) { $request.niagara_actor_label = $NiagaraActorLabel }
        [IO.File]::WriteAllText($temporaryPath, ($request | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
        Move-Item -LiteralPath $temporaryPath -Destination $requestPath
        $deadline = [DateTimeOffset]::UtcNow.AddSeconds($WaitSeconds)
        do {
            if (Test-Path -LiteralPath $responsePath) {
                $response = Get-Content -LiteralPath $responsePath -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($response.state -ne 'pending') { break }
            }
            Start-Sleep -Milliseconds 250
        } while ([DateTimeOffset]::UtcNow -lt $deadline)
        if (-not $response -or $response.state -eq 'pending') {
            $response = [pscustomobject]@{ id = $requestId; state = 'timeout'; response_path = $responsePath; error = 'Request wait elapsed; inspect response_path for late completion.' }
        }
        if (Test-Path -LiteralPath $statusPath) {
            $status = Get-Content -LiteralPath $statusPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $age = [Math]::Round(([DateTimeOffset]::UtcNow - [DateTimeOffset]::Parse($status.timestamp_utc)).TotalSeconds, 1)
            if ($age -gt $StaleSeconds) { $state = 'STALE' }
        }
    }
}

$logFile = $null
if ($status -and $status.log_path) {
    $logFile = Get-Item -LiteralPath $status.log_path -ErrorAction SilentlyContinue
} else {
    $logFile = Get-ChildItem -LiteralPath (Join-Path $projectDirectory 'Saved\Logs') -Filter '*.log' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
}
$logLines = @()
$recentErrors = @()
if ($logFile -and $LogTail -gt 0) {
    $tail = @(Get-Content -LiteralPath $logFile.FullName -Tail 300 -ErrorAction SilentlyContinue)
    $logLines = @($tail | Select-Object -Last $LogTail)
    $recentErrors = @($tail | Where-Object { $_ -match '(?i)(\bError:|Fatal error:|Traceback|ASTRA_EDITOR_BRIDGE.*ERROR)' } | Select-Object -Last $LogTail)
}
$result = [ordered]@{
    state = $state
    age_seconds = $age
    stale_after_seconds = $StaleSeconds
    project = $projectFile
    status_path = $statusPath
    status_error = $statusError
    processes = $engineProcesses
    process_query_error = $processQueryError
    status = $status
    request_result = $response
    log_path = if ($logFile) { $logFile.FullName } else { $null }
    recent_log_errors = $recentErrors
    log_tail = $logLines
}
if ($AsJson) {
    $result | ConvertTo-Json -Depth 14
} else {
    Write-Output ('Editor: {0} | heartbeat age: {1}s | stale after: {2}s' -f $state, $age, $StaleSeconds)
    if ($status) {
        Write-Output ('Map: {0} | PIE: {1} | PID: {2} | heartbeat: {3}' -f $status.editor_map, $status.pie, $status.pid, $status.sequence)
        Write-Output ('Actors: editor={0}, game={1} | selected={2}' -f $status.editor_actor_count, $status.game_actor_count, @($status.selected_actors).Count)
        $status.niagara | Select-Object world, label, asset, active, auto_activate, visible | Format-Table -AutoSize
        if ($status.errors) { Write-Output ('Status read errors: ' + ($status.errors -join '; ')) }
    }
    if ($statusError) { Write-Output ('Status error: ' + $statusError) }
    $engineProcesses | Format-Table -AutoSize
    if ($processQueryError) { Write-Output ('Process details unavailable: ' + $processQueryError) }
    if ($response) { $response | Format-List }
    if ($recentErrors.Count) { Write-Output 'Recent log errors:'; $recentErrors }
    if ($logFile -and $LogTail -gt 0) { Write-Output ('Latest log: ' + $logFile.FullName); $logLines }
    Write-Output ('Status JSON: ' + $statusPath)
}

if ($CloseEditor -and $response -and $response.action -eq 'close_editor' -and $response.state -eq 'complete' -and $response.closing) { exit 0 }
if ($state -ne 'LIVE') { exit 2 }
if ($response -and $response.state -ne 'complete') { exit 3 }
exit 0
