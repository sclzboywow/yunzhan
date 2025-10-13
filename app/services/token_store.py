from __future__ import annotations

from datetime import datetime, timedelta, timezone
import threading
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_from_base64, encrypt_to_base64
from app.core.db import SessionLocal
from app.core.config import get_settings
from app.models.token import OAuthToken
from app.models.user import User
from openapi_client import ApiClient, Configuration
from openapi_client.api.auth_api import AuthApi


class TokenStore:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        # process-wide mutex to avoid concurrent refresh
        # note: in multi-process deployment, prefer DB-based advisory lock
        if not hasattr(TokenStore, "_service_refresh_lock"):
            TokenStore._service_refresh_lock = threading.Lock()

    def get_user_token(self, user_id: int) -> Optional[tuple[str, Optional[str], Optional[datetime]]]:
        rec = self.db.execute(select(OAuthToken).where(OAuthToken.user_id == user_id, OAuthToken.is_service == 0)).scalar_one_or_none()
        if not rec:
            return None
        access = decrypt_from_base64(rec.access_token_enc)
        refresh = decrypt_from_base64(rec.refresh_token_enc) if rec.refresh_token_enc else None
        expires_at = rec.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            # normalize to UTC-aware
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return access, refresh, expires_at

    def save_user_token(self, user_id: int, access_token: str, refresh_token: Optional[str], expires_in: Optional[int]) -> None:
        expires_at = None
        if expires_in:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        enc_access = encrypt_to_base64(access_token)
        enc_refresh = encrypt_to_base64(refresh_token) if refresh_token else None
        rec = self.db.execute(select(OAuthToken).where(OAuthToken.user_id == user_id, OAuthToken.is_service == 0)).scalar_one_or_none()
        if rec:
            rec.access_token_enc = enc_access
            rec.refresh_token_enc = enc_refresh
            rec.expires_at = expires_at
        else:
            rec = OAuthToken(user_id=user_id, access_token_enc=enc_access, refresh_token_enc=enc_refresh, expires_at=expires_at)
            self.db.add(rec)
        self.db.commit()

    def ensure_fresh_access_token(self, user_id: int) -> Optional[str]:
        tok = self.get_user_token(user_id)
        if not tok:
            return None
        access, refresh, expires_at = tok
        now = datetime.now(timezone.utc)
        # 刷新窗口：提前 30 天刷新
        refresh_window = timedelta(days=30)
        if not expires_at or expires_at - now > refresh_window:
            return access
        # refresh
        if not refresh:
            return access
        cfg = Configuration()
        with ApiClient(cfg) as api_client:
            api = AuthApi(api_client)
            try:
                resp = api.oauth_token_refresh_token(refresh_token=refresh, client_id=self.settings.baidu_client_id or "", client_secret=self.settings.baidu_client_secret or "")
            except Exception:
                # 惰性修复：刷新失败直接返回现有 access（由上层决定是否重试/重新授权）
                return access
            access_new = resp.get("access_token")
            refresh_new = resp.get("refresh_token", refresh)
            expires_in = resp.get("expires_in")
            if access_new:
                self.save_user_token(user_id, access_new, refresh_new, expires_in)
                return access_new
        return access

    def start_device_code(self) -> dict:
        cfg = Configuration()
        with ApiClient(cfg) as api_client:
            api = AuthApi(api_client)
            scope = "basic,netdisk"
            resp = api.oauth_token_device_code(client_id=self.settings.baidu_client_id or "", scope=scope)
            # 转为可序列化 dict
            return resp.to_dict() if hasattr(resp, "to_dict") else dict(resp)

    def poll_device_token(self, device_code: str) -> dict:
        cfg = Configuration()
        with ApiClient(cfg) as api_client:
            api = AuthApi(api_client)
            resp = api.oauth_token_device_token(code=device_code, client_id=self.settings.baidu_client_id or "", client_secret=self.settings.baidu_client_secret or "")
            return resp.to_dict() if hasattr(resp, "to_dict") else dict(resp)

    # ---- Authorization Code flow ----
    def exchange_code_to_token(self, code: str) -> dict:
        cfg = Configuration()
        with ApiClient(cfg) as api_client:
            api = AuthApi(api_client)
            resp = api.oauth_token_code2token(
                code=code,
                client_id=self.settings.baidu_client_id or "",
                client_secret=self.settings.baidu_client_secret or "",
                redirect_uri=self.settings.baidu_redirect_uri or "",
            )
            return resp.to_dict() if hasattr(resp, "to_dict") else dict(resp)

    def exchange_code_to_service_token(self, code: str) -> dict:
        # 同用户流程，区别在保存位置
        return self.exchange_code_to_token(code)

    # ---- Service (public) token management ----
    def get_service_token(self) -> Optional[tuple[str, Optional[str], Optional[datetime]]]:
        rec = self.db.execute(select(OAuthToken).where(OAuthToken.is_service == 1)).scalar_one_or_none()
        if not rec:
            return None
        access = decrypt_from_base64(rec.access_token_enc)
        refresh = decrypt_from_base64(rec.refresh_token_enc) if rec.refresh_token_enc else None
        expires_at = rec.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return access, refresh, expires_at

    def save_service_token(self, access_token: str, refresh_token: Optional[str], expires_in: Optional[int]) -> None:
        expires_at = None
        if expires_in:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        enc_access = encrypt_to_base64(access_token)
        enc_refresh = encrypt_to_base64(refresh_token) if refresh_token else None
        rec = self.db.execute(select(OAuthToken).where(OAuthToken.is_service == 1)).scalar_one_or_none()
        if rec:
            rec.access_token_enc = enc_access
            rec.refresh_token_enc = enc_refresh
            rec.expires_at = expires_at
        else:
            rec = OAuthToken(user_id=None, is_service=1, access_token_enc=enc_access, refresh_token_enc=enc_refresh, expires_at=expires_at)
            self.db.add(rec)
        self.db.commit()

    def ensure_fresh_service_token(self) -> Optional[str]:
        tok = self.get_service_token()
        if not tok:
            return None
        access, refresh, expires_at = tok
        now = datetime.now(timezone.utc)
        refresh_window = timedelta(days=30)
        if not expires_at or expires_at - now > refresh_window:
            return access
        if not refresh:
            return access
        # 全局互斥，避免并发刷新
        lock: threading.Lock = TokenStore._service_refresh_lock  # type: ignore[attr-defined]
        if not lock.acquire(blocking=False):
            # 有其他线程在刷新，返回旧 access（上层可稍后重试）
            return access
        try:
            cfg = Configuration()
            with ApiClient(cfg) as api_client:
                api = AuthApi(api_client)
                try:
                    resp = api.oauth_token_refresh_token(refresh_token=refresh, client_id=self.settings.baidu_client_id or "", client_secret=self.settings.baidu_client_secret or "")
                except Exception:
                    # 惰性修复：刷新失败（含 used/invalid_grant）不重试旧 refresh
                    return access
                access_new = resp.get("access_token")
                refresh_new = resp.get("refresh_token", refresh)
                expires_in = resp.get("expires_in")
                if access_new:
                    self.save_service_token(access_new, refresh_new, expires_in)
                    return access_new
                return access
        finally:
            try:
                lock.release()
            except Exception:
                pass


