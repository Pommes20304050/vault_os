@echo off
title VAULT-OS :: Launcher
color 0A
cd /d "%~dp0"

echo ============================================
echo  VAULT-OS :: START
echo ============================================
echo.

:: Alte Instanz auf Port 5000 beenden
echo [1/3] Beende alte Instanzen auf Port 5000...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr " :5000 "') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul
echo    OK.

echo.
echo [2/3] Starte Server...
start "VAULT-OS Server" /MIN cmd /c "python app.py & pause"
echo    Gestartet (laeuft im Hintergrund).

echo.
echo [3/3] Warte bis Server bereit ist...
:WAIT
timeout /t 1 /nobreak >nul
powershell -NoProfile -Command ^
  "try{$r=(Invoke-WebRequest 'http://127.0.0.1:5000' -UseBasicParsing -TimeoutSec 2).StatusCode;exit 0}catch{exit 1}" >nul 2>&1
if %errorlevel% neq 0 goto WAIT
echo    Server ist bereit!

echo.
:: Chrome bevorzugen, sonst Edge, sonst Standard-Browser
set URL=http://127.0.0.1:5000
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --new-window %URL%
    goto OPEN_OK
)
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" --new-window %URL%
    goto OPEN_OK
)
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --new-window %URL%
    goto OPEN_OK
)
start %URL%

:OPEN_OK
echo ============================================
echo  Dashboard geoeffnet: %URL%
echo  Dieses Fenster kann geschlossen werden.
echo  Server laeuft weiter im Hintergrund.
echo ============================================
echo.
pause
