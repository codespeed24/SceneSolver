# Ensure we are in the script's directory
$PSScriptRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
Set-Location $PSScriptRoot

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "Starting SceneSolver Services..." -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# 1. Start Flask AI Service
Write-Host "[1/3] Starting Flask AI Service..." -ForegroundColor Green
Start-Process cmd -ArgumentList "/k cd scenesolver-ai-service && venv\Scripts\python ai_service.py" -WindowStyle Normal

# Wait for Flask AI Service to start listening on port 5001
Write-Host "Waiting for Flask AI Service to initialize on port 5001 (loading models)..." -ForegroundColor Yellow
while (-not (Test-NetConnection -ComputerName 127.0.0.1 -Port 5001 -WarningAction SilentlyContinue).TcpTestSucceeded) {
    Start-Sleep -Seconds 2
}
Write-Host "Flask AI Service is active!" -ForegroundColor Green

# 2. Start Node.js Backend
Write-Host "[2/3] Starting Node.js Backend..." -ForegroundColor Green
Start-Process cmd -ArgumentList "/k cd scenesolver-backend && npm start" -WindowStyle Normal

# 3. Start React Frontend
Write-Host "[3/3] Starting React Frontend..." -ForegroundColor Green
Start-Process cmd -ArgumentList "/k cd scenesolver-frontend && npm start" -WindowStyle Normal

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "All services have been launched!" -ForegroundColor Cyan
Write-Host "Keep the launched terminal windows open while using the app." -ForegroundColor Yellow
Write-Host "- React Frontend:  http://localhost:3000" -ForegroundColor Gray
Write-Host "- Node.js Backend:  http://localhost:5000" -ForegroundColor Gray
Write-Host "- Flask AI Service: http://localhost:5001" -ForegroundColor Gray
Write-Host "====================================================" -ForegroundColor Cyan
