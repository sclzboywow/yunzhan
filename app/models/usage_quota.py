from __future__ import annotations

from datetime import datetime

from sqlalchemy import Date, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UsageQuota(Base):
    __tablename__ = "usage_quota"
    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_usage_quota_user_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    # YYYY-MM-DD in sqlite Date
    day: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


