from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.deps.auth import get_current_user
from app.models.usage_quota import UsageQuota
from app.models.user import User


def _today_date_utc() -> datetime:
    now = datetime.now(timezone.utc).astimezone()
    return datetime(year=now.year, month=now.month, day=now.day)


def get_daily_quota_limit_for_user(user: User) -> int:
    role = (user.role or "basic").lower()
    if role == "premium":
        return int(settings.daily_quota_premium)
    return int(settings.daily_quota_basic)


def check_and_consume_quota(
    current_user: User,
    db: Session,
) -> None:
    day = _today_date_utc().date()
    limit = get_daily_quota_limit_for_user(current_user)

    # read row or create if missing
    row = db.execute(
        select(UsageQuota).where(UsageQuota.user_id == current_user.id, UsageQuota.day == day)
    ).scalar_one_or_none()
    if row is None:
        row = UsageQuota(user_id=current_user.id, day=day, total_count=0)
        db.add(row)
        db.flush()

    if row.total_count >= limit:
        raise HTTPException(status_code=429, detail="daily_quota_exceeded")

    row.total_count += 1
    db.add(row)
    db.commit()


def quota_guard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    check_and_consume_quota(current_user, db)


