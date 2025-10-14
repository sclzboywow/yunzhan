from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps.auth import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.models.usage_quota import UsageQuota
from app.deps.quota import get_daily_quota_limit_for_user


router = APIRouter(prefix="/quota", tags=["quota"])


def _today_date_utc():
    now = datetime.now(timezone.utc).astimezone()
    return now.date()


@router.get("/today")
def quota_today(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> JSONResponse:
    day = _today_date_utc()
    row = db.execute(
        select(UsageQuota).where(UsageQuota.user_id == current.id, UsageQuota.day == day)
    ).scalar_one_or_none()
    used = int(row.total_count) if row else 0
    total = int(get_daily_quota_limit_for_user(current))
    left = max(total - used, 0)
    return JSONResponse({
        "status": "ok",
        "data": {
            "day": day.isoformat(),
            "role": current.role,
            "used": used,
            "total": total,
            "left": left,
        }
    })


