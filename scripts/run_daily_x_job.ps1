param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$script:LogPath = $null

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line
    if ($script:LogPath) {
        Add-Content -Path $script:LogPath -Value $line
    }
}

function Invoke-LoggedCommand {
    param(
        [string]$StepName,
        [string]$Command
    )

    Write-Log "START $StepName"
    & powershell.exe -NoProfile -Command $Command 2>&1 | Tee-Object -FilePath $script:LogPath -Append
    if ($LASTEXITCODE -ne 0) {
        throw "$StepName failed with exit code $LASTEXITCODE"
    }
    Write-Log "DONE  $StepName"
}

function Get-DirtyState {
    param(
        [string]$Root,
        [string[]]$Paths
    )

    $status = & git -C $Root status --porcelain -- @Paths
    if ($LASTEXITCODE -ne 0) {
        throw "git status preflight failed"
    }
    return [string]::Join("`n", $status).Trim()
}

$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$logDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$script:LogPath = Join-Path $logDir "daily_x_job_$timestamp.log"

$cookiePath = Join-Path $RepoRoot "human_comment\cookies.txt"
$generatedPaths = @("index.html", "reports/daily")

Write-Log "Repo root: $RepoRoot"
Write-Log "Log file: $script:LogPath"

$env:X_PROXY = ""
$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""
$env:ALL_PROXY = ""
$env:NO_PROXY = ""
Write-Log "Cleared proxy environment variables for direct X access"

if (-not (Test-Path $cookiePath)) {
    throw "cookie file not found: $cookiePath"
}

$dirtyGenerated = Get-DirtyState -Root $RepoRoot -Paths $generatedPaths
if ($dirtyGenerated) {
    Write-Log "Generated tracked paths are already dirty. Abort to avoid mixing scheduled output with manual changes."
    Add-Content -Path $script:LogPath -Value $dirtyGenerated
    exit 2
}

Invoke-LoggedCommand -StepName "x_user_crawler.py" -Command "Set-Location '$RepoRoot'; python .\x_user_crawler.py"
Invoke-LoggedCommand -StepName "run_daily_pipeline_v1.py" -Command "Set-Location '$RepoRoot'; python .\run_daily_pipeline_v1.py"

Write-Log "Staging generated files"
& git -C $RepoRoot add -- "index.html" "reports/daily"
if ($LASTEXITCODE -ne 0) {
    throw "git add failed"
}

& git -C $RepoRoot diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Log "No staged changes after crawl and pipeline. Nothing to commit."
    exit 0
}

$commitMessage = "chore: daily x crawl {0}" -f (Get-Date -Format "yyyy-MM-dd")
Write-Log "Creating commit: $commitMessage"
& git -C $RepoRoot commit -m $commitMessage 2>&1 | Tee-Object -FilePath $script:LogPath -Append
if ($LASTEXITCODE -ne 0) {
    throw "git commit failed"
}

if (-not $NoPush) {
    Write-Log "Pushing to origin/main"
    & git -C $RepoRoot push origin main 2>&1 | Tee-Object -FilePath $script:LogPath -Append
    if ($LASTEXITCODE -ne 0) {
        throw "git push failed"
    }
}

Write-Log "Daily X job completed successfully"
