from __future__ import annotations

import os
import hashlib
import shutil
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
import logging
from fastapi.responses import JSONResponse

from app.deps.auth import get_current_user
from app.models.user import User
from app.services.mcp_client import get_netdisk_client
from app.services.file_service import FileService


router = APIRouter(prefix="/upload", tags=["upload"])
logger = logging.getLogger(__name__)


def _path_starts_with_user_upload(p: str | None) -> bool:
    if not p:
        return False
    s = str(p).strip()
    return s == "/用户上传" or s.startswith("/用户上传/")


@router.post("")
async def upload_public(
    dir: str = Form(..., description="目标目录，必须在 /用户上传 下"),
    file: UploadFile = File(...),
    filename: Optional[str] = Form(None, description="保存文件名（可选，不填用原文件名）"),
    md5: Optional[str] = Form(None, description="可选：文件内容MD5，用于服务端前置查重"),
    enrich: bool = Form(False, description="是否补充 file_metas 权威信息（默认否）"),
    current: User = Depends(get_current_user),
) -> JSONResponse:
    target_dir = (dir or "").strip()
    if not _path_starts_with_user_upload(target_dir):
        raise HTTPException(status_code=400, detail="upload_dir_not_allowed")

    save_name = (filename or file.filename or "upload.bin").strip()
    if not save_name:
        save_name = "upload.bin"

    # 若提供 md5，先做全站查重，命中则直接返回，不执行上传
    try:
        if md5 and len(md5.strip()) >= 16:
            fs = FileService()
            md5_clean = md5.strip()
            cnt = fs.has_md5(md5_clean)
            logger.info("upload.precheck md5=%s count=%s dir=%s filename=%s", md5_clean, cnt, target_dir, save_name)
            if cnt > 0:
                logger.info("upload.duplicate md5=%s count=%s -> early_return", md5_clean, cnt)
                return JSONResponse({
                    "status": "duplicate",
                    "reason": "md5_exists",
                    "md5": md5_clean,
                    "count": cnt,
                }, status_code=200)
    except Exception:
        # 查重失败不阻塞上传
        pass

    # 将流保存到临时文件
    tmp_path = None
    local_size = 0
    try:
        with tempfile.NamedTemporaryFile(prefix="mcp_ul_", delete=False) as tmp:
            tmp_path = tmp.name
            # 流式写入，避免占用过多内存
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                tmp.write(chunk)
                local_size += len(chunk)

        # 若未提供 md5，则计算临时文件 md5 做一次前置查重
        try:
            md5_clean = (md5 or "").strip()
            if not md5_clean or len(md5_clean) < 16:
                h = hashlib.md5()
                with open(tmp_path, "rb") as f:
                    for part in iter(lambda: f.read(1024 * 1024), b""):
                        h.update(part)
                md5_clean = h.hexdigest()
                logger.info("upload.precheck.auto_md5 path=%s md5=%s", tmp_path, md5_clean)
            fs = FileService()
            cnt = fs.has_md5(md5_clean)
            logger.info("upload.precheck md5=%s count=%s dir=%s filename=%s", md5_clean, cnt, target_dir, save_name)
            if cnt > 0:
                logger.info("upload.duplicate md5=%s count=%s -> early_return", md5_clean, cnt)
                return JSONResponse({
                    "status": "duplicate",
                    "reason": "md5_exists",
                    "md5": md5_clean,
                    "count": cnt,
                }, status_code=200)
        except Exception:
            # 查重失败不阻塞上传
            pass

        # 调用公共态客户端执行上传
        client = get_netdisk_client(mode="public")
        remote_path = f"{target_dir.rstrip('/')}/{save_name}"
        data = client.upload_local(local_file_path=tmp_path, remote_path=remote_path)
        # 解析 SDK 结果，尽量获取 fs_id、md5、size、category、ctime/mtime
        fs_id: Optional[int] = None
        file_md5: Optional[str] = None
        size_val: Optional[int] = None
        category_val: Optional[int] = None
        ctime_val: Optional[int] = None
        mtime_val: Optional[int] = None
        try:
            # 兼容多种返回结构
            obj = data if isinstance(data, dict) else {}
            fs_id = int(obj.get("fs_id") or obj.get("fsid") or obj.get("fsId") or 0) or None
            file_md5 = (obj.get("md5") or obj.get("block_md5") or obj.get("md5sum") or None)
            # 常见返回字段
            try:
                size_val = int(obj.get("size") or obj.get("filesize") or obj.get("file_size") or 0) or None
            except Exception:
                size_val = None
            try:
                category_val = int(obj.get("category") or 0) or None
            except Exception:
                category_val = None
            try:
                ctime_val = int(obj.get("server_ctime") or obj.get("ctime") or 0) or None
            except Exception:
                ctime_val = None
            try:
                mtime_val = int(obj.get("server_mtime") or obj.get("mtime") or 0) or None
            except Exception:
                mtime_val = None
        except Exception:
            pass

        # 若开启 enrich，则通过 file_metas 补齐权威信息（默认关闭以提升速度）
        if enrich and fs_id and (not file_md5 or not size_val or category_val is None or not ctime_val or not mtime_val):
            try:
                metas = client.file_metas(fsids=json.dumps([int(fs_id)]))
                # 解析与脚本相同逻辑
                candidates = []
                if isinstance(metas, dict):
                    if isinstance(metas.get("list"), list):
                        candidates = metas.get("list", [])
                    elif isinstance(metas.get("data"), dict) and isinstance(metas["data"].get("list"), list):
                        candidates = metas["data"].get("list", [])
                for it in candidates:
                    try:
                        _fsid = int(it.get("fs_id") or it.get("fsid") or it.get("fsId") or 0)
                    except Exception:
                        _fsid = 0
                    if _fsid == int(fs_id):
                        _md5 = it.get("md5") or it.get("block_md5") or it.get("md5sum")
                        if isinstance(_md5, str) and len(_md5.strip()) >= 16:
                            file_md5 = _md5.strip()
                        try:
                            size_val = size_val or (int(it.get("size") or it.get("filesize") or it.get("file_size") or 0) or None)
                        except Exception:
                            pass
                        try:
                            category_val = category_val if category_val is not None else (int(it.get("category") or 0) or None)
                        except Exception:
                            pass
                        try:
                            ctime_val = ctime_val or (int(it.get("server_ctime") or it.get("ctime") or 0) or None)
                        except Exception:
                            pass
                        try:
                            mtime_val = mtime_val or (int(it.get("server_mtime") or it.get("mtime") or 0) or None)
                        except Exception:
                            pass
                            break
                logger.info("upload.file_metas fs_id=%s md5=%s size=%s category=%s ctime=%s mtime=%s", fs_id, file_md5, size_val, category_val, ctime_val, mtime_val)
            except Exception:
                pass

        # 上传成功即落库（幂等）
        try:
            fs = FileService()
            # 以“前端传入 md5”为最高优先级，其次 file_metas/SDK 返回
            final_md5 = (md5.strip() if isinstance(md5, str) and len(md5.strip()) >= 16 else None) or file_md5 or (md5_clean if 'md5_clean' in locals() else None)
            final_size = size_val or local_size or None
            fs.upsert_exported_file(
                file_name=save_name,
                file_path=remote_path,
                file_size=final_size,
                fs_id=fs_id,
                file_md5=final_md5,
                create_time=ctime_val,
                modify_time=mtime_val,
                category=category_val,
            )
            logger.info("upload.indexed path=%s fs_id=%s md5=%s size=%s category=%s ctime=%s", remote_path, fs_id, final_md5, final_size, category_val, ctime_val)
        except Exception:
            # 不影响主流程
            pass

        return JSONResponse({"status": "ok", "data": data, "remote_path": remote_path})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"upload_failed: {str(e)}")
    finally:
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


