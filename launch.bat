@echo off
title SceneSolver Launcher
echo ====================================================
echo Starting SceneSolver Services...
echo ====================================================

:: Get the directory of the batch file itself to ensure correct relative paths
cd /d "%~dp0"

:: 1. Start Flask AI Service
echo [1/3] Starting Flask AI Service...
start "SceneSolver AI Service" cmd /k "cd scenesolver-ai-service && venv\Scripts\python ai_service.py"

:: Wait for Flask AI Service to start listening on port 5001
echo Waiting for Flask AI Service to initialize on port 5001 (loading models)...
powershell -Command "while (! (Test-NetConnection 127.0.0.1 -Port 5001 -WarningAction SilentlyContinue).TcpTestSucceeded) { Start-Sleep 2 }"
echo Flask AI Service is active!

:: 2. Start Node.js Backend
echo [2/3] Starting Node.js Backend (MongoDB should be running)...
start "SceneSolver Backend" cmd /k "cd scenesolver-backend && npm start"

:: 3. Start React Frontend
echo [3/3] Starting React Frontend...
start "SceneSolver Frontend" cmd /k "cd scenesolver-frontend && npm start"

echo ====================================================
echo All services have been launched! 
echo Keep their command prompt windows open while working.
echo.
echo - React Frontend:  http://localhost:3000
echo - Node.js Backend:  http://localhost:5000
echo - Flask AI Service: http://localhost:5001
echo ====================================================
pause
