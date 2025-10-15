"""
更新检查数据模式
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class VersionInfo(BaseModel):
    """版本信息"""
    version: str = Field(..., description="版本号")
    version_code: int = Field(..., description="版本代码")
    platform: str = Field(..., description="平台类型")
    release_notes: Optional[str] = Field(None, description="发布说明")
    download_url: Optional[str] = Field(None, description="下载链接")
    file_size: Optional[int] = Field(None, description="文件大小")
    file_hash: Optional[str] = Field(None, description="文件哈希值")
    is_force_update: bool = Field(False, description="是否强制更新")
    is_latest: bool = Field(False, description="是否为最新版本")
    created_at: datetime = Field(..., description="创建时间")


class UpdateCheckRequest(BaseModel):
    """更新检查请求"""
    client_version: str = Field(..., description="客户端版本号")
    client_platform: str = Field(..., description="客户端平台")
    user_agent: Optional[str] = Field(None, description="用户代理")


class UpdateCheckResponse(BaseModel):
    """更新检查响应"""
    has_update: bool = Field(..., description="是否有更新")
    current_version: str = Field(..., description="当前版本")
    latest_version: Optional[str] = Field(None, description="最新版本")
    latest_version_info: Optional[VersionInfo] = Field(None, description="最新版本信息")
    force_update: bool = Field(False, description="是否强制更新")
    message: Optional[str] = Field(None, description="提示信息")


class VersionCreateRequest(BaseModel):
    """创建版本请求"""
    version: str = Field(..., description="版本号")
    version_code: int = Field(..., description="版本代码")
    platform: str = Field(..., description="平台类型")
    release_notes: Optional[str] = Field(None, description="发布说明")
    download_url: Optional[str] = Field(None, description="下载链接")
    file_size: Optional[int] = Field(None, description="文件大小")
    file_hash: Optional[str] = Field(None, description="文件哈希值")
    is_force_update: bool = Field(False, description="是否强制更新")
    is_latest: bool = Field(False, description="是否为最新版本")
