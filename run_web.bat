@echo off
chcp 65001 >nul
title AUTO EDIT PRO V7.5 - Web (Chrome)
cd /d "%~dp0"

where python >nul 2>nul || (echo [LOI] Chua cai Python 3.10+ ^& pause ^& exit /b 1)
python -m pip install -q -r requirements.txt

echo Dang mo giao dien web tai http://localhost:8501 ...
start "" cmd /c "timeout /t 4 >nul & (start chrome http://localhost:8501 || start http://localhost:8501)"
python -m streamlit run app.py --server.headless true --server.port 8501
pause
