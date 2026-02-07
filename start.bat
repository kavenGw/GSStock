@echo off
cd /d "%~dp0"
start /b python run.py
timeout /t 2 /nobreak >nul
start http://127.0.0.1:5000
