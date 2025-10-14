from __future__ import annotations

from datetime import datetime

from sqlalchemy import Date, DateTime, Integer, String, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PublicReport(Base):
    __tablename__ = "public_reports"
    __table_args__ = (
        Index("idx_public_reports_target", "target"),
        Index("idx_public_reports_created_at", "created_at"),
        # 业务去重：同一用户对同一目标，每天只计一次
        UniqueConstraint("user_id", "target", "day", name="uq_report_user_target_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 被举报对象标识：可放分享短链、fsid、路径或自定义ID
    target: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    # 举报原因（简短文本）
    reason: Mapped[str] = mapped_column(String(1024), nullable=False)
    # 举报人用户名（冗余存储便于审计）
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False, default=0)
    # 业务日期（用于日去重与汇总）
    day: Mapped[datetime] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


