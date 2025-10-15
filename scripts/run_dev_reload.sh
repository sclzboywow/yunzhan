#!/usr/bin/env bash
set -euo pipefail

# 环境变量（可被外部覆盖）
export APP_ENC_MASTER_KEY=${APP_ENC_MASTER_KEY:-IExFkb0be89F8dmUFK4pLTBoIwjFi8nv}
export APP_ADMIN_SECRET=${APP_ADMIN_SECRET:-y2oW3usi55pHCMvHIy3sEKqe}

cd /opt/web

# 激活虚拟环境
if [ -f .venv/bin/activate ]; then
	source .venv/bin/activate
fi

# 释放端口并以热重载模式运行
fuser -k 8000/tcp || true
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /opt/web
