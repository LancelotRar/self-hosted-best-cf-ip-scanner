#!/bin/sh
# 面板容器入口：启动 uvicorn（单镜像双入口的第二个入口）。
set -eu

exec python -m uvicorn panel.app:create_app \
  --factory \
  --host 0.0.0.0 \
  --port "${PANEL_PORT:-8080}" \
  --no-server-header
