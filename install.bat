@echo off
echo ====================================
echo    SAIT AI - Quick Setup
echo ====================================
echo.

echo [1/4] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker not found! Install Docker Desktop first.
    echo https://docs.docker.com/desktop/install/windows-install/
    pause
    exit /b 1
)
echo Docker OK!

echo.
echo [2/4] Creating data directories...
if not exist "data\uploads" mkdir data\uploads
if not exist "data\postgres" mkdir data\postgres

echo.
echo [3/4] Starting SAIT AI...
docker compose up -d

echo.
echo [4/4] Waiting for services to start...
timeout /t 30 /nobreak >nul

echo.
echo ====================================
echo    SAIT AI is ready!
echo ====================================
echo.
echo    Chat UI:    http://localhost:3005
echo    Backend:    http://localhost:8083
echo    Documents:  http://localhost:8083/documents
echo.
echo    Upload a PDF and start chatting!
echo ====================================
echo.
pause