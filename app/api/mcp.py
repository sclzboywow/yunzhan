from __future__ import annotations

from typing import Optional
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app.deps.auth import get_current_user
from app.models.user import User
from app.deps.quota import check_and_consume_quota
from app.core.db import get_db
from sqlalchemy.orm import Session
from app.services.mcp_client import get_netdisk_client


router = APIRouter(prefix="/mcp", tags=["mcp"])
logger = logging.getLogger(__name__)


@router.get("/user/quota")
def user_quota(current: User = Depends(get_current_user)) -> JSONResponse:
    client = get_netdisk_client(user_id=current.id, mode="user")
    data = client.quota()
    return JSONResponse(data)


@router.get("/user/list")
def user_list_files(
    dir: str = Query("/", alias="dir"),
    limit: int = 100,
    order: str = "time",
    desc: int = 1,
    current: User = Depends(get_current_user),
) -> JSONResponse:
    client = get_netdisk_client(user_id=current.id, mode="user")
    data = client.list_files(dir_path=dir, limit=limit, order=order, desc=desc)
    return JSONResponse(data)


@router.get("/public/quota")
def public_quota(current: User = Depends(get_current_user)) -> JSONResponse:
    try:
        client = get_netdisk_client(mode="public")
        data = client.quota()
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=200)


@router.get("/public/list")
def public_list_files(
    dir: str = Query("/", alias="dir"),
    limit: int = 100,
    order: str = "time",
    desc: int = 1,
    current: User = Depends(get_current_user),
) -> JSONResponse:
    client = get_netdisk_client(mode="public")
    data = client.list_files(dir_path=dir, limit=limit, order=order, desc=desc)
    return JSONResponse(data)


# ---- Generic exec (allowlist) ----

ALLOWED_OPS: set[str] = {
    # 基础信息
    "quota",
    # 文件列表/检索
    "list_files",
    "list_images",
    "list_videos",
    "list_docs",
    "list_bt",
    "list_category",
    "search_filename",
    "search_semantic",
    # 文件管理
    "mkdir",
    "delete",
    "move",
    "rename",
    "copy",
    # 上传
    "upload_local",
    "upload_url",
    "upload_text",
    # 批量上传
    "upload_batch_local",
    "upload_batch_url",
    "upload_batch_text",
    # 播单/最近
    "playlist",
    "recent",
    # 扫描/元信息
    "list_all",
    "file_metas",
    "download_links",
    "share_create",
    # 下载票据
    "download_ticket",
    # 离线下载
    "offline_add",
    "offline_status",
    "offline_cancel",
}


