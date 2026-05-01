# ============================================
# ChatPDF One-Click Startup Script
# Start backend (FastAPI) and frontend (Vite) together
# ============================================

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# ------------ Helper: Colored Output ------------
function Write-Info($msg)   { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Write-Fail($msg)  { Write-Host "[ERR]  $msg" -ForegroundColor Red }
function Write-Warn($msg)  { Write-Host "[WARN] $msg" -ForegroundColor Yellow }

# ------------ Helper: Port Check ------------
function Test-PortInUse($port) {
    $connections = netstat -ano | Select-String "LISTENING" | Select-String ":$port "
    return $connections -ne $null
}

Write-Info "========================================"
Write-Info "  ChatPDF Startup"
Write-Info "========================================"
Write-Info ""

# ------------ Check Dependencies ------------
$PythonExe = Join-Path $ProjectRoot "chatpdf_venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Fail "Python venv not found: $PythonExe"
    Write-Fail "Please create virtual environment: python -m venv chatpdf_venv"
    exit 1
}
Write-Ok "Python venv: $PythonExe"

$FrontendDir = Join-Path $ProjectRoot "frontend"
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Warn "Frontend dependencies missing, installing..."
    Push-Location $FrontendDir
    try {
        npm install
        Write-Ok "Frontend dependencies installed"
    } catch {
        Write-Fail "npm install failed: $_"
        Pop-Location
        exit 1
    }
    Pop-Location
}
Write-Ok "Frontend dependencies: ready"

$EnvFile = Join-Path $ProjectRoot "backend\.env"
if (-not (Test-Path $EnvFile)) {
    Write-Warn "backend\.env not found, copying from .env.example..."
    Copy-Item (Join-Path $ProjectRoot "backend\.env.example") $EnvFile
    Write-Warn "Please edit backend\.env and set DEEPSEEK_API_KEY"
    exit 1
}
Write-Ok "Config: backend\.env ready"

# ------------ Check Port Conflicts ------------
if (Test-PortInUse 8000) {
    Write-Fail "Port 8000 is already in use"
    Write-Fail "Please close the existing process or change the port"
    exit 1
}
if (Test-PortInUse 5173) {
    Write-Fail "Port 5173 is already in use"
    Write-Fail "Please close the existing process or change the port"
    exit 1
}

# ------------ Start Backend ------------
Write-Info ""
Write-Info "Starting backend server..."
$BackendLog = Join-Path $ProjectRoot "backend\server.log"
$BackendErrLog = Join-Path $ProjectRoot "backend\server.error.log"
$BackendProcess = Start-Process -FilePath $PythonExe `
    -ArgumentList "-m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000" `
    -WorkingDirectory (Join-Path $ProjectRoot "backend") `
    -NoNewWindow -PassThru `
    -RedirectStandardOutput $BackendLog `
    -RedirectStandardError $BackendErrLog

Write-Ok "Backend starting (PID: $($BackendProcess.Id))..."
Write-Info "  Stdout: $BackendLog"
Write-Info "  Stderr: $BackendErrLog"

# Wait for backend (max 30s)
$BackendReady = $false
for ($i = 1; $i -le 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $BackendReady = $true
            break
        }
    } catch {
        # keep waiting
    }
    if ($i % 5 -eq 0) { Write-Info "  Waiting for backend... ($i sec)" }
}

if (-not $BackendReady) {
    Write-Warn "Backend may still be initializing (Phase 2 takes 3-8s)"
    Write-Warn "Check later: http://localhost:8000/api/v1/health"
} else {
    Write-Ok "Backend ready -> http://localhost:8000"
}

# ------------ Start Frontend ------------
Write-Info ""
Write-Info "Starting frontend server..."
$FrontendLog = Join-Path $ProjectRoot "frontend\vite.log"
$FrontendErrLog = Join-Path $ProjectRoot "frontend\vite.error.log"
$FrontendProcess = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c npm run dev" `
    -WorkingDirectory $FrontendDir `
    -NoNewWindow -PassThru `
    -RedirectStandardOutput $FrontendLog `
    -RedirectStandardError $FrontendErrLog

Write-Ok "Frontend starting (PID: $($FrontendProcess.Id))..."
Write-Info "  Stdout: $FrontendLog"
Write-Info "  Stderr: $FrontendErrLog"

# Wait for frontend (max 30s)
$FrontendReady = $false
for ($i = 1; $i -le 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200 -or $response.StatusCode -eq 304) {
            $FrontendReady = $true
            break
        }
    } catch {
        # keep waiting
    }
    if ($i % 5 -eq 0) { Write-Info "  Waiting for frontend... ($i sec)" }
}

if (-not $FrontendReady) {
    Write-Warn "Frontend may still be starting"
    Write-Warn "Check later: http://localhost:5173"
} else {
    Write-Ok "Frontend ready -> http://localhost:5173"
}

# ------------ Show Result ------------
Write-Info ""
Write-Info "========================================"
Write-Info "  ChatPDF Started Successfully"
if ($BackendReady) {
    Write-Ok "  Backend: http://localhost:8000"
    Write-Info "  Health:  http://localhost:8000/api/v1/health"
} else {
    Write-Warn "  Backend: still initializing (check backend\server.error.log)"
}
if ($FrontendReady) {
    Write-Ok "  Frontend: http://localhost:5173"
} else {
    Write-Warn "  Frontend: still starting (check frontend\vite.error.log)"
}
Write-Info "========================================"
Write-Info ""
Write-Info "Press Ctrl+C to exit (services will keep running)"
Write-Info "To stop all services:"
Write-Info "  Stop-Process -Id $($BackendProcess.Id) -Force"
Write-Info "  Stop-Process -Id $($FrontendProcess.Id) -Force"

# ------------ Monitor Loop ------------
while ($true) {
    if ($BackendProcess.HasExited) {
        Write-Warn "Backend exited (PID: $($BackendProcess.Id))"
    }
    if ($FrontendProcess.HasExited) {
        Write-Warn "Frontend exited (PID: $($FrontendProcess.Id))"
    }
    if ($BackendProcess.HasExited -and $FrontendProcess.HasExited) {
        Write-Fail "Both services exited, script terminating"
        break
    }
    Start-Sleep -Seconds 5
}
