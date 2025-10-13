from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.deps.auth import get_current_user
from app.models.user import User
from app.services.token_store import TokenStore
from app.services.ws_manager import manager
from app.core.config import get_settings


router = APIRouter(prefix="/oauth", tags=["oauth"])


@router.post("/device/start")
def device_start(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> JSONResponse:
    store = TokenStore(db)
    data = store.start_device_code()
    # WS 推送开始事件
    try:
        payload = {
            "type": "oauth_device",
            "phase": "start",
            "user_code": data.get("user_code"),
            "device_code": data.get("device_code"),
            "verification_url": data.get("verification_url") or data.get("verification_url_qrcode"),
            "interval": data.get("interval"),
            "expires_in": data.get("expires_in"),
        }
        # 异步发送
        import asyncio
        asyncio.get_event_loop().create_task(manager.send_to_user(current.id, payload))
    except Exception:
        pass
    return JSONResponse(data)


@router.post("/device/poll")
def device_poll(device_code: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> JSONResponse:
    store = TokenStore(db)
    try:
        data = store.poll_device_token(device_code)
        access = data.get("access_token") if isinstance(data, dict) else None
        refresh = data.get("refresh_token") if isinstance(data, dict) else None
        expires_in = data.get("expires_in") if isinstance(data, dict) else None
        if access:
            store.save_user_token(current.id, access, refresh, expires_in)
        status_str = "ok" if access else ("pending" if data else "pending")
    except Exception as e:
        # 不抛 500，返回结构化错误，便于前端重试
        return JSONResponse({"status": "error", "error": str(e)})
    # WS 推送进度/结果
    try:
        import asyncio
        payload = {
            "type": "oauth_device",
            "phase": "result",
            "status": status_str,
            "has_access": bool(access),
            "error": data.get("error") if isinstance(data, dict) else None,
        }
        asyncio.get_event_loop().create_task(manager.send_to_user(current.id, payload))
    except Exception:
        pass
    return JSONResponse({"status": status_str, "data": data})


@router.get("/token")
def token_masked(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> JSONResponse:
    store = TokenStore(db)
    tok = store.get_user_token(current.id)
    if not tok:
        return JSONResponse({"has_token": False})
    access, refresh, expires_at = tok
    def mask(s: str) -> str:
        return s[:4] + "***" + s[-4:] if len(s) > 8 else "***"
    return JSONResponse({
        "has_token": True,
        "access_token": mask(access),
        "refresh_token": mask(refresh) if refresh else None,
        "expires_at": expires_at.isoformat() if expires_at else None,
    })


# ---- Service (public) token device flow ----
@router.post("/service/device/start")
def service_device_start(admin_secret: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> JSONResponse:
    if admin_secret != get_settings().admin_secret:
        raise HTTPException(status_code=401, detail="invalid admin_secret")
    store = TokenStore(db)
    data = store.start_device_code()
    # 异步 WS 推送
    try:
        import asyncio
        asyncio.get_event_loop().create_task(manager.send_to_user(current.id, {"type":"oauth_device","phase":"service_start","user_code":data.get("user_code"),"verification_url":data.get("verification_url") or data.get("verification_url_qrcode")}))
    except Exception:
        pass
    return JSONResponse(data)


@router.post("/service/device/poll")
def service_device_poll(device_code: str, admin_secret: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> JSONResponse:
    if admin_secret != get_settings().admin_secret:
        raise HTTPException(status_code=401, detail="invalid admin_secret")
    store = TokenStore(db)
    try:
        data = store.poll_device_token(device_code)
        access = data.get("access_token") if isinstance(data, dict) else None
        refresh = data.get("refresh_token") if isinstance(data, dict) else None
        expires_in = data.get("expires_in") if isinstance(data, dict) else None
        status_str = "ok" if access else ("pending" if data else "pending")
        if access:
            store.save_service_token(access, refresh, expires_in)
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)})
    # WS 推送
    try:
        import asyncio
        asyncio.get_event_loop().create_task(manager.send_to_user(current.id, {"type":"oauth_device","phase":"service_result","status":status_str}))
    except Exception:
        pass
    return JSONResponse({"status": status_str})


# ---- Authorization Code flow (user) ----
MOBILE_HTML_BASE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>{title}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji"; margin: 0; padding: 24px; background: #0b1220; color: #e6edf3; }
    .card { max-width: 520px; margin: 8vh auto 0; background: #111a2b; border-radius: 16px; padding: 20px 18px; box-shadow: 0 10px 30px rgba(0,0,0,.35); }
    .title { font-size: 20px; margin: 0 0 6px; }
    .desc { font-size: 14px; opacity: .8; margin: 0 0 14px; line-height: 1.5; }
    .ok { color: #3fb950; }
    .err { color: #f85149; }
    code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; word-break: break-all; }
    .footer { margin-top: 16px; font-size: 12px; opacity: .65; }
    .btn { display: inline-block; margin-top: 8px; padding: 10px 14px; background: #1f6feb; color: #fff; border-radius: 10px; text-decoration: none; }
  </style>
  <script>
    // 支持在移动端内置浏览器里关闭当前页
    function closeWin(){ if (window.history.length > 1) history.back(); else window.close(); }
    setTimeout(closeWin, 2200);
  </script>
  </head>
  <body>
    <div class="card">
      <h1 class="title {cls}">{title}</h1>
      <p class="desc">{message}</p>
      {extra}
      <div class="footer mono">NetDisk OAuth Callback • {now}</div>
    </div>
  </body>
</html>
"""


@router.get("/callback", response_class=HTMLResponse)
def oauth_callback(code: str, state: str | None = None, db: Session = Depends(get_db)) -> HTMLResponse:
    """统一回调：通过 state 区分 user / service。

    - state == 'service' → 作为服务账户令牌保存
    - 其他或空 → 保存为当前用户令牌
    """
    store = TokenStore(db)
    # 交换 token
    if state == "service":
        data = store.exchange_code_to_service_token(code)
    else:
        data = store.exchange_code_to_token(code)
    access = data.get("access_token")
    refresh = data.get("refresh_token")
    expires_in = data.get("expires_in")
    if not access:
        # 对于用户态，直接把 code 返回给前端自行完成后续交换/保存
        html = MOBILE_HTML_BASE.format(
            title="授权失败",
            cls="err",
            message="未从提供方获得 access_token。请返回重试。",
            extra=f"<div class=\"mono\">code: <code>{code}</code></div>",
            now="{now}",
        ).replace("{now}", __import__("datetime").datetime.now().isoformat(timespec="seconds"))
        return HTMLResponse(html, status_code=400)
    # 保存
    if state == "service":
        store.save_service_token(access, refresh, expires_in)
        html = MOBILE_HTML_BASE.format(
            title="授权成功",
            cls="ok",
            message="服务端已保存凭证，您可以关闭此页面。",
            extra="",
            now="{now}",
        ).replace("{now}", __import__("datetime").datetime.now().isoformat(timespec="seconds"))
        return HTMLResponse(html)
    else:
        # 用户令牌交由前端负责：这里不落库，直接把 access/refresh 返回给前端（前端需安全保存）
        html = MOBILE_HTML_BASE.format(
            title="授权成功",
            cls="ok",
            message="已获取用户凭证，请在客户端完成后续绑定。",
            extra="",
            now="{now}",
        ).replace("{now}", __import__("datetime").datetime.now().isoformat(timespec="seconds"))
        return HTMLResponse(html)
    return HTMLResponse(MOBILE_HTML_BASE.format(
        title="完成",
        cls="ok",
        message="操作已完成。",
        extra="",
        now=__import__("datetime").datetime.now().isoformat(timespec="seconds")
    ))


# ---- Authorization Code flow (service/public) ----
# 兼容旧地址：保留但内部转发到统一逻辑
@router.get("/service/callback")
def oauth_service_callback_compat(code: str, db: Session = Depends(get_db)) -> JSONResponse:
    return oauth_callback(code=code, state="service", db=db)


@router.get("/service/token")
def service_token_masked(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> JSONResponse:
    store = TokenStore(db)
    tok = store.get_service_token()
    if not tok:
        return JSONResponse({"has_token": False})
    access, refresh, expires_at = tok
    def mask(s: str) -> str:
        return s[:4] + "***" + s[-4:] if len(s) > 8 else "***"
    return JSONResponse({
        "has_token": True,
        "access_token": mask(access),
        "refresh_token": mask(refresh) if refresh else None,
        "expires_at": expires_at.isoformat() if expires_at else None,
    })


# ---- User token upsert (frontend provides user access/refresh) ----
@router.post("/user/token/upsert")
def user_token_upsert(
    access_token: str,
    refresh_token: str | None = None,
    expires_in: int | None = None,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Persist user-provided tokens for later server-side MCP execution.

    Body form or JSON fields: access_token, refresh_token?, expires_in?
    """
    store = TokenStore(db)
    store.save_user_token(current.id, access_token, refresh_token, expires_in)
    return JSONResponse({"status": "ok"})