def _exec_with_client(op: str, args: dict, client) -> dict:
    # 已实现的操作
    if op == "quota":
        return client.quota()
    if op == "list_files":
        return client.list_files(
            dir_path=args.get("dir", "/"),
            limit=int(args.get("limit", 100)),
            order=str(args.get("order", "time")),
            desc=int(args.get("desc", 1)),
        )
    if op == "list_images":
        return client.list_images(
            parent_path=args.get("dir", "/"),
            page=int(args.get("page", 1)),
            num=int(args.get("num", 50)),
            order=str(args.get("order", "time")),
            desc=str(args.get("desc", "1")),
        )
    if op == "list_docs":
        return client.list_docs(
            parent_path=args.get("dir", "/"),
            page=int(args.get("page", 1)),
            num=int(args.get("num", 50)),
            order=str(args.get("order", "time")),
            desc=str(args.get("desc", "1")),
        )
    if op == "search_filename":
        return client.search_filename(
            key=str(args.get("key", "")),
            dir_path=str(args.get("dir", "/")),
            page=str(args.get("page", "1")),
            num=str(args.get("num", "50")),
            recursion=str(args.get("recursion", "1")),
        )
    if op == "list_videos":
        return client.list_videos(
            path=str(args.get("path", "/")),
            recursion=int(args.get("recursion", 0)),
            start=int(args.get("start", 0)),
            limit=int(args.get("limit", 100)),
            order=str(args.get("order", "time")),
            desc=int(args.get("desc", 1)),
        )
    if op == "list_bt":
        return client.list_bt(
            path=str(args.get("path", "/")),
            recursion=int(args.get("recursion", 0)),
            start=int(args.get("start", 0)),
            limit=int(args.get("limit", 100)),
            order=str(args.get("order", "time")),
            desc=int(args.get("desc", 1)),
        )
    if op == "list_category":
        return client.list_category(
            path=str(args.get("path", "/")),
            recursion=int(args.get("recursion", 1)),
            limit=int(args.get("limit", 1000)),
        )
    if op == "recent":
        return client.recent(
            path=str(args.get("path", "/")),
            limit=int(args.get("limit", 50)),
        )
    if op == "mkdir":
        path_val = str(args.get("path", "/新建文件夹"))
        if args.get("rtype") is not None:
            return client.mkdir(path=path_val, rtype=int(args.get("rtype")))
        return client.mkdir(path=path_val)
    if op == "search_semantic":
        return client.search_semantic(
            query=str(args.get("query", "")),
            dir_path=str(args.get("dir", "/")),
            page=str(args.get("page", "1")),
            num=str(args.get("num", "50")),
            recursion=str(args.get("recursion", "1")),
        )
    if op == "upload_local":
        return client.upload_local(
            local_file_path=str(args.get("local_file_path", "")),
            remote_path=str(args.get("remote_path", "/来自：mcp_server/upload.bin")),
        )
    if op == "upload_url":
        return client.upload_url(
            url=str(args.get("url", "")),
            dir_path=str(args.get("dir", "/")),
            filename=args.get("filename"),
        )
    if op == "upload_text":
        return client.upload_text(
            content=str(args.get("content", "")),
            dir_path=str(args.get("dir", "/")),
            filename=args.get("filename"),
        )
    if op == "upload_batch_local":
        file_list = args.get("file_list", [])
        max_concurrent = int(args.get("max_concurrent", 3))
        return client.upload_batch_local(file_list, max_concurrent)
    if op == "upload_batch_url":
        url_list = args.get("url_list", [])
        max_concurrent = int(args.get("max_concurrent", 3))
        return client.upload_batch_url(url_list, max_concurrent)
    if op == "upload_batch_text":
        text_list = args.get("text_list", [])
        max_concurrent = int(args.get("max_concurrent", 3))
        return client.upload_batch_text(text_list, max_concurrent)
    if op == "delete":
        return client.fm_delete(
            filelist_json=str(args.get("filelist", "[]")),
            async_mode=int(args.get("async", 1)),
            ondup=args.get("ondup"),
        )
    if op == "move":
        return client.fm_move(
            filelist_json=str(args.get("filelist", "[]")),
            async_mode=int(args.get("async", 1)),
            ondup=args.get("ondup"),
        )
    if op == "rename":
        return client.fm_rename(
            filelist_json=str(args.get("filelist", "[]")),
            async_mode=int(args.get("async", 1)),
            ondup=args.get("ondup"),
        )
    if op == "copy":
        return client.fm_copy(
            filelist_json=str(args.get("filelist", "[]")),
            async_mode=int(args.get("async", 1)),
            ondup=args.get("ondup"),
        )
    if op == "list_all":
        return client.list_all(
            path=str(args.get("path", "/")),
            recursion=int(args.get("recursion", 1)),
            start=int(args.get("start", 0)),
            limit=int(args.get("limit", 100)),
            order=str(args.get("order", "time")),
            desc=int(args.get("desc", 1)),
        )
    if op == "file_metas":
        return client.file_metas(
            fsids=str(args.get("fsids", "[]")),
            thumb=args.get("thumb"),
            extra=args.get("extra"),
            dlink=args.get("dlink"),
            path=args.get("path"),
            needmedia=args.get("needmedia"),
        )
    if op == "download_links":
        fsids_val = args.get("fsids", "[]")
        try:
            parsed = json.loads(fsids_val) if isinstance(fsids_val, str) else fsids_val
        except Exception:
            parsed = fsids_val
        return client.download_links(parsed)
    if op == "share_create":
        # 支持两种参数名：fsid_list 和 fsids
        fsids_val = args.get("fsid_list") or args.get("fsids", "[]")
        try:
            fsid_list = json.loads(fsids_val) if isinstance(fsids_val, str) else fsids_val
        except Exception:
            fsid_list = fsids_val
        period = int(args.get("period", 7))
        pwd = str(args.get("pwd", "1234"))
        remark = args.get("remark")
        ticket = args.get("ticket")
        return client.create_share_link(fsid_list=fsid_list, period=period, pwd=pwd, remark=remark, ticket=ticket)
    if op == "download_ticket":
        # 允许通过 fsid 或直接传 dlink 申请票据
        import time as _time
        from app.core.config import settings
        try:
            import jwt as _jwt
        except Exception:
            return {"status": "error", "error": "pyjwt_not_installed"}

        dlink: str | None = args.get("dlink")
        fsid = args.get("fsid")
        ttl_seconds = int(args.get("ttl", 300))  # 默认5分钟

        if not dlink and not fsid:
            return {"status": "error", "error": "missing_dlink_or_fsid"}

        # 若提供 fsid，则用当前 client 获取 dlink（默认走公共态由调用方控制）
        if not dlink and fsid is not None:
            try:
                fsids = [int(fsid)]
            except Exception:
                try:
                    fsids = [int(str(fsid))]
                except Exception:
                    return {"status": "error", "error": "invalid_fsid"}
            metas = client.download_links(fsids)
            # 兼容不同返回结构
            items = metas.get("list") or metas.get("data", {}).get("list") or []
            if not items:
                return {"status": "error", "error": "dlink_not_found"}
            first = items[0] if isinstance(items, list) else items
            dlink = first.get("dlink") if isinstance(first, dict) else None
            if not dlink:
                return {"status": "error", "error": "dlink_not_found"}

        now = int(_time.time())
        payload = {
            "typ": "bd.dl.ticket",
            "dlink": dlink,
            "iat": now,
            "exp": now + ttl_seconds,
            # 可扩展字段，如文件名、fsid 等
        }
        token = _jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        return {
            "status": "ok",
            "ticket": token,
            "expires_in": ttl_seconds,
        }
    
    # 离线下载功能
    if op == "offline_add":
        url = str(args.get("url", ""))
        save_path = str(args.get("save_path", "/"))
        filename = args.get("filename")
        return client.offline_add(url=url, save_path=save_path, filename=filename)
    
    if op == "offline_status":
        task_id = args.get("task_id")
        return client.offline_status(task_id=task_id)
    
    if op == "offline_cancel":
        task_id = str(args.get("task_id", ""))
        return client.offline_cancel(task_id=task_id)
    
    # 其他操作待逐步对接 openapi_client 具体方法
    raise NotImplementedError(op)


