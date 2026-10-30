# Starts the API, the worker and the frontend, each in its own PowerShell window, then checks
# that the API can reach MongoDB Atlas, Redis and Qdrant.
#
# Run from the repository root:
#   powershell -ExecutionPolicy Bypass -File .\start-dev.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "backend\.venv is missing. Create it first (see TECH_STACK_GUIDE.md, section 11)." -ForegroundColor Red
    exit 1
}

# Another program on port 8000 (for example another project's backend) would receive the
# frontend's requests instead of this API.
$busy = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    foreach ($listener in $busy) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
        Write-Host "Port 8000 is already in use by PID $($listener.OwningProcess):" -ForegroundColor Yellow
        Write-Host "  $($process.CommandLine)"
    }
    Write-Host "Stop that process (Stop-Process -Id <PID>) and run this script again." -ForegroundColor Yellow
    exit 1
}

function Start-Window([string]$title, [string]$directory, [string]$command) {
    $script = "`$Host.UI.RawUI.WindowTitle = '$title'; Set-Location '$directory'; $command"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $script | Out-Null
}

Start-Window "Copilot API" $backend "& '$python' -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
Start-Window "Copilot worker" $backend "& '$python' -m arq app.workers.settings.WorkerSettings"
if (-not (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Window "Copilot frontend" $frontend "npm run dev"
}

Write-Host "Waiting for the API..."
$report = $null
for ($i = 0; $i -lt 45 -and -not $report; $i++) {
    Start-Sleep -Seconds 2
    try {
        $report = Invoke-RestMethod http://127.0.0.1:8000/api/health -TimeoutSec 10
    } catch {
        $response = $_.Exception.Response
        if ($response) {
            $body = (New-Object IO.StreamReader($response.GetResponseStream())).ReadToEnd()
            $report = ($body | ConvertFrom-Json).error.details
        }
    }
}

if (-not $report) {
    Write-Host "The API did not start. Check the 'Copilot API' window for the error." -ForegroundColor Red
    exit 1
}

foreach ($name in "mongodb", "redis", "qdrant") {
    $check = $report.checks.$name
    $color = if ($check.status -eq "ok") { "Green" } else { "Red" }
    Write-Host ("  {0,-8} {1} {2}" -f $name, $check.status, $check.error) -ForegroundColor $color
}

if ($report.checks.mongodb.status -ne "ok") {
    $ip = try { (Invoke-WebRequest https://api.ipify.org -UseBasicParsing -TimeoutSec 10).Content } catch { "unknown" }
    Write-Host ""
    Write-Host "MongoDB Atlas is not reachable, so sign-in and registration will fail." -ForegroundColor Red
    Write-Host "Add this machine's public IP ($ip) in Atlas > Security > Network Access."
    Write-Host "Details: run backend\scripts\check_mongodb_atlas.py"
    exit 1
}

Write-Host ""
Write-Host "Ready: http://localhost:3000" -ForegroundColor Green
