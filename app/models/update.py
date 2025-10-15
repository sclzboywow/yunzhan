"""
更新检查数据模型
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from app.core.db import Base


class AppVersion(Base):
    """应用版本信息表"""
    __tablename__ = "app_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(50), unique=True, index=True, nullable=False, comment="版本号")
    version_code = Column(Integer, nullable=False, comment="版本代码（用于比较）")
    platform = Column(String(20), nullable=False, comment="平台类型：web, desktop, mobile")
    release_notes = Column(Text, comment="发布说明")
    download_url = Column(String(500), comment="下载链接")
    file_size = Column(Integer, comment="文件大小（字节）")
    file_hash = Column(String(128), comment="文件哈希值")
    is_force_update = Column(Boolean, default=False, comment="是否强制更新")
    is_latest = Column(Boolean, default=False, comment="是否为最新版本")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")


class UpdateCheck(Base):
    """更新检查记录表"""
    __tablename__ = "update_checks"
    
    id = Column(Integer, primary_key=True, index=True)
    client_version = Column(String(50), nullable=False, comment="客户端版本")
    client_platform = Column(String(20), nullable=False, comment="客户端平台")
    user_agent = Column(String(500), comment="用户代理")
    ip_address = Column(String(45), comment="IP地址")
    has_update = Column(Boolean, default=False, comment="是否有更新")
    latest_version = Column(String(50), comment="最新版本号")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="检查时间")
