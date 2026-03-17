#!/bin/bash
# 强制拉取最新代码并重启 GSStock

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "=== 停止 GSStock ==="
./gsstock stop

echo "=== 拉取最新代码 ==="
git fetch --all
git reset --hard origin/main

echo "=== 安装/更新依赖 ==="
if [ -f venv/bin/pip ]; then
    venv/bin/pip install -r requirements.txt -q
else
    pip3 install -r requirements.txt -q
fi

echo "=== 启动 GSStock ==="
./gsstock start
