$ErrorActionPreference = "Stop"

$TaskName = "YouTube Production - Opportunity Research Continue"

Write-Host "Removing task: $TaskName"

& schtasks.exe /Delete /TN $TaskName /F
if ($LASTEXITCODE -ne 0) {
    Write-Host "Task was not removed. It may already be absent."
    exit $LASTEXITCODE
}

Write-Host "Auto refresh task removed."
