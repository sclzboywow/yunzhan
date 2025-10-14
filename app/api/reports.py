from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps.auth import get_current_user
from app.core.db import get_db
from app.models.report import PublicReport
from app.models.user import User


router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/public")
def report_public(
    target: str = Query(..., max_length=512, description="单个被举报对象标识（推荐 fsid）"),
    reason: str = Query(..., max_length=1024, description="举报原因（简述）"),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    target_norm = (target or "").strip()
    reason_norm = (reason or "").strip()
    if not target_norm or not reason_norm:
        raise HTTPException(status_code=400, detail="invalid_params")
    # 风控：单用户每日举报次数上限与节流（可调）
    DAILY_LIMIT = 3
    MIN_SECONDS_INTERVAL = 10
    # 统计今日次数
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).astimezone().date()
    cnt_today = db.execute(
        select(func.count()).select_from(PublicReport).where(
            PublicReport.user_id == current.id,
            PublicReport.day == today,
        )
    ).scalar() or 0
    if cnt_today >= DAILY_LIMIT:
        raise HTTPException(status_code=429, detail="report_daily_limit")
    # 最近一条时间间隔
    last = db.execute(
        select(PublicReport.created_at)
        .where(PublicReport.user_id == current.id)
        .order_by(PublicReport.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if last is not None:
        import time
        if (datetime.utcnow() - last).total_seconds() < MIN_SECONDS_INTERVAL:
            raise HTTPException(status_code=429, detail="report_too_frequent")
    # 去重：当日同目标只记一次
    exists = db.execute(
        select(PublicReport.id).where(
            PublicReport.user_id == current.id,
            PublicReport.target == target_norm,
            PublicReport.day == today,
        )
    ).scalar_one_or_none()
    if not exists:
        if cnt_today >= DAILY_LIMIT:
            raise HTTPException(status_code=429, detail="report_daily_limit")
        rec = PublicReport(
            target=target_norm,
            reason=reason_norm,
            username=current.username,
            user_id=current.id,
            day=today,
        )
        db.add(rec)
        db.commit()
    # 汇总该 target 被举报次数
    total = db.execute(
        select(func.count()).select_from(PublicReport).where(PublicReport.target == target_norm)
    ).scalar() or 0
    return JSONResponse({"status": "ok", "data": {"reported": True, "target": target_norm, "count": int(total)}})


@router.get("/public/count")
def report_public_count(
    target: str = Query(..., max_length=512),
    db: Session = Depends(get_db),
) -> JSONResponse:
    total = db.execute(select(func.count()).select_from(PublicReport).where(PublicReport.target == target.strip())).scalar() or 0
    return JSONResponse({"status": "ok", "data": {"target": target.strip(), "count": int(total)}})


