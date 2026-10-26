@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title GSStock Server
set PYTHONUTF8=1
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" startup.py
) else (
    python startup.py
)
exit /b %errorlevel%
