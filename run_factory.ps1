# =====================================================================
# GTA 6 AI Clip Factory - PowerShell Launcher
# Production runner for FastAPI Backend + Next.js Gaming UI
# =====================================================================

$ErrorActionPreference = "Stop"

function Write-BrandHeader {
    Clear-Host
    Write-Host "=====================================================================" -ForegroundColor Magenta
    Write-Host "                GTA 6 AI CLIP FACTORY - DESKTOP STUDIO               " -ForegroundColor Cyan
    Write-Host "     Automated Vertical Highlights Engine for GTA 6 Streamers        " -ForegroundColor Yellow
    Write-Host "=====================================================================" -ForegroundColor Magenta
    Write-Host ""
}

Write-BrandHeader

# 1. Environment Verification
Write-Host "[1/5] Verifying System Dependencies..." -ForegroundColor Cyan

# Check Python
try {
    $pythonVer = (python --version 2>&1)
    Write-Host "  [+] Python: $pythonVer" -ForegroundColor Green
} catch {
    Write-Host "  [!] ERROR: Python is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# Check Node.js
try {
    $nodeVer = (node --version 2>&1)
    Write-Host "  [+] Node.js: $nodeVer" -ForegroundColor Green
} catch {
    Write-Host "  [!] ERROR: Node.js is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# 2. Hardware / Acceleration Detection
Write-Host "`n[2/5] Checking Hardware Acceleration..." -ForegroundColor Cyan
try {
    $gpuCheck = python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU Fallback\"}')" 2>&1
    Write-Host "  [+] $gpuCheck" -ForegroundColor Green
} catch {
    Write-Host "  [i] PyTorch acceleration check: Running in resilient CPU mode." -ForegroundColor Yellow
}

# 3. Create Storage Directories
Write-Host "`n[3/5] Initializing Local Storage Hierarchy..." -ForegroundColor Cyan
$directories = @(
    "backend/data/temp",
    "backend/data/storage/recordings",
    "backend/data/storage/clips",
    "backend/data/storage/thumbnails",
    "backend/data/models"
)
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  [+] Created: $dir" -ForegroundColor DarkGray
    }
}
Write-Host "  [+] Storage directories verified." -ForegroundColor Green

# 4. Frontend Dependencies Check
Write-Host "`n[4/5] Checking Frontend Assets..." -ForegroundColor Cyan
if (-not (Test-Path "frontend/node_modules")) {
    Write-Host "  [i] First-time setup: Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location frontend
    npm install
    Pop-Location
}
Write-Host "  [+] Frontend ready." -ForegroundColor Green

# 5. Launch Backend & Frontend Services
Write-Host "`n[5/5] Launching Services..." -ForegroundColor Cyan

# Spawn Backend API Process
$backendCmd = "cd '$PSScriptRoot/backend'; `$env:PYTHONPATH='.'; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle = 'GTA 6 Clip Factory - Backend API (Port 8000)'; $backendCmd"
Write-Host "  [+] FastAPI Backend started on http://127.0.0.1:8000" -ForegroundColor Green

# Spawn Frontend UI Process
$frontendCmd = "cd '$PSScriptRoot/frontend'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle = 'GTA 6 Clip Factory - Web UI (Port 3000)'; $frontendCmd"
Write-Host "  [+] Next.js UI started on http://127.0.0.1:3000" -ForegroundColor Green

Write-Host "`nWaiting 5 seconds for services to initialize..." -ForegroundColor DarkGray
Start-Sleep -Seconds 5

# Auto-open browser
Write-Host "Opening GTA 6 AI Clip Factory in default browser..." -ForegroundColor Cyan
Start-Process "http://localhost:3000"

Write-Host "`n=====================================================================" -ForegroundColor Magenta
Write-Host "  APPLICATION IS RUNNING SUCCESSFULLY!" -ForegroundColor Green
Write-Host "  - Web Dashboard:     http://localhost:3000" -ForegroundColor White
Write-Host "  - Swagger API Docs:  http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "  - OpenAPI Schema:    http://127.0.0.1:8000/openapi.json" -ForegroundColor White
Write-Host "  - Strict Mode:       Zero Auto-Publishing (Local MP4s only)" -ForegroundColor Yellow
Write-Host "=====================================================================" -ForegroundColor Magenta
Write-Host "`nPress Enter or close this window when done."
Read-Host
