@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: 读取 .env 中的 LLAMA_SERVER_ENABLED
set LLAMA_SERVER_ENABLED=false
if exist .env (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        if "%%a"=="LLAMA_SERVER_ENABLED" set LLAMA_SERVER_ENABLED=%%b
    )
)

:: 启动 llama-server
if /i "%LLAMA_SERVER_ENABLED%"=="true" (
    if exist llama-server.bat (
        echo 正在启动 llama-server...
        start "" cmd /k llama-server.bat
    ) else (
        echo [警告] LLAMA_SERVER_ENABLED=true 但未找到 llama-server.bat
    )
)

title GSStock Server
echo 正在启动股票管理工具...
python run.py
