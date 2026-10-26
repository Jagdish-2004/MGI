# PhotoDepth 3D -- Launch Script
# Binds strictly to 127.0.0.1 (Local execution only)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         PhotoDepth 3D - Local Application Launcher       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Environment and Cache Verification
$env:TORCH_HOME = "$ProjectRoot\.cache\torch"
$PythonExe = "$ProjectRoot\.venv\Scripts\python.exe"
$StreamlitExe = "$ProjectRoot\.venv\Scripts\streamlit.exe"
$ViewerScript = "$ProjectRoot\viewer\serve_viewer.py"
$AppScript = "$ProjectRoot\app.py"

if (-not (Test-Path $PythonExe)) {
    Write-Error "Virtual environment not found at $PythonExe. Please ensure Phase 2 setup is complete."
    exit 1
}

Write-Host "[1/3] Environment verified: Python 3.12 (.venv)" -ForegroundColor Green
Write-Host "      Model cache: $env:TORCH_HOME" -ForegroundColor DarkGray

# 2. Check or Launch Viewer Server (Port 8080)
Write-Host "[2/3] Checking 3DGS Viewer Server on port 8080..." -ForegroundColor Yellow
$ViewerRunning = $false
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8080/" -Method Head -TimeoutSec 1 -ErrorAction SilentlyContinue
    if ($resp.StatusCode -eq 200) { $ViewerRunning = $true }
} catch {
    $ViewerRunning = $false
}

if ($ViewerRunning) {
    Write-Host "      Viewer server is already active at http://127.0.0.1:8080/" -ForegroundColor Green
} else {
    Write-Host "      Starting viewer server in background..." -ForegroundColor Yellow
    Start-Process -FilePath $PythonExe -ArgumentList "$ViewerScript 8080" -WorkingDirectory $ProjectRoot -WindowStyle Hidden
    Start-Sleep -Seconds 2
    Write-Host "      Viewer server started at http://127.0.0.1:8080/" -ForegroundColor Green
}

# 3. Launch Streamlit Application (Port 8501)
Write-Host "[3/3] Launching Streamlit UI at http://127.0.0.1:8501/ ..." -ForegroundColor Cyan
Write-Host "----------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "Press Ctrl+C to terminate the Streamlit session." -ForegroundColor DarkGray
Write-Host "----------------------------------------------------------" -ForegroundColor DarkGray

& $StreamlitExe run $AppScript --server.port 8501 --server.address 127.0.0.1 --browser.gatherUsageStats false
