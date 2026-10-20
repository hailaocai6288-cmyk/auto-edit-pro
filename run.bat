@echo off
chcp 65001 >nul
title AUTO EDIT PRO V7.5 - Dong lenh
cd /d "%~dp0"

where python >nul 2>nul || (echo [LOI] Chua cai Python 3.10+ ^& pause ^& exit /b 1)
python -m pip install -q -r requirements.txt

echo ========================================
echo   AUTO EDIT PRO V7.5 - Dang chay...
echo ========================================
echo.
python gemini_smart_cut.py %*

echo.
echo ----------------------------------------
echo Da ket thuc. Nhan phim bat ky de dong.
pause >nul
