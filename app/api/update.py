"""
更新检查API接口
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from app.schemas.update import (
    UpdateCheckRequest, UpdateCheckResponse, 
    VersionCreateRequest, VersionInfo
)
from app.models.update import AppVersion, UpdateCheck
from app.deps.auth import get_current_user
from app.core.db import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/update", tags=["更新检查"])


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_client_ip(request: Request) -> str:
    """获取客户端IP地址"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"


def parse_version_code(version: str) -> int:
    """解析版本号为数字代码"""
    try:
        parts = version.split('.')
        code = 0
        for i, part in enumerate(parts[:3]):
            code += int(part) * (100 ** (2 - i))
        return code
    except (ValueError, IndexError):
        return 0


@router.post("/check", response_model=UpdateCheckResponse, summary="检查更新")
async def check_update(
    request: UpdateCheckRequest,
    db: Session = Depends(get_db),
    client_request: Request = None,
):
    """
    检查客户端是否有可用更新
    
    - **client_version**: 客户端当前版本号
    - **client_platform**: 客户端平台（web, desktop, mobile）
    - **user_agent**: 用户代理字符串（可选）
    """
    try:
        # 获取最新版本
        latest_version = db.query(AppVersion).filter(
            and_(
                AppVersion.platform == request.client_platform,
                AppVersion.is_latest == True
            )
        ).first()
        
        # 比较版本
        has_update = False
        force_update = False
        
        if latest_version:
            current_code = parse_version_code(request.client_version)
            latest_code = latest_version.version_code
            
            has_update = latest_code > current_code
            force_update = latest_version.is_force_update
        
        # 记录检查日志
        ip_address = get_client_ip(client_request) if client_request else None
        check_record = UpdateCheck(
            client_version=request.client_version,
            client_platform=request.client_platform,
            user_agent=request.user_agent,
            ip_address=ip_address,
            has_update=has_update,
            latest_version=latest_version.version if latest_version else None
        )
        
        db.add(check_record)
        db.commit()
        
        logger.info(f"更新检查 - 版本: {request.client_version}, 平台: {request.client_platform}, 有更新: {has_update}")
        
        return UpdateCheckResponse(
            has_update=has_update,
            current_version=request.client_version,
            latest_version=latest_version.version if latest_version else None,
            latest_version_info=VersionInfo.model_validate(latest_version.__dict__) if latest_version else None,
            force_update=force_update,
            message="发现新版本" if has_update else "当前已是最新版本"
        )
        
    except Exception as e:
        logger.error(f"检查更新失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查更新失败: {str(e)}")


@router.get("/check", response_model=UpdateCheckResponse, summary="检查更新（GET方式）")
async def check_update_get(
    client_version: str = Query(..., description="客户端版本号"),
    client_platform: str = Query(..., description="客户端平台"),
    user_agent: Optional[str] = Query(None, description="用户代理"),
    db: Session = Depends(get_db),
    client_request: Request = None,
):
    """
    通过GET方式检查更新（适用于简单的前端调用）
    """
    try:
        request = UpdateCheckRequest(
            client_version=client_version,
            client_platform=client_platform,
            user_agent=user_agent
        )
        
        # 获取最新版本
        latest_version = db.query(AppVersion).filter(
            and_(
                AppVersion.platform == client_platform,
                AppVersion.is_latest == True
            )
        ).first()
        
        # 比较版本
        has_update = False
        force_update = False
        
        if latest_version:
            current_code = parse_version_code(client_version)
            latest_code = latest_version.version_code
            
            has_update = latest_code > current_code
            force_update = latest_version.is_force_update
        
        # 记录检查日志
        ip_address = get_client_ip(client_request) if client_request else None
        check_record = UpdateCheck(
            client_version=client_version,
            client_platform=client_platform,
            user_agent=user_agent,
            ip_address=ip_address,
            has_update=has_update,
            latest_version=latest_version.version if latest_version else None
        )
        
        db.add(check_record)
        db.commit()
        
        logger.info(f"更新检查(GET) - 版本: {client_version}, 平台: {client_platform}, 有更新: {has_update}")
        
        return UpdateCheckResponse(
            has_update=has_update,
            current_version=client_version,
            latest_version=latest_version.version if latest_version else None,
            latest_version_info=VersionInfo.model_validate(latest_version.__dict__) if latest_version else None,
            force_update=force_update,
            message="发现新版本" if has_update else "当前已是最新版本"
        )
        
    except Exception as e:
        logger.error(f"检查更新失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查更新失败: {str(e)}")


@router.get("/latest", response_model=VersionInfo, summary="获取最新版本信息")
async def get_latest_version(
    platform: str = Query(..., description="平台类型"),
    db: Session = Depends(get_db),
):
    """
    获取指定平台的最新版本信息
    """
    try:
        latest_version = db.query(AppVersion).filter(
            and_(
                AppVersion.platform == platform,
                AppVersion.is_latest == True
            )
        ).first()
        
        if not latest_version:
            raise HTTPException(status_code=404, detail="未找到该平台的最新版本")
        
        return VersionInfo.model_validate(latest_version.__dict__)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取最新版本失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取最新版本失败: {str(e)}")


@router.post("/versions", response_model=VersionInfo, summary="创建新版本")
async def create_version(
    request: VersionCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    创建新版本（需要管理员权限）
    """
    try:
        # 如果设置为最新版本，先将其他版本设为非最新
        if request.is_latest:
            db.query(AppVersion).filter(
                AppVersion.platform == request.platform
            ).update({"is_latest": False})
        
        version = AppVersion(
            version=request.version,
            version_code=request.version_code,
            platform=request.platform,
            release_notes=request.release_notes,
            download_url=request.download_url,
            file_size=request.file_size,
            file_hash=request.file_hash,
            is_force_update=request.is_force_update,
            is_latest=request.is_latest
        )
        
        db.add(version)
        db.commit()
        db.refresh(version)
        
        logger.info(f"用户 {getattr(current_user, 'username', 'unknown')} 创建新版本: {request.version}")
        return VersionInfo.model_validate(version.__dict__)
        
    except Exception as e:
        logger.error(f"创建版本失败: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建版本失败: {str(e)}")


@router.get("/status", summary="更新服务状态")
async def get_update_status():
    """
    获取更新服务状态
    """
    return JSONResponse({
        "status": "ok",
        "message": "更新检查服务正常运行",
        "timestamp": "2024-01-01T00:00:00Z"
    })
