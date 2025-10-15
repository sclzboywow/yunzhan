#!/usr/bin/env bash
set -euo pipefail

# 基础配置（可按需修改）
APP_HOST=${APP_HOST:-0.0.0.0}
APP_PORT=${APP_PORT:-8000}
WORKERS=${WORKERS:-2}
TIMEOUT=${TIMEOUT:-120}

# 机密/密钥（可通过 systemd Environment 覆盖）
export APP_ENC_MASTER_KEY=${APP_ENC_MASTER_KEY:-IExFkb0be89F8dmUFK4pLTBoIwjFi8nv}
export APP_ADMIN_SECRET=${APP_ADMIN_SECRET:-y2oW3usi55pHCMvHIy3sEKqe}

cd /opt/web

# 激活虚拟环境
if [ -f .venv/bin/activate ]; then
	source .venv/bin/activate
fi

# 启动前清理同端口进程（可选）
fuser -k ${APP_PORT}/tcp || true

# 使用 gunicorn 常驻管理 uvicorn worker
exec gunicorn app.main:app \
	--bind ${APP_HOST}:${APP_PORT} \
	--workers ${WORKERS} \
	--worker-class uvicorn.workers.UvicornWorker \
	--timeout ${TIMEOUT} \
	--access-logfile - \
	--error-logfile -
