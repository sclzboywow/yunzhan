"""
文件管理API
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from app.models.file import FileListRequest, FileListResponse, FileStatsResponse, FileInfo
from app.services.file_service import FileService
from app.deps.auth import get_current_user
from app.deps.quota import quota_guard
from app.core.config import settings

import requests
import jwt
import urllib.parse
from app.core.db import SessionLocal
from app.services.token_store import TokenStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["文件管理"])


def get_file_service() -> FileService:
    """获取文件服务实例"""
    return FileService()


@router.get("/dedup/md5", summary="按MD5查重（存在则返回样本列表）")
async def dedup_by_md5(
    md5: str = Query(..., min_length=16, max_length=64, description="文件MD5"),
    sample_limit: int = Query(5, ge=1, le=20, description="返回样本条数上限"),
    file_service: FileService = Depends(get_file_service),
    current_user: dict = Depends(get_current_user),
):
    try:
        files = file_service.get_files_by_md5(md5.strip(), sample_limit)
        return {"exists": len(files) > 0, "count": len(files), "samples": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"dedup_md5_failed: {str(e)}")


@router.get("/list", response_model=FileListResponse, summary="获取文件列表")
async def get_file_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(1000, ge=1, le=1000, description="每页数量，最大1000"),
    file_path: Optional[str] = Query(None, description="文件路径过滤，支持模糊匹配"),
    category: Optional[int] = Query(None, description="文件类别过滤"),
    file_size_min: Optional[int] = Query(None, ge=0, description="最小文件大小（字节）"),
    file_size_max: Optional[int] = Query(None, ge=0, description="最大文件大小（字节）"),
    status: Optional[str] = Query(None, description="文件状态过滤"),
    order_by: str = Query("id", description="排序字段"),
    order_desc: bool = Query(True, description="是否降序排列"),
    file_service: FileService = Depends(get_file_service),
    current_user: dict = Depends(get_current_user)
):
    """
    获取文件列表，支持分页和多条件过滤
    
    - **page**: 页码，从1开始
    - **page_size**: 每页数量，最大1000
    - **file_path**: 文件路径过滤，支持模糊匹配
    - **category**: 文件类别过滤
    - **file_size_min**: 最小文件大小（字节）
    - **file_size_max**: 最大文件大小（字节）
    - **status**: 文件状态过滤
    - **order_by**: 排序字段（id, file_name, file_path, file_size, create_time, modify_time, export_time）
    - **order_desc**: 是否降序排列
    """
    try:
        request = FileListRequest(
            page=page,
            page_size=page_size,
            file_path=file_path,
            category=category,
            file_size_min=file_size_min,
            file_size_max=file_size_max,
            status=status,
            order_by=order_by,
            order_desc=order_desc
        )
        
        result = file_service.get_file_list(request)
        logger.info(f"用户 {getattr(current_user, 'username', 'unknown')} 查询文件列表，页码: {page}, 结果数: {len(result.files)}")
        return result
        
    except Exception as e:
        logger.error(f"获取文件列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")


@router.get("/stats", response_model=FileStatsResponse, summary="获取文件统计信息")
async def get_file_stats(
    file_service: FileService = Depends(get_file_service),
    current_user: dict = Depends(get_current_user)
):
    """
    获取文件统计信息，包括总数、大小、分类统计等
    """
    try:
        stats = file_service.get_file_stats()
        logger.info(f"用户 {getattr(current_user, 'username', 'unknown')} 查询文件统计信息")
        return stats
        
    except Exception as e:
        logger.error(f"获取文件统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文件统计失败: {str(e)}")


@router.get("/search", response_model=list[FileInfo], summary="搜索文件")
async def search_files(
    keyword: str = Query(..., description="搜索关键词"),
    limit: int = Query(100, ge=1, le=1000, description="返回结果数量限制"),
    file_service: FileService = Depends(get_file_service),
    current_user: dict = Depends(get_current_user)
):
    """
    根据关键词搜索文件（文件名或路径）
    """
    try:
        files = file_service.search_files(keyword, limit)
        logger.info(f"用户 {getattr(current_user, 'username', 'unknown')} 搜索文件: {keyword}, 结果数: {len(files)}")
        return files
        
    except Exception as e:
        logger.error(f"搜索文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索文件失败: {str(e)}")


@router.get("/categories", response_model=dict, summary="获取文件类别列表")
async def get_categories(
    file_service: FileService = Depends(get_file_service),
    current_user: dict = Depends(get_current_user)
):
    """
    获取所有文件类别及其统计信息
    """
    try:
        stats = file_service.get_file_stats()
        logger.info(f"用户 {getattr(current_user, 'username', 'unknown')} 查询文件类别列表")
        return {
            "categories": stats.category_stats,
            "total": stats.total_files
        }
        
    except Exception as e:
        logger.error(f"获取文件类别失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文件类别失败: {str(e)}")


@router.get("/statuses", response_model=dict, summary="获取文件状态列表")
async def get_statuses(
    file_service: FileService = Depends(get_file_service),
    current_user: dict = Depends(get_current_user)
):
    """
    获取所有文件状态及其统计信息
    """
    try:
        stats = file_service.get_file_stats()
        logger.info(f"用户 {getattr(current_user, 'username', 'unknown')} 查询文件状态列表")
        return {
            "statuses": stats.status_stats,
            "total": stats.total_files
        }
        
    except Exception as e:
        logger.error(f"获取文件状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文件状态失败: {str(e)}")


@router.get("/proxy_download", summary="通过票据代理下载（流式转发，支持 Range）")
async def proxy_download(
    ticket: str = Query(..., description="download_ticket 签发的票据"),
    range_header: Optional[str] = Query(None, alias="range", description="可选 Range 请求头的值，用于断点续传"),
    current_user: dict = Depends(get_current_user),
):
    """
    校验票据，向百度直链发起请求并流式转发给前端。
    为避免阻塞，采用 requests 的流式迭代，并保留状态码/头部（含 Accept-Ranges/Content-Range）。
    """
    try:
        # 校验与解析票据
        try:
            payload = jwt.decode(ticket, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="ticket_expired")
        except Exception:
            raise HTTPException(status_code=400, detail="ticket_invalid")

        dlink = payload.get("dlink")
        if not dlink:
            raise HTTPException(status_code=400, detail="dlink_missing_in_ticket")

        # 组装请求头（支持 Range）
        # 默认尽量贴近百度网盘客户端
        headers = {
            "User-Agent": "netdisk;7.2.8;PC",  # 常见可用 UA
            "Accept": "*/*",
            "Connection": "keep-alive",
            "Referer": "https://pan.baidu.com/",
        }
        # 允许通过 query param 传入 range=bytes=... 以兼容部分客户端不便设置请求头
        if range_header:
            headers["Range"] = range_header

        # 使用流式请求到百度直链
        def do_request(hdrs: dict):
            return requests.get(dlink, headers=hdrs, stream=True, timeout=30)

        try:
            upstream = do_request(headers)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"upstream_connect_failed: {str(e)}")

        # 如果出现 403，尝试使用更接近网页/客户端的头重试一次
        if upstream.status_code == 403:
            try:
                body_text = upstream.text[:512]
            except Exception:
                body_text = ""
            need_retry = False
            parsed_err = None
            if body_text:
                try:
                    import json as _json
                    parsed = _json.loads(body_text)
                    parsed_err = parsed if isinstance(parsed, dict) else None
                    if isinstance(parsed, dict) and parsed.get("error_code") in {31045, 31326}:
                        need_retry = True
                except Exception:
                    pass
            else:
                need_retry = True

            if need_retry:
                retry_headers = dict(headers)
                # 多一些常见浏览器特征
                retry_headers.update({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 NetDisk/7.2.8",
                    "Referer": "https://pan.baidu.com/disk/home",
                    "Origin": "https://pan.baidu.com",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "same-site",
                    "Sec-Fetch-Dest": "document",
                })
                if range_header and "Range" not in retry_headers:
                    retry_headers["Range"] = range_header
                # 若命中防盗链，强制添加基础 Range 与关闭压缩，避免中间层改写
                if (not range_header) and parsed_err and parsed_err.get("error_code") == 31326:
                    retry_headers.setdefault("Range", "bytes=0-")
                retry_headers.setdefault("Accept-Encoding", "identity")
                # 若为 31045，尝试追加公共态 access_token 到 dlink 再重试
                dlink_retry = dlink
                try:
                    if parsed_err and parsed_err.get("error_code") == 31045:
                        with SessionLocal() as _db:
                            store = TokenStore(_db)
                            access = store.ensure_fresh_service_token() or ""
                        if access:
                            urlp = urllib.parse.urlparse(dlink_retry)
                            q = urllib.parse.parse_qs(urlp.query, keep_blank_values=True)
                            if "access_token" not in q:
                                q["access_token"] = [access]
                                new_query = urllib.parse.urlencode({k: v[0] if isinstance(v, list) and v else v for k, v in q.items()}, doseq=True)
                                dlink_retry = urllib.parse.urlunparse(urlp._replace(query=new_query))
                except Exception:
                    pass
                try:
                    # 使用可能追加了 access_token 的 dlink 重试
                    upstream = requests.get(dlink_retry, headers=retry_headers, stream=True, timeout=30)
                except Exception as e:
                    raise HTTPException(status_code=502, detail=f"upstream_connect_failed_after_retry: {str(e)}")

        # 准备向前端转发的头
        forward_headers = {}
        for name, value in upstream.headers.items():
            lname = name.lower()
            # 透传与下载相关的重要头
            if lname in {"content-type", "content-length", "content-range", "accept-ranges", "content-disposition"}:
                forward_headers[name] = value

        # 构造生成器以逐块转发数据
        def iter_stream():
            for chunk in upstream.iter_content(chunk_size=64 * 1024):
                if chunk:
                    yield chunk

        status_code = upstream.status_code
        return StreamingResponse(iter_stream(), status_code=status_code, headers=forward_headers)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"代理下载失败: {e}")
        raise HTTPException(status_code=500, detail=f"proxy_download_failed: {str(e)}")


@router.get("/{file_id}", response_model=FileInfo, summary="获取文件详情")
async def get_file_detail(
    file_id: int,
    file_service: FileService = Depends(get_file_service),
    current_user: dict = Depends(get_current_user),
    _q = Depends(quota_guard),
):
    """
    根据文件ID获取文件详细信息
    """
    try:
        file_info = file_service.get_file_by_id(file_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        logger.info(f"用户 {getattr(current_user, 'username', 'unknown')} 查询文件详情: {file_id}")
        return file_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文件详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文件详情失败: {str(e)}")
