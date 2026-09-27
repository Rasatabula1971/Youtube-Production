param(
    [int]$EveryHours = 2,
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"

if ($EveryHours -lt 1) {
    throw "EveryHours must be at least 1."
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $ProjectRoot "experiment_01_discovery\opportunity_research.py"

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
$TaskCommand = "`"$PythonPath`" `"$Runner`" --mode continue"

$Arguments = @(
    "/Create",
    "/TN", $TaskName,
    "/TR", $TaskCommand,
    "/SC", "HOURLY",
    "/MO", "$EveryHours",
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
Write-Host "Opportunity Research continuation installed."
Write-Host "The task wakes every $EveryHours hour(s), takes a frozen-cohort snapshot"
Write-Host "only when due, then automatically advances through 01.4 and 01.5 when"
Write-Host "velocity evidence becomes ready."
