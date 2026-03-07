@echo off
chcp 65001 >nul
title llama-server
llama-server -m D:\Models\Qwen_Qwen3.5-9B-Q4_K_M.gguf -ngl 99 -c 4096 --port 8080
