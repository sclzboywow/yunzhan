from __future__ import annotations

from typing import Optional
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app.deps.auth import get_current_user
from app.models.user import User
from app.services.mcp_client import get_netdisk_client


router = APIRouter(prefix="/mcp", tags=["mcp"])


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
def public_exec(payload: dict, current: User = Depends(get_current_user)) -> JSONResponse:
    op = str(payload.get("op", "")).strip()
    args = payload.get("args") or {}
    if op not in ALLOWED_OPS:
        return JSONResponse({"status": "error", "error": "op_not_allowed", "op": op}, status_code=400)
    try:
        client = get_netdisk_client(mode="public")
        data = _exec_with_client(op, args, client)
        return JSONResponse({"status": "ok", "data": data})
    except NotImplementedError:
        return JSONResponse({"status": "error", "error": "op_not_implemented", "op": op}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=200)


@router.post("/user/exec")
def user_exec(payload: dict, current: User = Depends(get_current_user)) -> JSONResponse:
    op = str(payload.get("op", "")).strip()
    args = payload.get("args") or {}
    if op not in ALLOWED_OPS:
        return JSONResponse({"status": "error", "error": "op_not_allowed", "op": op}, status_code=400)
    try:
        client = get_netdisk_client(user_id=current.id, mode="user")
        data = _exec_with_client(op, args, client)
        return JSONResponse({"status": "ok", "data": data})
    except NotImplementedError:
        return JSONResponse({"status": "error", "error": "op_not_implemented", "op": op}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=200)

