from __future__ import annotations

from typing import Any, Dict, Optional
import hashlib
import json
import os
import tempfile
import time

from openapi_client import ApiClient, Configuration
from openapi_client.api.userinfo_api import UserinfoApi
from openapi_client.api.fileinfo_api import FileinfoApi
from openapi_client.api.filemanager_api import FilemanagerApi
from openapi_client.api.multimediafile_api import MultimediafileApi
from openapi_client.api.fileupload_api import FileuploadApi

from app.core.config import get_settings
import urllib.parse
import urllib.request
from app.services.token_store import TokenStore
from app.core.db import SessionLocal


class NetdiskClient:
    def __init__(self, access_token: Optional[str] = None, user_id: Optional[int] = None, mode: str = "user") -> None:
        settings = get_settings()
        # 记录令牌模式，便于下游调试输出
        self._token_mode = mode
        if mode == "public":
            # 仅使用服务账户令牌，不再回退环境变量
            with SessionLocal() as db:
                store = TokenStore(db)
                token = store.ensure_fresh_service_token()
                self._access_token = token or ""
        elif user_id is not None:
            with SessionLocal() as db:
                store = TokenStore(db)
                token = store.ensure_fresh_access_token(user_id)
                # 用户态：必须拿到用户自己的百度token，禁止任何服务态/环境变量兜底
                if not token:
                    raise ValueError("user_baidu_token_missing")
                self._access_token = token
        else:
            self._access_token = access_token or ""
        self._config = Configuration()

    def quota(self) -> Dict[str, Any]:
        with ApiClient(self._config) as api_client:
            api = UserinfoApi(api_client)
            resp = api.apiquota(access_token=self._access_token)
            return resp.to_dict() if hasattr(resp, "to_dict") else dict(resp)

    def get_user_info(self) -> Dict[str, Any]:
        """获取百度网盘用户信息"""
        import requests
        
        url = "https://pan.baidu.com/rest/2.0/xpan/nas"
        params = {
            "method": "uinfo",
            "access_token": self._access_token,
            "vip_version": "v2"
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "errno": -1,
                "errmsg": f"获取用户信息失败: {str(e)}"
            }

    def list_files(self, dir_path: str = "/", limit: int = 100, order: str = "time", desc: int = 1) -> Dict[str, Any]:
        with ApiClient(self._config) as api_client:
            api = FileinfoApi(api_client)
            resp = api.xpanfilelist(access_token=self._access_token, dir=dir_path, limit=limit, order=order, desc=desc)
            return resp.to_dict() if hasattr(resp, "to_dict") else (resp if isinstance(resp, dict) else {"data": resp})

    def list_images(self, parent_path: str = "/", page: int = 1, num: int = 50, order: str = "time", desc: str = "1") -> Dict[str, Any]:
        with ApiClient(self._config) as api_client:
            api = FileinfoApi(api_client)
            resp = api.xpanfileimagelist(access_token=self._access_token, parent_path=parent_path, page=page, num=num, order=order, desc=desc)
            return resp.to_dict() if hasattr(resp, "to_dict") else (resp if isinstance(resp, dict) else {"data": resp})

    def list_docs(self, parent_path: str = "/", page: int = 1, num: int = 50, order: str = "time", desc: str = "1") -> Dict[str, Any]:
        with ApiClient(self._config) as api_client:
            api = FileinfoApi(api_client)
            resp = api.xpanfiledoclist(access_token=self._access_token, parent_path=parent_path, page=page, num=num, order=order, desc=desc)
            return resp.to_dict() if hasattr(resp, "to_dict") else (resp if isinstance(resp, dict) else {"data": resp})

    def search_filename(self, key: str, dir_path: str = "/", page: str = "1", num: str = "50", recursion: str = "1") -> Dict[str, Any]:
        with ApiClient(self._config) as api_client:
            api = FileinfoApi(api_client)
            resp = api.xpanfilesearch(access_token=self._access_token, key=key, dir=dir_path, page=page, num=num, recursion=recursion)
            return resp.to_dict() if hasattr(resp, "to_dict") else (resp if isinstance(resp, dict) else {"data": resp})

    # ---- File manager operations ----
    def fm_delete(self, filelist_json: str, async_mode: int = 1, ondup: str | None = None) -> Dict[str, Any]:
        with ApiClient(self._config) as api_client:
            api = FilemanagerApi(api_client)
            kwargs = {"access_token": self._access_token, "_async": async_mode, "filelist": filelist_json}
            if ondup is not None:
                kwargs["ondup"] = ondup
            resp = api.filemanagerdelete(**kwargs)
            return resp.to_dict() if hasattr(resp, "to_dict") else (resp if isinstance(resp, dict) else {"status": "ok"})

    def fm_move(self, filelist_json: str, async_mode: int = 1, ondup: str | None = None) -> Dict[str, Any]:
        with ApiClient(self._config) as api_client:
            api = FilemanagerApi(api_client)
            kwargs = {"access_token": self._access_token, "_async": async_mode, "filelist": filelist_json}
            if ondup is not None:
                kwargs["ondup"] = ondup
            resp = api.filemanagermove(**kwargs)
            return resp.to_dict() if hasattr(resp, "to_dict") else (resp if isinstance(resp, dict) else {"status": "ok"})

    def fm_rename(self, filelist_json: str, async_mode: int = 1, ondup: str | None = None) -> Dict[str, Any]:
        with ApiClient(self._config) as api_client:
            api = FilemanagerApi(api_client)
            kwargs = {"access_token": self._access_token, "_async": async_mode, "filelist": filelist_json}
            if ondup is not None:
                kwargs["ondup"] = ondup
            resp = api.filemanagerrename(**kwargs)
            return resp.to_dict() if hasattr(resp, "to_dict") else (resp if isinstance(resp, dict) else {"status": "ok"})

    def fm_copy(self, filelist_json: str, async_mode: int = 1, ondup: str | None = None) -> Dict[str, Any]:
        with ApiClient(self._config) as api_client:
            api = FilemanagerApi(api_client)
            kwargs = {"access_token": self._access_token, "_async": async_mode, "filelist": filelist_json}
            if ondup is not None:
                kwargs["ondup"] = ondup
            resp = api.filemanagercopy(**kwargs)
            return resp.to_dict() if hasattr(resp, "to_dict") else (resp if isinstance(resp, dict) else {"status": "ok"})

    # ---- Multimedia ----
    def list_all(self, path: str = "/", recursion: int = 1, start: int = 0, limit: int = 100, order: str = "time", desc: int = 1) -> Dict[str, Any]:
        with ApiClient(self._config) as api_client:
            api = MultimediafileApi(api_client)
            resp = api.xpanfilelistall(access_token=self._access_token, path=path, recursion=recursion, start=start, limit=limit, order=order, desc=desc)
            return resp.to_dict() if hasattr(resp, "to_dict") else (resp if isinstance(resp, dict) else {"data": resp})

    def file_metas(self, fsids: str, thumb: str | None = None, extra: str | None = None, dlink: str | None = None, path: str | None = None, needmedia: int | None = None) -> Dict[str, Any]:
        with ApiClient(self._config) as api_client:
            api = MultimediafileApi(api_client)
            resp = api.xpanmultimediafilemetas(access_token=self._access_token, fsids=fsids, thumb=thumb, extra=extra, dlink=dlink, path=path, needmedia=needmedia)
            return resp.to_dict() if hasattr(resp, "to_dict") else (resp if isinstance(resp, dict) else {"data": resp})

    def download_links(self, fsids: list[int] | list[str] | str) -> Dict[str, Any]:
        if isinstance(fsids, (list, tuple)):
            fsids_str = json.dumps([int(x) for x in fsids])
        else:
            fsids_str = str(fsids)
        with ApiClient(self._config) as api_client:
            api = MultimediafileApi(api_client)
            resp = api.xpanmultimediafilemetas(access_token=self._access_token, fsids=fsids_str, dlink="1")
            data = resp.to_dict() if hasattr(resp, "to_dict") else (resp if isinstance(resp, dict) else {"data": resp})
            return data

    # ---- Share (per doc https://pan.baidu.com/union/doc/Tlaaocmkj) ----
    def create_share_link(self, fsid_list: list[int] | list[str] | str, period: int, pwd: str, remark: str | None = None, ticket: dict | None = None) -> Dict[str, Any]:
        settings = get_settings()
        appid = settings.baidu_app_id or ""
        # 基础参数校验（提前拦截明显错误）
        try:
            import re
            if period not in {1, 7, 30}:
                return {"errno": -40001, "errmsg": "invalid period, must be 1/7/30", "period": period}
            if not isinstance(pwd, str) or not re.fullmatch(r"[a-z0-9]{4}", pwd or ""):
                return {"errno": -40002, "errmsg": "invalid pwd, must be 4 chars [a-z0-9]", "pwd": pwd}
        except Exception:
            pass

        if isinstance(fsid_list, (list, tuple)):
            fsid_list_str = json.dumps([str(x) for x in fsid_list])
        else:
            fsid_list_str = str(fsid_list)

        # doc requires: POST form to https://pan.baidu.com/apaas/1.0/share/set?product=netdisk&appid=...&access_token=...
        query = urllib.parse.urlencode({
            "product": "netdisk",
            "appid": appid,
            "access_token": self._access_token,
        })
        url = f"https://pan.baidu.com/apaas/1.0/share/set?{query}"
        form = {
            "fsid_list": fsid_list_str,
            "period": str(period),
            "pwd": pwd,
        }
        if remark:
            form["remark"] = remark
        if ticket:
            form["ticket"] = json.dumps(ticket, ensure_ascii=False)

        data = urllib.parse.urlencode(form).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8")
                try:
                    parsed = json.loads(body)
                except Exception:
                    parsed = {"raw": body}
                # 正常 2xx 时直接返回百度结构
                return parsed
        except Exception as e:
            # 若为 HTTPError，读取响应体，透传百度原始错误以便定位（如 MAC check failed / errno）
            try:
                from urllib.error import HTTPError
                if isinstance(e, HTTPError) and e.fp is not None:
                    err_body = e.fp.read().decode("utf-8", errors="ignore")
                    try:
                        err_parsed = json.loads(err_body)
                    except Exception:
                        err_parsed = {"errmsg": err_body}
                    # 附带调试关键信息（不包含 token），帮助确认是否为 appid/令牌不匹配
                    err_parsed.setdefault("errno", -1)
                    err_parsed.setdefault("errmsg", str(e))
                    # 解析 fsid_list 长度时避免再次抛错
                    fs_len = 0
                    try:
                        parsed_fs = json.loads(fsid_list_str) if fsid_list_str and fsid_list_str.strip().startswith("[") else None
                        if isinstance(parsed_fs, list):
                            fs_len = len(parsed_fs)
                    except Exception:
                        fs_len = 0
                    err_parsed["__debug"] = {
                        "appid": appid,
                        "token_mode": getattr(self, "_token_mode", "unknown"),
                        "fsid_list_len": fs_len,
                        "http_status": getattr(e, "code", None),
                    }
                    return err_parsed
            except Exception:
                pass
            # 兜底：无法读取响应体时，返回通用错误
            return {"errno": -1, "errmsg": str(e)}

    # ---- Convenience filters (videos / bt / category summary / recent) ----
    def list_videos(self, path: str = "/", recursion: int = 0, start: int = 0, limit: int = 100, order: str = "time", desc: int = 1) -> Dict[str, Any]:
        data = self.list_all(path=path, recursion=recursion, start=start, limit=limit, order=order, desc=desc)
        items = data.get("list") or data.get("data", {}).get("list") or data
        if isinstance(items, dict) and "list" in items:
            items = items["list"]
        filtered = [it for it in (items or []) if isinstance(it, dict) and it.get("category") == 1]
        return {"errno": 0, "list": filtered}

    def list_bt(self, path: str = "/", recursion: int = 0, start: int = 0, limit: int = 100, order: str = "time", desc: int = 1) -> Dict[str, Any]:
        data = self.list_all(path=path, recursion=recursion, start=start, limit=limit, order=order, desc=desc)
        items = data.get("list") or data.get("data", {}).get("list") or data
        if isinstance(items, dict) and "list" in items:
            items = items["list"]
        filtered = [it for it in (items or []) if isinstance(it, dict) and it.get("category") == 7]
        return {"errno": 0, "list": filtered}

    def list_category(self, path: str = "/", recursion: int = 1, limit: int = 1000) -> Dict[str, Any]:
        data = self.list_all(path=path, recursion=recursion, limit=limit)
        items = data.get("list") or data.get("data", {}).get("list") or []
        if isinstance(items, dict) and "list" in items:
            items = items["list"]
        counts: Dict[int, int] = {}
        for it in items or []:
            if not isinstance(it, dict):
                continue
            cat = int(it.get("category") or 0)
            counts[cat] = counts.get(cat, 0) + 1
        return {"errno": 0, "counts": counts}

    def recent(self, path: str = "/", limit: int = 50) -> Dict[str, Any]:
        data = self.list_all(path=path, recursion=1, limit=limit, order="time", desc=1)
        return data

    # ---- mkdir ----
    def mkdir(self, path: str, rtype: int = 0) -> Dict[str, Any]:
        """Create directory at path using xpan file create with isdir=1.

        Some providers ignore uploadid/block_list for directories; pass placeholders.
        """
        with ApiClient(self._config) as api_client:
            api = FileuploadApi(api_client)
            kwargs = {
                "access_token": self._access_token,
                "path": path,
                "isdir": 1,
                "size": 0,
                "uploadid": "",
                "block_list": "[]",
            }
            kwargs["rtype"] = int(rtype)
            resp = api.xpanfilecreate(**kwargs)
            return resp.to_dict() if hasattr(resp, "to_dict") else (resp if isinstance(resp, dict) else {"data": resp})

    # ---- semantic search (mapped to filesearch as provider API) ----
    def search_semantic(self, query: str, dir_path: str = "/", page: str = "1", num: str = "50", recursion: str = "1") -> Dict[str, Any]:
        with ApiClient(self._config) as api_client:
            api = FileinfoApi(api_client)
            resp = api.xpanfilesearch(access_token=self._access_token, key=query, dir=dir_path, page=page, num=num, recursion=recursion)
            return resp.to_dict() if hasattr(resp, "to_dict") else (resp if isinstance(resp, dict) else {"data": resp})

    # ---- uploads (placeholders to be implemented) ----
    def upload_local(self, local_file_path: str, remote_path: str) -> Dict[str, Any]:
        if not os.path.isfile(local_file_path):
            return {"status": "error", "error": "local_file_not_found"}
        file_size = os.path.getsize(local_file_path)
        # 计算单块 md5（小文件用单分片上传）
        with open(local_file_path, "rb") as f:
            file_bytes = f.read()
        block_md5 = hashlib.md5(file_bytes).hexdigest()
        block_list = json.dumps([block_md5])
        with ApiClient(self._config) as api_client:
            up = FileuploadApi(api_client)
            # 预创建
            pre = up.xpanfileprecreate(
                access_token=self._access_token,
                path=remote_path,
                isdir=0,
                size=file_size,
                autoinit=1,
                block_list=block_list,
            )
            pre_dict = pre if isinstance(pre, dict) else (pre.to_dict() if hasattr(pre, "to_dict") else {})
            uploadid = pre_dict.get("uploadid") or pre_dict.get("upload_id") or ""
            if not uploadid:
                return {"status": "error", "error": "precreate_failed", "data": pre_dict}
            # 上传分片（单分片 partseq=0）
            with open(local_file_path, "rb") as f:
                _ = up.pcssuperfile2(
                    access_token=self._access_token,
                    partseq="0",
                    path=remote_path,
                    uploadid=uploadid,
                    type="tmpfile",
                    file=f,
                )
            # 合并创建
            fin = up.xpanfilecreate(
                access_token=self._access_token,
                path=remote_path,
                isdir=0,
                size=file_size,
                uploadid=uploadid,
                block_list=block_list,
            )
            return fin.to_dict() if hasattr(fin, "to_dict") else (fin if isinstance(fin, dict) else {"data": fin})

    def upload_url(self, url: str, dir_path: str = "/", filename: str | None = None) -> Dict[str, Any]:
        try:
            import requests  # lazy import
        except Exception:
            return {"status": "error", "error": "requests_not_installed"}
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
        except Exception as e:
            return {"status": "error", "error": f"download_failed: {e}"}
        name = filename or (url.rstrip("/").split("/")[-1] or "download.bin")
        remote_path = os.path.join(dir_path if dir_path else "/", name)
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(r.content)
            tmp_path = tmp.name
        try:
            return self.upload_local(tmp_path, remote_path)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def upload_text(self, content: str, dir_path: str = "/", filename: str | None = None) -> Dict[str, Any]:
        safe_name = filename or "note.txt"
        remote_path = os.path.join(dir_path if dir_path else "/", safe_name)
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as tmp:
            tmp.write(content.encode("utf-8"))
            tmp_path = tmp.name
        try:
            return self.upload_local(tmp_path, remote_path)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def upload_batch_local(self, file_list: list[dict], max_concurrent: int = 3) -> Dict[str, Any]:
        """批量上传本地文件
        
        Args:
            file_list: 文件列表，每个元素包含 {"local_path": str, "remote_path": str}
            max_concurrent: 最大并发数，默认3个
        """
        import concurrent.futures
        import threading
        
        results = []
        errors = []
        
        def upload_single_file(file_info: dict) -> dict:
            try:
                local_path = file_info.get("local_path", "")
                remote_path = file_info.get("remote_path", "")
                if not local_path or not remote_path:
                    return {"status": "error", "error": "missing_paths", "file": file_info}
                
                result = self.upload_local(local_path, remote_path)
                return {"file": file_info, "result": result}
            except Exception as e:
                return {"file": file_info, "result": {"status": "error", "error": str(e)}}
        
        # 使用线程池进行并发上传
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_file = {
                executor.submit(upload_single_file, file_info): file_info 
                for file_info in file_list
            }
            
            for future in concurrent.futures.as_completed(future_to_file):
                file_info = future_to_file[future]
                try:
                    result = future.result()
                    if result["result"].get("status") == "error":
                        errors.append(result)
                    else:
                        results.append(result)
                except Exception as e:
                    errors.append({
                        "file": file_info, 
                        "result": {"status": "error", "error": str(e)}
                    })
        
        return {
            "status": "completed",
            "total": len(file_list),
            "success": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors
        }

    def upload_batch_url(self, url_list: list[dict], max_concurrent: int = 3) -> Dict[str, Any]:
        """批量上传URL文件
        
        Args:
            url_list: URL列表，每个元素包含 {"url": str, "dir_path": str, "filename": str}
            max_concurrent: 最大并发数，默认3个
        """
        import concurrent.futures
        
        results = []
        errors = []
        
        def upload_single_url(url_info: dict) -> dict:
            try:
                url = url_info.get("url", "")
                dir_path = url_info.get("dir_path", "/")
                filename = url_info.get("filename")
                
                if not url:
                    return {"status": "error", "error": "missing_url", "url_info": url_info}
                
                result = self.upload_url(url, dir_path, filename)
                return {"url_info": url_info, "result": result}
            except Exception as e:
                return {"url_info": url_info, "result": {"status": "error", "error": str(e)}}
        
        # 使用线程池进行并发上传
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_url = {
                executor.submit(upload_single_url, url_info): url_info 
                for url_info in url_list
            }
            
            for future in concurrent.futures.as_completed(future_to_url):
                url_info = future_to_url[future]
                try:
                    result = future.result()
                    if result["result"].get("status") == "error":
                        errors.append(result)
                    else:
                        results.append(result)
                except Exception as e:
                    errors.append({
                        "url_info": url_info, 
                        "result": {"status": "error", "error": str(e)}
                    })
        
        return {
            "status": "completed",
            "total": len(url_list),
            "success": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors
        }

    def upload_batch_text(self, text_list: list[dict], max_concurrent: int = 3) -> Dict[str, Any]:
        """批量上传文本内容
        
        Args:
            text_list: 文本列表，每个元素包含 {"content": str, "dir_path": str, "filename": str}
            max_concurrent: 最大并发数，默认3个
        """
        import concurrent.futures
        
        results = []
        errors = []
        
        def upload_single_text(text_info: dict) -> dict:
            try:
                content = text_info.get("content", "")
                dir_path = text_info.get("dir_path", "/")
                filename = text_info.get("filename")
                
                if not content:
                    return {"status": "error", "error": "missing_content", "text_info": text_info}
                
                result = self.upload_text(content, dir_path, filename)
                return {"text_info": text_info, "result": result}
            except Exception as e:
                return {"text_info": text_info, "result": {"status": "error", "error": str(e)}}
        
        # 使用线程池进行并发上传
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_text = {
                executor.submit(upload_single_text, text_info): text_info 
                for text_info in text_list
            }
            
            for future in concurrent.futures.as_completed(future_to_text):
                text_info = future_to_text[future]
                try:
                    result = future.result()
                    if result["result"].get("status") == "error":
                        errors.append(result)
                    else:
                        results.append(result)
                except Exception as e:
                    errors.append({
                        "text_info": text_info, 
                        "result": {"status": "error", "error": str(e)}
                    })
        
        return {
            "status": "completed",
            "total": len(text_list),
            "success": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors
        }

    # ---- 离线下载功能 ----
    def offline_add(self, url: str, save_path: str = "/", filename: str | None = None) -> Dict[str, Any]:
        """添加离线下载任务
        
        Args:
            url: 下载链接
            save_path: 保存路径
            filename: 文件名（可选）
        """
        try:
            import requests
        except Exception:
            return {"status": "error", "error": "requests_not_installed"}
        
        # 构建请求参数
        params = {
            "method": "add_task",
            "access_token": self._access_token,
            "url": url,
            "save_path": save_path,
        }
        
        if filename:
            params["filename"] = filename
        
        # 调用百度网盘离线下载API
        try:
            response = requests.post(
                "https://pan.baidu.com/rest/2.0/xpan/offline",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            # 检查百度网盘API返回的错误码
            if isinstance(result, dict) and "errno" in result:
                errno = result.get("errno", 0)
                if errno != 0:
                    error_msg = result.get("errmsg", "未知错误")
                    return {"status": "error", "error": f"百度网盘API错误 {errno}: {error_msg}"}
            
            return result
        except Exception as e:
            return {"status": "error", "error": f"offline_add_failed: {str(e)}"}

    def offline_status(self, task_id: str | None = None) -> Dict[str, Any]:
        """查询离线下载任务状态
        
        Args:
            task_id: 任务ID，如果为None则查询所有任务
        """
        try:
            import requests
        except Exception:
            return {"status": "error", "error": "requests_not_installed"}
        
        # 构建请求参数
        params = {
            "method": "query_task",
            "access_token": self._access_token,
        }
        
        if task_id:
            params["task_id"] = task_id
        
        # 调用百度网盘离线下载API
        try:
            response = requests.post(
                "https://pan.baidu.com/rest/2.0/xpan/offline",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            # 检查百度网盘API返回的错误码
            if isinstance(result, dict) and "errno" in result:
                errno = result.get("errno", 0)
                if errno != 0:
                    error_msg = result.get("errmsg", "未知错误")
                    return {"status": "error", "error": f"百度网盘API错误 {errno}: {error_msg}"}
            
            return result
        except Exception as e:
            return {"status": "error", "error": f"offline_status_failed: {str(e)}"}

    def offline_cancel(self, task_id: str) -> Dict[str, Any]:
        """取消离线下载任务
        
        Args:
            task_id: 任务ID
        """
        try:
            import requests
        except Exception:
            return {"status": "error", "error": "requests_not_installed"}
        
        # 构建请求参数
        params = {
            "method": "cancel_task",
            "access_token": self._access_token,
            "task_id": task_id,
        }
        
        # 调用百度网盘离线下载API
        try:
            response = requests.post(
                "https://pan.baidu.com/rest/2.0/xpan/offline",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            # 检查百度网盘API返回的错误码
            if isinstance(result, dict) and "errno" in result:
                errno = result.get("errno", 0)
                if errno != 0:
                    error_msg = result.get("errmsg", "未知错误")
                    return {"status": "error", "error": f"百度网盘API错误 {errno}: {error_msg}"}
            
            return result
        except Exception as e:
            return {"status": "error", "error": f"offline_cancel_failed: {str(e)}"}


def get_netdisk_client(access_token: Optional[str] = None, user_id: Optional[int] = None, mode: str = "user") -> NetdiskClient:
    return NetdiskClient(access_token=access_token, user_id=user_id, mode=mode)


