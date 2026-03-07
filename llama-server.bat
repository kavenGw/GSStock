@echo off
chcp 65001 >nul
title llama-server

:loop
echo [%date% %time%] Starting llama-server...
powershell -Command "llama-server -m D:\Models\Qwen_Qwen3.5-9B-Q4_K_M.gguf -ngl 99 -c 4096 --port 8080 --log-verbose 2>&1"
echo.
echo [%date% %time%] llama-server exited, restarting in 3 seconds...
timeout /t 3 /nobreak >nul
goto loop
