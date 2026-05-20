#!/bin/bash
# 构建前端并启动 Trellis Manager
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "=== 构建前端 ==="
cd frontend && npm run build && cd ..

echo "=== 启动应用 ==="
python3 launcher.py
