#!/bin/bash
# Trellis Manager 启动脚本
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

usage() {
    echo "用法: ./run.sh [dev|build]"
    echo ""
    echo "命令:"
    echo "  dev    开发模式：启动 Vite dev server（热更新生效），然后打开桌面壳"
    echo "  build  构建模式（默认）：先构建前端，再启动桌面壳"
    echo ""
    echo "环境变量:"
    echo "  TRELLIS_USE_DEV_SERVER=1  main.py 强制使用 Vite dev server"
}

MODE="${1:-build}"

case "$MODE" in
    dev)
        echo "=== 开发模式 ==="
        echo "启动 Vite dev server..."
        cd frontend && pnpm dev &
        VITE_PID=$!
        cd "$APP_DIR"
        # 退出桌面壳时清理 Vite，避免开发服务残留。
        trap 'kill "$VITE_PID" 2>/dev/null || true' EXIT INT TERM
        echo "Vite dev server PID: $VITE_PID"
        echo ""
        echo "=== 启动应用 ==="
        TRELLIS_USE_DEV_SERVER=1 python3 launcher.py
        ;;
    build|*)
        echo "=== 构建前端 ==="
        cd frontend && pnpm build && cd ..
        echo "=== 启动应用 ==="
        python3 launcher.py
        ;;
esac
