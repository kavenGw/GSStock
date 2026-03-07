@echo off
chcp 65001 >nul
cd /d "%~dp0"

set LLAMA_SERVER_ENABLED=false
if exist .env (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        if "%%a"=="LLAMA_SERVER_ENABLED" set LLAMA_SERVER_ENABLED=%%b
    )
)

if /i "%LLAMA_SERVER_ENABLED%"=="true" (
    if exist llama-server.bat (
        echo Starting llama-server...
        start "llama-server" llama-server.bat
    ) else (
        echo [WARN] LLAMA_SERVER_ENABLED=true but llama-server.bat not found
    )
)

title GSStock Server
echo Starting stock server...
python run.py