@router.post("/public/exec")
def public_exec(payload: dict, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> JSONResponse:
    op = str(payload.get("op", "")).strip()
    args = payload.get("args") or {}
    if op not in ALLOWED_OPS:
        return JSONResponse({"status": "error", "error": "op_not_allowed", "op": op}, status_code=400)
    try:
        # temporary debug: safe args preview (avoid sensitive fields)
        def _safe_args_preview(d: dict) -> dict:
            keys = {
                "dir", "dir_path", "filename", "url", "remote_path", "local_file_path",
                "url_list", "text_list", "file_list", "fsids", "fsid_list", "path", "key"
            }
            return {k: d.get(k) for k in keys if k in d}

        logger.info(f"mcp.public op=%s user=%s args=%s", op, current.username, _safe_args_preview(args))
        # ---- Upload directory enforcement ----
        def _path_starts_with_user_upload(p: str | None) -> bool:
            if not p:
                return False
            try:
                s = str(p)
            except Exception:
                return False
            s = s.strip()
            return s == "/用户上传" or s.startswith("/用户上传/")

        def _enforce_upload_dir(op_name: str, op_args: dict) -> None:
            # Only enforce for upload ops
            if op_name in {"upload_url"}:
                if not _path_starts_with_user_upload(op_args.get("dir") or op_args.get("dir_path")):
                    raise HTTPException(status_code=400, detail="upload_dir_not_allowed")
            if op_name in {"upload_text"}:
                if not _path_starts_with_user_upload(op_args.get("dir")):
                    raise HTTPException(status_code=400, detail="upload_dir_not_allowed")
            if op_name in {"upload_local"}:
                if not _path_starts_with_user_upload(op_args.get("remote_path")):
                    raise HTTPException(status_code=400, detail="upload_dir_not_allowed")
            if op_name in {"upload_batch_url"}:
                items = op_args.get("url_list") or []
                for it in items:
                    if not _path_starts_with_user_upload((it or {}).get("dir_path")):
                        raise HTTPException(status_code=400, detail="upload_dir_not_allowed")
            if op_name in {"upload_batch_text"}:
                items = op_args.get("text_list") or []
                for it in items:
                    if not _path_starts_with_user_upload((it or {}).get("dir")):
                        raise HTTPException(status_code=400, detail="upload_dir_not_allowed")
            if op_name in {"upload_batch_local"}:
                items = op_args.get("file_list") or []
                for it in items:
                    if not _path_starts_with_user_upload((it or {}).get("remote_path")):
                        raise HTTPException(status_code=400, detail="upload_dir_not_allowed")

        if op.startswith("upload_"):
            _enforce_upload_dir(op, args)

        # Charge quota for public-mode operations too, except for space quota queries
        CHARGE_OPS = {"download_ticket", "share_create", "file_metas"}
        if op in CHARGE_OPS:
            check_and_consume_quota(current, db)
        client = get_netdisk_client(mode="public")
        try:
            data = _exec_with_client(op, args, client)
            logger.info(f"mcp.public result op=%s status=ok", op)
        except Exception as e:
            logger.error("mcp.public result op=%s error=%s", op, e)
            raise
        return JSONResponse({"status": "ok", "data": data})
    except NotImplementedError:
        return JSONResponse({"status": "error", "error": "op_not_implemented", "op": op}, status_code=400)
    except Exception as e:
        # 尝试从 HTTPError 中提取原始响应体，便于定位（如 MAC check failed、errno 等）
        try:
            from urllib.error import HTTPError
            if isinstance(e, HTTPError) and e.fp is not None:
                body = e.fp.read().decode("utf-8", errors="ignore")
                try:
                    import json as _json
                    parsed = _json.loads(body)
                except Exception:
                    parsed = {"errmsg": body}
                parsed.setdefault("errno", -1)
                parsed.setdefault("errmsg", str(e))
                parsed["__debug"] = {
                    "op": op,
                    "token_mode": "public",
                }
                return JSONResponse({"status": "error", "error": parsed.get("errmsg"), "data": parsed}, status_code=200)
        except Exception:
            pass
        return JSONResponse({"status": "error", "error": str(e), "data": {"__debug": {"op": op, "token_mode": "public"}}}, status_code=200)


@router.post("/user/exec")
def user_exec(payload: dict, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> JSONResponse:
    op = str(payload.get("op", "")).strip()
    args = payload.get("args") or {}
    if op not in ALLOWED_OPS:
        return JSONResponse({"status": "error", "error": "op_not_allowed", "op": op}, status_code=400)
    # Only charge quota for counting operations; do NOT count space quota refresh
    CHARGE_OPS = {"download_ticket", "share_create", "file_metas"}
    if op in CHARGE_OPS:
        # consume 1 from shared daily quota
        try:
            check_and_consume_quota(current, db)
        except Exception as _e:
            # bubble up HTTPException if any
            raise
    # temporary debug: safe args preview
    def _safe_args_preview_user(d: dict) -> dict:
        keys = {
            "dir", "dir_path", "filename", "url", "remote_path", "local_file_path",
            "url_list", "text_list", "file_list", "fsids", "fsid_list", "path", "key"
        }
        return {k: d.get(k) for k in keys if k in d}
    logger.info("mcp.user op=%s user=%s args=%s", op, current.username, _safe_args_preview_user(args))
    # Enforce upload directory for user mode as well
    if op.startswith("upload_"):
        def _path_starts_with_user_upload(p: str | None) -> bool:
            if not p:
                return False
            try:
                s = str(p)
            except Exception:
                return False
            s = s.strip()
            return s == "/用户上传" or s.startswith("/用户上传/")

        def _enforce_upload_dir_user(op_name: str, op_args: dict) -> None:
            if op_name in {"upload_url"}:
                if not _path_starts_with_user_upload(op_args.get("dir") or op_args.get("dir_path")):
                    raise HTTPException(status_code=400, detail="upload_dir_not_allowed")
            if op_name in {"upload_text"}:
                if not _path_starts_with_user_upload(op_args.get("dir")):
                    raise HTTPException(status_code=400, detail="upload_dir_not_allowed")
            if op_name in {"upload_local"}:
                if not _path_starts_with_user_upload(op_args.get("remote_path")):
                    raise HTTPException(status_code=400, detail="upload_dir_not_allowed")
            if op_name in {"upload_batch_url"}:
                items = op_args.get("url_list") or []
                for it in items:
                    if not _path_starts_with_user_upload((it or {}).get("dir_path")):
                        raise HTTPException(status_code=400, detail="upload_dir_not_allowed")
            if op_name in {"upload_batch_text"}:
                items = op_args.get("text_list") or []
                for it in items:
                    if not _path_starts_with_user_upload((it or {}).get("dir")):
                        raise HTTPException(status_code=400, detail="upload_dir_not_allowed")
            if op_name in {"upload_batch_local"}:
                items = op_args.get("file_list") or []
                for it in items:
                    if not _path_starts_with_user_upload((it or {}).get("remote_path")):
                        raise HTTPException(status_code=400, detail="upload_dir_not_allowed")

        _enforce_upload_dir_user(op, args)
    try:
        client = get_netdisk_client(user_id=current.id, mode="user")
        try:
            data = _exec_with_client(op, args, client)
            logger.info("mcp.user result op=%s status=ok", op)
        except Exception as e:
            logger.error("mcp.user result op=%s error=%s", op, e)
            raise
        return JSONResponse({"status": "ok", "data": data})
    except NotImplementedError:
        return JSONResponse({"status": "error", "error": "op_not_implemented", "op": op}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=200)

