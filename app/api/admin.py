from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models.usage_quota import UsageQuota
from app.models.user import User


router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(secret: str) -> None:
    if secret != settings.admin_secret:
        raise HTTPException(status_code=401, detail="invalid admin_secret")


@router.get("/quota")
def quota_get(username: str, admin_secret: str, db: Session = Depends(get_db)) -> JSONResponse:
    _require_admin(admin_secret)
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    rows = db.execute(select(UsageQuota).where(UsageQuota.user_id == user.id).order_by(UsageQuota.day.desc())).scalars().all()
    data = [
        {"day": r.day.isoformat(), "total_count": r.total_count} for r in rows
    ]
    return JSONResponse({"status": "ok", "username": username, "data": data})


@router.post("/quota/reset")
def quota_reset(username: str, day: str | None = None, admin_secret: str = Query(...), db: Session = Depends(get_db)) -> JSONResponse:
    _require_admin(admin_secret)
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    if day:
        try:
            target = datetime.fromisoformat(day).date()
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_day")
        db.execute(delete(UsageQuota).where(UsageQuota.user_id == user.id, UsageQuota.day == target))
    else:
        db.execute(delete(UsageQuota).where(UsageQuota.user_id == user.id))
    db.commit()
    return JSONResponse({"status": "ok"})


