@echo off
chcp 65001 >nul
cd /d "%~dp0"
title GSStock Server
echo 正在启动股票管理工具...
python run.py
