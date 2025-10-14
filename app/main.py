from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import sys, os

app = FastAPI(title="NetDisk Backend", version="0.1.0")

# CORS配置 - 允许PySide6桌面应用访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:*",       # 本地所有端口
        "http://127.0.0.1:*",      # 本地IP所有端口
        "file://*",                # 本地文件协议
        "*",                      # 开发环境允许所有来源
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", include_in_schema=False)
def _root() -> RedirectResponse:
    return RedirectResponse(url="/docs")

@app.get("/favicon.ico", include_in_schema=False)
def _favicon() -> Response:
    # 避免日志刷 404，如需可改为返回实际图标
    return Response(status_code=204)

@app.get("/health", tags=["system"])  # 健康检查
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})

# ---- Auth wiring ----
from app.api.auth import router as auth_router
from app.deps.auth import get_current_user
from app.schemas.auth import UserOut
from app.models.user import User


@app.get("/auth/me", response_model=UserOut, tags=["auth"])
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)


app.include_router(auth_router)

# ---- WebSocket wiring ----
from app.api.ws import router as ws_router


app.include_router(ws_router)

# ---- DB init on startup ----
from app.core.db import Base, engine


@app.on_event("startup")
def _ensure_tables() -> None:
    Base.metadata.create_all(bind=engine)

# ensure openapi_client import path (MCP sdk) BEFORE importing mcp routes
mcp_sdk_path = "/opt/web/@netdisk/mcp/netdisk-mcp-server-stdio"
if mcp_sdk_path not in sys.path and os.path.isdir(mcp_sdk_path):
    sys.path.append(mcp_sdk_path)

# ---- MCP wiring ----
from app.api.mcp import router as mcp_router
from app.api.oauth import router as oauth_router


app.include_router(mcp_router)
app.include_router(oauth_router)
