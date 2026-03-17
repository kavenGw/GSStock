#!/bin/bash
# 强制拉取最新代码并重启 GSStock

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "=== 停止 GSStock ==="
./gsstock stop

echo "=== 拉取最新代码 ==="
git fetch --all
git reset --hard origin/main
chmod +x gsstock update_and_run.sh

echo "=== 安装/更新依赖 ==="
if [ ! -f venv/bin/pip ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi
venv/bin/pip install -r requirements.txt -q

echo "=== 启动 GSStock ==="
./gsstock start
