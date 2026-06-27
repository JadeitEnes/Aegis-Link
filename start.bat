@echo off
:: MediaPipe Publisher - yeni pencerede başlat
start "CWE Publisher" cmd /k "cd /d D:\Kod-Program\CWE && call venv\Scripts\activate.bat && python bridge\mp_publisher.py"

:: Python Bridge - yeni pencerede başlat
start "CWE Bridge" cmd /k "cd /d D:\Kod-Program\CWE && call venv\Scripts\activate.bat && cd bridge && uvicorn main:app --port 8000"

:: Tarayıcıyı aç
timeout /t 4 /nobreak >nul
start http://localhost:8000
