from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse

from app.deps.auth import get_current_user
from app.models.user import User
from app.services.ws_manager import manager
from app.core.security import decode_access_token
from app.core.config import get_settings

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    # JWT from query param `token` or header `Authorization: Bearer <token>`
    token: str | None = None
    query_token = websocket.query_params.get("token")
    if query_token:
        token = query_token
    else:
        auth_header = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        await websocket.close(code=4401)
        return

    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
    except Exception:
        await websocket.close(code=4401)
        return

    settings = get_settings()
    await manager.connect(user_id, websocket)
    try:
        await manager.send_to_user(user_id, {"type": "welcome", "user_id": user_id})
        while True:
            # 读取消息并限流
            data = await websocket.receive_json()
            if not manager.check_rate_limit(websocket, settings.ws_max_messages_per_minute):
                await websocket.send_json({"type": "error", "reason": "rate_limit"})
                continue
            msg_type = data.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                manager.touch_pong(websocket)
                # 心跳超时检测（软性，下一次循环再判断）
                if manager.is_timed_out(websocket, settings.ws_heartbeat_timeout_seconds):
                    await websocket.close(code=4408)
                    break
            else:
                # Echo for now
                await websocket.send_json({"type": "echo", "data": data})
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)


@router.post("/ws/broadcast")
def ws_broadcast(message: dict, admin_secret: str) -> JSONResponse:
    settings = get_settings()
    if admin_secret != settings.admin_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin_secret")
    # 广播是异步函数，简单处理：在下一个事件循环中发送
    import asyncio

    async def _task():
        await manager.broadcast({"type": "broadcast", "data": message})

    asyncio.get_event_loop().create_task(_task())
    return JSONResponse({"status": "ok"})
