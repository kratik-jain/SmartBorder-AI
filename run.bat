@echo off
setlocal EnableExtensions
cd /d %~dp0
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
set PORT=8000
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if %ERRORLEVEL% EQU 0 set PORT=8001
echo SMARTBORDER AI starting on http://127.0.0.1:%PORT%
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port %PORT%
