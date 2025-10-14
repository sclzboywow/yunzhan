from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    Critical variables should be provided via environment in production.
    """

    app_name: str = "NetDisk Backend"
    environment: str = "development"

    # Security
    jwt_secret_key: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expires_minutes: int = 60 * 24  # 24 hours

    # Database
    sqlite_path: str = "/opt/web/app_data/app.sqlite3"
    data_dir: str = "/opt/web/data"

    # WebSocket
    ws_heartbeat_timeout_seconds: int = 35
    ws_max_messages_per_minute: int = 240

    # Admin
    admin_secret: str = "change-admin"

    # MCP/Netdisk
    baidu_access_token: str | None = None
    mcp_base_path: str = "/opt/web/@netdisk/mcp/netdisk-mcp-server-stdio"
    baidu_client_id: str | None = None
    baidu_client_secret: str | None = None
    baidu_redirect_uri: str | None = "http://127.0.0.1:8000/oauth/callback"
    baidu_service_redirect_uri: str | None = None  # 可单独配置服务账户回调，如未配置将自动推断为 /oauth/service/callback
    baidu_app_id: str | None = None  # 分享等部分接口需要 appid

    # Crypto
    enc_master_key: str = "dev-master-key-32-bytes-please-change!!!"

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


# 全局设置实例
settings = get_settings()


