param(
    [int]$EveryHours = 2,
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"

if ($EveryHours -lt 1) {
    throw "EveryHours must be at least 1."
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $ProjectRoot "experiment_01_discovery\scheduled_refresh.py"

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

$TaskName = "YouTube Production - Experiment 01.3 Auto Refresh"
$StartTime = (Get-Date).AddMinutes(5).ToString("HH:mm")
$TaskCommand = "`"$PythonPath`" `"$Runner`""

$Arguments = @(
    "/Create",
    "/TN", $TaskName,
    "/TR", $TaskCommand,
    "/SC", "HOURLY",
    "/MO", "$EveryHours",
    "/ST", $StartTime,
    "/RL", "LIMITED",
    "/F"
)

Write-Host "Registering task: $TaskName"
Write-Host "Schedule: every $EveryHours hour(s)"
Write-Host "Runner: $Runner"

& schtasks.exe @Arguments
if ($LASTEXITCODE -ne 0) {
    throw "Task Scheduler registration failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "Auto refresh installed."
Write-Host "The task is self-limiting: it skips when no cohort exists, the cohort"
Write-Host "is insufficient, a recent snapshot already exists, another refresh is"
Write-Host "running, or the current cohort already has enough evidence for 01.4."
