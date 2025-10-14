"""
文件数据模型
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    """文件信息模型"""
    id: int
    file_name: Optional[str] = None
    file_path: str
    file_size: Optional[int] = None
    fs_id: Optional[int] = None
    create_time: Optional[float] = None
    modify_time: Optional[float] = None
    file_md5: Optional[str] = None
    category: Optional[int] = None
    sync_id: Optional[str] = None
    status: Optional[str] = None
    export_time: Optional[float] = None

    class Config:
        from_attributes = True


class FileListRequest(BaseModel):
    """文件列表请求参数"""
    page: int = Field(1, ge=1, description="页码，从1开始")
    page_size: int = Field(1000, ge=1, le=1000, description="每页数量，最大1000")
    file_path: Optional[str] = Field(None, description="文件路径过滤，支持模糊匹配")
    category: Optional[int] = Field(None, description="文件类别过滤")
    file_size_min: Optional[int] = Field(None, ge=0, description="最小文件大小（字节）")
    file_size_max: Optional[int] = Field(None, ge=0, description="最大文件大小（字节）")
    status: Optional[str] = Field(None, description="文件状态过滤")
    order_by: str = Field("id", description="排序字段")
    order_desc: bool = Field(True, description="是否降序排列")


class FileListResponse(BaseModel):
    """文件列表响应"""
    files: list[FileInfo]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class FileStatsResponse(BaseModel):
    """文件统计信息"""
    total_files: int
    total_size: int
    category_stats: dict[int, int]
    status_stats: dict[str, int]
    path_stats: dict[str, int]
