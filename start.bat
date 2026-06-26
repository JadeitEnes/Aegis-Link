@echo off
:: C++ Publisher - yeni pencerede başlat
start "CWE Publisher" cmd /k "set PATH=C:\msys64\ucrt64\bin;%PATH% && cd /d D:\Kod-Program\CWE\build && cwe_publisher.exe"

:: Python Bridge - yeni pencerede başlat
start "CWE Bridge" cmd /k "cd /d D:\Kod-Program\CWE && call venv\Scripts\activate.bat && cd bridge && uvicorn main:app --port 8000"

:: Tarayıcıyı aç
timeout /t 3 /nobreak >nul
start http://localhost:8000
