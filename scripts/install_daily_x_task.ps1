param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$TaskName = "AI_News_Updator_Daily_X",
    [string]$Time = "06:00"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$runner = Join-Path $RepoRoot "scripts\run_daily_x_job.ps1"
if (-not (Test-Path $runner)) {
    throw "runner script not found: $runner"
}

$taskCommand = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $runner

schtasks /Create /SC DAILY /ST $Time /TN $TaskName /TR $taskCommand /F | Out-Host
schtasks /Query /TN $TaskName /V /FO LIST | Out-Host
