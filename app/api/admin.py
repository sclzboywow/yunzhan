from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models.usage_quota import UsageQuota
from app.models.ticket import Ticket
from datetime import datetime, timedelta
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


# ---- Tickets management ----
@router.get("/tickets")
def tickets_list(
    admin_secret: str = Query(...),
    scope: str | None = None,
    consumed: bool | None = None,
    page: int = 1,
    page_size: int = 100,
    db: Session = Depends(get_db),
) -> JSONResponse:
    _require_admin(admin_secret)
    q = db.query(Ticket)
    if scope:
        q = q.filter(Ticket.scope == scope)
    if consumed is not None:
        if consumed:
            q = q.filter(Ticket.consumed_at.isnot(None))
        else:
            q = q.filter(Ticket.consumed_at.is_(None))
    q = q.order_by(Ticket.id.desc())
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    data = []
    for t in items:
        data.append({
            "jti": t.jti,
            "scope": t.scope,
            "user_id": t.user_id,
            "issued_at": t.issued_at.isoformat() if t.issued_at else None,
            "expires_at": t.expires_at.isoformat() if t.expires_at else None,
            "consumed_at": t.consumed_at.isoformat() if t.consumed_at else None,
            "fsid": t.fsid,
        })
    return JSONResponse({"status": "ok", "total": total, "items": data})


@router.post("/tickets/revoke")
def tickets_revoke(jti: str, admin_secret: str = Query(...), db: Session = Depends(get_db)) -> JSONResponse:
    _require_admin(admin_secret)
    t = db.query(Ticket).filter(Ticket.jti == jti).first()
    if not t:
        raise HTTPException(status_code=404, detail="ticket_not_found")
    if t.consumed_at is None:
        t.consumed_at = datetime.utcnow()
        db.add(t)
        db.commit()
    return JSONResponse({"status": "ok"})


@router.post("/tickets/gc")
def tickets_gc(
    admin_secret: str = Query(...),
    keep_days: int = 7,
    db: Session = Depends(get_db)
) -> JSONResponse:
    _require_admin(admin_secret)
    cutoff = datetime.utcnow() - timedelta(days=keep_days)
    # 清理过期或已消费且较久的票据
    # 对 sqlite 使用简单删除策略
    from sqlalchemy import delete
    db.execute(
        delete(Ticket).where(
            (Ticket.expires_at < datetime.utcnow()) |
            ((Ticket.consumed_at.isnot(None)) & (Ticket.consumed_at < cutoff))
        )
    )
    db.commit()
    return JSONResponse({"status": "ok"})

