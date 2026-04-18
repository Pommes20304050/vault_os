@echo off
title VaultOS - Installation
color 0A
echo ============================================
echo  VAULT-OS :: INSTALLATION
echo ============================================
echo.

echo [1/3] Aktualisiere pip...
python -m pip install --upgrade pip

echo.
echo [2/3] Deinstalliere opencv-python (Konflikt mit contrib)...
pip uninstall opencv-python -y 2>nul

echo.
echo [3/3] Installiere Abhaengigkeiten...
pip install -r requirements.txt

echo.
echo ============================================
echo  Installation abgeschlossen!
echo  Starte mit: start.bat
echo  Dashboard: http://localhost:5000
echo ============================================
pause
