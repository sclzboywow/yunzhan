from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import Base, engine, get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.core.config import settings


router = APIRouter(prefix="/auth", tags=["auth"])


@router.on_event("startup")
def _create_tables() -> None:
    Base.metadata.create_all(bind=engine)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserOut:
    exists = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=400, detail="username already exists")
    user = User(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="invalid username or password")
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.post("/set_role")
def set_role(username: str, role: str, admin_secret: str, db: Session = Depends(get_db)) -> dict:
    if admin_secret != settings.admin_secret:
        raise HTTPException(status_code=401, detail="invalid admin_secret")
    role_norm = role.lower().strip()
    if role_norm not in {"basic", "premium"}:
        raise HTTPException(status_code=400, detail="invalid_role")
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    user.role = role_norm
    db.add(user)
    db.commit()
    return {"status": "ok", "username": username, "role": role_norm}


