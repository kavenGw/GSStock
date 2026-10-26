#!/bin/bash
# 强制拉取最新代码并重启 GSStock
set -Eeuo pipefail
trap 'rc=$?; echo "[FAIL] 更新/启动失败，行 $LINENO，退出码 $rc" >&2; exit "$rc"' ERR

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
    if ! python3 -m venv venv 2>/dev/null; then
        echo "venv 模块缺失，尝试自动安装..."
        PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        if command -v apt-get >/dev/null 2>&1; then
            sudo apt-get update -qq
            sudo apt-get install -y -qq "python${PY_VER}-venv"
        else
            echo "错误：请手动安装 python3-venv 包"
            exit 1
        fi
        python3 -m venv venv || { echo "venv 创建失败"; exit 1; }
    fi
fi
venv/bin/pip install -r requirements.txt -q
venv/bin/pip install -U akshare -q

echo "=== 安装 Playwright Chromium 浏览器 ==="
READONLY_MODE=$(venv/bin/python -c 'from config import Config; print(int(Config.READONLY_MODE))')
if [ "$READONLY_MODE" = "1" ]; then
    echo "[SKIP] Chromium: 只读模式"
else
    venv/bin/python -m playwright install chromium --with-deps
fi

echo "=== 检查 PyTorch（AI走势预测，可选） ==="
if venv/bin/python -c "import torch" 2>/dev/null; then
    echo "PyTorch 已安装"
else
    echo "PyTorch 未安装，AI走势预测功能将不可用"
    echo "如需安装: venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu"
fi

echo "=== 启动 GSStock ==="
./gsstock start
