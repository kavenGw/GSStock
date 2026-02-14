@echo off
cd /d "%~dp0"
echo 正在启动股票管理工具...
echo.

REM 使用新窗口运行，保持窗口打开以便查看错误
start "GSStock Server" cmd /k "python run.py"

echo 等待服务器启动...
timeout /t 3 /nobreak >nul

REM 检查服务器是否启动成功
curl -s http://127.0.0.1:5000 >nul 2>&1
if %errorlevel%==0 (
    echo 服务器启动成功，正在打开浏览器...
    start http://127.0.0.1:5000
) else (
    echo 服务器可能未启动成功，请检查服务器窗口中的错误信息
    echo 如果没有问题，可手动访问: http://127.0.0.1:5000
    pause
)
