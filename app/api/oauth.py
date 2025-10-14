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
from app.services.mcp_client import NetdiskClient
import secrets
import hashlib
import uuid


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


# ---- 自动扫码授权（无需JWT认证） ----
@router.post("/device/start_auto")
def device_start_auto(db: Session = Depends(get_db)) -> JSONResponse:
    """启动自动授权流程，无需JWT认证"""
    store = TokenStore(db)
    data = store.start_device_code()
    # 规范返回：提供前端可直接用于扫码的 URL，避免误用 verification_url 造成二次二维码
    scan_qr_url = data.get("qrcode_url") or data.get("verification_url_qrcode")
    if not scan_qr_url:
        # 官方未返回二维码直链时，生成一个图片直链（编码 verification_url + user_code + display=mobile）
        from urllib.parse import urlencode, quote
        verification_url = data.get("verification_url") or ""
        user_code = data.get("user_code") or ""
        # 将 user_code 和 display=mobile 作为 query 便于移动端展示
        target = verification_url
        if verification_url:
            sep = "&" if ("?" in verification_url) else "?"
            if user_code:
                target = f"{verification_url}{sep}user_code={quote(user_code)}&display=mobile"
            else:
                target = f"{verification_url}{sep}display=mobile"
        if target:
            # 使用公共二维码服务生成图片直链
            params = urlencode({"size": "300x300", "data": target})
            scan_qr_url = f"https://api.qrserver.com/v1/create-qr-code/?{params}"
        else:
            scan_qr_url = None
    # 额外提供移动端友好回调页链接（非二维码）：verification_url + display=mobile [+ user_code]
    verification_url = data.get("verification_url") or ""
    verification_url_mobile = None
    if verification_url:
        from urllib.parse import quote
        sep = "&" if ("?" in verification_url) else "?"
        if data.get("user_code"):
            verification_url_mobile = f"{verification_url}{sep}user_code={quote(data.get('user_code'))}&display=mobile"
        else:
            verification_url_mobile = f"{verification_url}{sep}display=mobile"

    normalized = {
        **data,
        "scan_qr_url": scan_qr_url,
        "verification_url_mobile": verification_url_mobile,
    }
    return JSONResponse(normalized)


@router.post("/device/poll_auto")
def device_poll_auto(device_code: str, device_fingerprint: str = None, db: Session = Depends(get_db)) -> JSONResponse:
    """轮询自动授权状态，自动创建用户账号"""
    store = TokenStore(db)
    
    try:
        # 轮询授权状态
        data = store.poll_device_token(device_code)
        
        if not isinstance(data, dict) or not data.get("access_token"):
            return JSONResponse({
                "status": "pending" if data else "error",
                "error": data.get("error") if isinstance(data, dict) else "授权未完成"
            })
        
        # 获取百度网盘用户信息
        access_token = data.get("access_token")
        client = NetdiskClient(access_token=access_token)
        user_info = client.get_user_info()
        
        if user_info.get("errno") != 0:
            return JSONResponse({
                "status": "error",
                "error": f"获取用户信息失败: {user_info.get('errmsg', '未知错误')}"
            })
        
        # 提取用户信息
        uk = user_info.get("uk")
        baidu_name = user_info.get("baidu_name", "")
        netdisk_name = user_info.get("netdisk_name", "")
        avatar_url = user_info.get("avatar_url", "")
        vip_type = user_info.get("vip_type", 0)
        
        if not uk:
            return JSONResponse({
                "status": "error",
                "error": "无法获取用户ID"
            })
        
        # 生成设备指纹（如果未提供）
        if not device_fingerprint:
            device_fingerprint = str(uuid.uuid4())
        
        # 创建用户名：uk + 设备指纹
        username = f"user_{uk}_{hashlib.md5(device_fingerprint.encode()).hexdigest()[:8]}"
        
        # 检查用户是否已存在
        existing_user = db.query(User).filter(User.username == username).first()
        
        if existing_user:
            # 用户已存在，更新token
            user_id = existing_user.id
            store.save_user_token(user_id, access_token, data.get("refresh_token"), data.get("expires_in"))
        else:
            # 创建新用户（字段白名单：仅使用 User 模型实际存在字段）
            password = secrets.token_urlsafe(16)  # 随机密码
            new_user = User(
                username=username,
                password_hash=hashlib.sha256(password.encode()).hexdigest(),
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            user_id = new_user.id
            
            # 保存token
            store.save_user_token(user_id, access_token, data.get("refresh_token"), data.get("expires_in"))
        
        # 生成JWT token
        from app.core.security import create_access_token
        jwt_token = create_access_token(subject=str(user_id))
        
        return JSONResponse({
            "status": "success",
            "user_id": user_id,
            "username": username,
            "jwt_token": jwt_token,
            "baidu_token": access_token,
            "user_info": {
                "uk": uk,
                "baidu_name": baidu_name,
                "netdisk_name": netdisk_name,
                "avatar_url": avatar_url,
                "vip_type": vip_type
            }
        })
        
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": f"处理授权失败: {str(e)}"
        })

