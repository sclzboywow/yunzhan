from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("jti", name="uq_tickets_jti"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # JWT ID，一次性票据标识
    jti: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 票据作用域：user/public
    scope: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # 可选：签发用户ID（仅用于审计）
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    # 关联信息（便于溯源和调试）
    dlink: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    fsid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    issued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)



