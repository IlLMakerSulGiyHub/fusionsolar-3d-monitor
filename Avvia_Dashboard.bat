@echo off
title FusionSolar 3D Monitor - Avvio Automatico
cd /d "%~dp0"

echo ========================================================
echo    HUAWEI FUSIONSOLAR 3D MONITOR - AVVIO APPLICAZIONE
echo ========================================================
echo.

REM Verifica e installa eventuali librerie mancanti al primo avvio
pip show flask >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/2] Installazione librerie necessarie al primo avvio...
    pip install -r requirements.txt
)

echo [2/2] Apertura del browser su http://127.0.0.1:5000 ...
start "" "http://127.0.0.1:5000"

echo Server in esecuzione! Chiudi questa finestra quando hai finito.
echo.
python app.py
pause
