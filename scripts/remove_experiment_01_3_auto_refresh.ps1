$ErrorActionPreference = "Stop"

$TaskName = "YouTube Production - Opportunity Research Continue"
$LegacyTaskName = "YouTube Production - Experiment 01.3 Auto Refresh"

Write-Host "Removing task: $TaskName"

& schtasks.exe /Delete /TN $TaskName /F
if ($LASTEXITCODE -ne 0) {
    Write-Host "Task was not removed. It may already be absent."
    exit $LASTEXITCODE
}

& schtasks.exe /Delete /TN $LegacyTaskName /F 2>$null | Out-Null
Write-Host "Opportunity Research continuation task removed."
