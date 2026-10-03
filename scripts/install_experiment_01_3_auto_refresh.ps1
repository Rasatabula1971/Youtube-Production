param(
    [int]$EveryHours = 2,
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"

if ($EveryHours -lt 1) {
    throw "EveryHours must be at least 1."
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $ProjectRoot "opportunity_engine\scheduled_tick.py"

if (-not (Test-Path $Runner)) {
    throw "Cannot find scheduled refresh runner: $Runner"
}

if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonCommand = Get-Command python -ErrorAction Stop
    $PythonPath = $PythonCommand.Source
}

if (-not (Test-Path $PythonPath)) {
    throw "Cannot find Python executable: $PythonPath"
}

$TaskName = "YouTube Production - Opportunity Research Continue"
$LegacyTaskName = "YouTube Production - Experiment 01.3 Auto Refresh"
$TaskCommand = "`"$PythonPath`" `"$Runner`""

$Arguments = @(
    "/Create",
    "/TN", $TaskName,
    "/TR", $TaskCommand,
    "/SC", "HOURLY",
    "/MO", "$EveryHours",
    "/RL", "LIMITED",
    "/F"
)

& schtasks.exe /Delete /TN $LegacyTaskName /F 2>$null | Out-Null

Write-Host "Registering task: $TaskName"
Write-Host "Schedule: every $EveryHours hour(s)"
Write-Host "Runner: $Runner"

& schtasks.exe @Arguments
if ($LASTEXITCODE -ne 0) {
    throw "Task Scheduler registration failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "Opportunity automation installed."
Write-Host "The task wakes every $EveryHours hour(s). It takes a frozen-cohort snapshot"
Write-Host "only when due and advances through 01.4 and 01.5 when velocity evidence is"
Write-Host "ready, then runs one viral radar tick: discovery when due (every 8 hours by"
Write-Host "default), otherwise snapshots of tracked breakouts when due."
