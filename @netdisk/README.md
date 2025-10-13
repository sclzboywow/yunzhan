## 项目实施计划（后端：FastAPI + WebSocket + SQLite + PyCryptodome）

### M0 项目初始化（1–2 天）
- **建仓与约定**：Poetry、`pyproject.toml`、`pre-commit`（ruff/black/mypy）、`.env.example`
- **基础服务**：FastAPI 骨架、健康检查、Swagger/ReDoc、结构化日志、CORS
- **配置体系**：`pydantic-settings` 管理环境变量（区分 dev/prod）
- **容器化**：`Dockerfile`、`docker-compose.dev.yml`（SQLite 数据卷）
- **目录布局**：
  - `app/`：`main.py`、`api/`、`services/`、`models/`、`schemas/`、`deps/`、`core/`
  - `migrations/`（如采用 Alembic）
  - `tests/`

### M1 身份认证与用户（2–3 天）
- **JWT**：`/auth/login`、`/auth/refresh`，设置过期、时钟偏移容忍
- **用户模型与存储**：SQLite + SQLAlchemy，密码哈希（argon2/bcrypt）
- **依赖守卫**：`get_current_user`、权限装饰器；可选黑名单登出

#### 已实现（当前状态）
- 应用内 JWT 登录：`POST /auth/login` 返回 `access_token`，前端以 `Authorization: Bearer <token>` 访问受保护接口（如 `/auth/me`）。
- Swagger 在线调试注意：Request body 仅填纯 JSON，不要粘贴整段 curl 命令。
- 统一用户信息接口：`GET /auth/me`（由主应用提供，文档重复 `operationId` 已移除）。

### M2 百度网盘 Token 管理（2–3 天）
- **加密存储**：用户-百度Token 表，PyCryptodome AES-GCM 加密
- **主密钥管理**：`ENC_MASTER_KEY`（环境变量/KMS），预留轮换
- **SDK 封装**：统一入口、错误码映射、签名/重试/超时策略

#### 已实现（当前状态）
- 表结构：`oauth_tokens`，字段包含 `user_id`、`is_service`、`access_token_enc`、`refresh_token_enc`、`expires_at`。
- 加密：使用 `AES-GCM`，密钥来源 `APP_ENC_MASTER_KEY`（见 `app/core/crypto.py`）。
- 用户态 token：`TokenStore.save_user_token/get_user_token/ensure_fresh_access_token` 封装，自动在过期前 60s 内使用 refresh 刷新。
- 服务态 token：`TokenStore.save_service_token/get_service_token/ensure_fresh_service_token` 封装，优先用于公共/服务端调用（`mode="public"`）。
- 统一 SDK 客户端：`services/mcp_client.py` 的 `NetdiskClient`，根据 `mode` 与 `user_id` 自动获取并刷新 access_token。

#### 设计约定
- 服务端持有“公共/服务” token（长期凭证）并加密落库；用户态 token 默认由前端保存，但后端也支持加密落库用于异步任务。
- 不在 URL Query 中透传第三方 token；仅通过后端安全通道传递或保存在服务端。
- 建议开启 HTTPS，前端尽量使用 HttpOnly Cookie 或内存存储第三方 token。

### M3 WebSocket 实时通信（2–3 天）
- **连接**：`/ws`，JWT 握手认证，心跳保活
- **连接管理器**：多用户多连接、消息路由
- **事件规范**：`progress_update`、`mcp_callback`、`heartbeat`、`error`
- **稳健性**：回压与限速（队列/丢弃策略）；PySide6 客户端约定

### M4 下载次数限制（1–2 天）
- **表设计**：`user_id + yyyymmdd + count`
- **策略**：每日限额（默认 10，`DOWNLOAD_LIMIT` 可配）
- **接入**：依赖/中间件在下载相关接口前校验
- **管理**：查询与调整上限（可选）

### M5 MCP 接口集成与编排（3–5 天）
- **统一客户端**：requests 封装、主账号密钥、按用户授权隔离
- **典型能力**：列文件、触发下载、任务状态轮询/回调
- **审计**：请求/响应摘要与错误脱敏落库

### M6 部署上线（2–3 天）
- **进程模型**：Gunicorn 管理 Uvicorn workers（`--worker-class uvicorn.workers.UvicornWorker`）
- **反向代理**：Nginx TLS/HTTP2、WebSocket 升级、压缩
- **腾讯云轻量**：防火墙放行、systemd/Docker Compose、滚动发布
- **备份与日志**：SQLite 定期快照、日志轮转

### M7 监控与告警（可选 1–2 天）
- **指标接入**：`prometheus-fastapi-instrumentator`、自定义业务 metrics
- **可视化**：Grafana 看板（延迟/错误率/连接数/WS 活跃）
- **告警**：阈值与异常比率预警（可选飞书/企业微信/邮件）

### 依赖清单（建议）
- **后端框架**：FastAPI、Uvicorn、Gunicorn
- **认证与安全**：PyJWT、passlib[argon2] 或 bcrypt、python-multipart
- **数据层**：SQLAlchemy、SQLite、alembic（可选）
- **配置与校验**：Pydantic、pydantic-settings
- **加密**：PyCryptodome
- **网络**：requests（或 httpx）
- **可观测**：prometheus-fastapi-instrumentator、loguru/structlog（其一）
- **质量保障**：ruff、black、mypy、pytest、pre-commit

### 交付物列表
- 代码仓初始化、`pyproject.toml`、`Dockerfile`、`docker-compose.dev.yml`
- FastAPI 服务骨架与 `/health`、自动文档 `/docs`/`/redoc`
- `/auth` 模块（登录/刷新）、用户模型与加密存储
- 百度网盘 Token 加密存取与统一 SDK 封装
- `/ws` 实时通道与事件协议说明
- 下载次数限制机制与配置
- MCP 典型接口适配与审计记录
- 部署脚本/说明（Nginx、Gunicorn、Systemd 或 Compose）
- 监控仪表（可选）与使用说明

---

## 使用说明（补充）

### 登录与鉴权
1. 注册：`POST /auth/register`，JSON：`{"username":"<u>","password":"<p>"}`。
2. 登录：`POST /auth/login`，仅发送纯 JSON，返回 `{ "access_token": "..." }`。
3. 调用受保护接口：在请求头添加 `Authorization: Bearer <access_token>`。

常见错误：422 json_invalid → 请求体不是 JSON，而是把整段 curl 命令贴入了 body；请仅发送 JSON。

### MCP/网盘客户端
- 用户态：后端通过 `NetdiskClient(user_id=<id>, mode="user")` 自动获取并刷新用户 access_token。
- 公共态：后端通过 `NetdiskClient(mode="public")` 仅使用加密落库的服务 token（不再回退 `APP_BAIDU_ACCESS_TOKEN`）。

#### Token 刷新与一致性保证
- 服务 token 自动刷新：在过期前 30 天预刷新；失败时返回旧 access 由上层兜底。
- 刷新互斥：对服务 token 刷新加全局锁，避免并发导致 “refresh token has been used”。
- 惰性修复：遇到 `invalid_grant`/`refresh token has been used` 立即放弃旧 refresh，需重新授权。
- SQLite WAL：启用 WAL（写前日志）与 `synchronous=NORMAL` 提升并发与耐久性。
- 单条服务记录：仅维护一条 `is_service=1` 记录，刷新时“查到则更新，否则插入”。

### 前后端协作与多用户
- 前端无 MCP 能力时，统一由后端代理执行：
  - 用户态：`POST /mcp/user/exec`（携带用户 JWT），后端按当前用户从库取 token 并转发。
  - 公共态：`POST /mcp/public/exec`（走服务 token）。
- 多前端/多用户：每个用户的 Baidu token 独立加密存储；公共操作共用服务 token，刷新由全局锁串行化。
- 回调页（移动端友好）：`GET /oauth/callback` 根据 `state` 渲染成功/失败提示，不在 URL 透传第三方 token。

### 新接口（前端→后端上报用户 Token）
`POST /oauth/user/token/upsert`

请求头：`Authorization: Bearer <user_jwt>`

请求体（JSON）：

```json
{
  "access_token": "<user_access>",
  "refresh_token": "<user_refresh>",
  "expires_in": 2592000
}
```

说明：前端在完成用户授权后，将 token 交给后端加密落库，便于后端统一通过 `/mcp/user/exec` 代表该用户调用。

## MCP Exec API（18 项能力）

请求：`POST /mcp/public/exec` 或 `POST /mcp/user/exec`

格式：`{"op":"<能力名>", "args":{...}}`

已实现能力与示例：
- quota：`{"op":"quota"}`
- list_files：`{"op":"list_files","args":{"dir":"/","limit":50,"order":"time","desc":1}}`
- list_images：`{"op":"list_images","args":{"dir":"/","page":1,"num":50}}`
- list_docs：`{"op":"list_docs","args":{"dir":"/","page":1,"num":50}}`
- list_videos：`{"op":"list_videos","args":{"path":"/","limit":20}}`
- list_bt：`{"op":"list_bt","args":{"path":"/","limit":20}}`
- list_category：`{"op":"list_category","args":{"path":"/"}}`
- list_all：`{"op":"list_all","args":{"path":"/","recursion":1,"limit":100}}`
- file_metas：`{"op":"file_metas","args":{"fsids":"[123,456]","dlink":"1"}}`
- download_links：`{"op":"download_links","args":{"fsids":"[123,456]"}}`
- search_filename：`{"op":"search_filename","args":{"dir":"/","key":"pdf","page":"1","num":"20","recursion":"1"}}`
- search_semantic：`{"op":"search_semantic","args":{"dir":"/","query":"报告","page":"1","num":"20","recursion":"1"}}`
- mkdir：`{"op":"mkdir","args":{"path":"/来自：mcp_server/新建文件夹"}}`
- delete：`{"op":"delete","args":{"filelist":"[\"/test/a.txt\"]","async":1}}`
- move：`{"op":"move","args":{"filelist":"[{\"path\":\"/src/a.txt\",\"dest\":\"/dst\",\"newname\":\"a.txt\"}]","async":1}}`
- rename：`{"op":"rename","args":{"filelist":"[{\"path\":\"/a.txt\",\"newname\":\"b.txt\"}]","async":1}}`
- copy：`{"op":"copy","args":{"filelist":"[{\"path\":\"/a.txt\",\"dest\":\"/dst\"}]","async":1}}`
- upload_local：`{"op":"upload_local","args":{"local_file_path":"/tmp/demo.txt","remote_path":"/来自：mcp_server/demo.txt"}}`
- upload_url：`{"op":"upload_url","args":{"url":"https://example.com/a.txt","dir":"/来自：mcp_server","filename":"a.txt"}}`
- upload_text：`{"op":"upload_text","args":{"content":"hello","dir":"/来自：mcp_server","filename":"note.txt"}}`
- share_create：`{"op":"share_create","args":{"fsid_list":"[\"123\"]","period":7,"pwd":"12zx","remark":"test"}}`

返回：统一 `{status:"ok", data: ...}` 或 `{status:"error", error: ...}`。部分底层接口为直返数据时做了 `to_dict()` 兼容。

注意：
- token 仅使用后端落库服务/用户 token；已实现自动刷新（提前 30 天）。
- playlist 暂无 SDK 端点，后续如文档发布再接入。

### MCP 扩展能力优先级（待接入）
- 回收站（高优先级）
  - 能力：回收站列表、还原、清空
  - 建议 ops：`recycle_list`、`recycle_restore`、`recycle_clear`
- 分享管理（高优先级）
  - 能力：分享列表、取消分享、更新分享属性（目前仅实现创建）
  - 建议 ops：`share_list`、`share_cancel`、`share_update`
- 离线下载任务（高优先级）
  - 能力：新增离线任务、查询任务进度、取消任务
  - 建议 ops：`offline_add`、`offline_status`、`offline_cancel`
- 上传增强（中高优先级）
  - 能力：多分片并发/断点续传、CRC/多块 MD5 校验、秒传优化
  - 建议 ops：`upload_multipart_init`、`upload_multipart_part`、`upload_multipart_finish`
- 预览/缩略图（中优先级）
  - 能力：图片缩略图、文档/媒体预览（若 SDK/文档可用）
  - 建议 ops：`thumb_get`、`preview_get`
- 媒体增强（中优先级）
  - 能力：播放列表/转码清单、字幕/码率信息
  - 建议 ops：`media_playlist`、`media_info`
- 智能分类/AI 标签（中优先级）
  - 能力：更细粒度分类、语义标签（若 SDK 暴露）
  - 建议 ops：`ai_category`、`ai_tags`
- 文件属性/扩展（中优先级）
  - 能力：单文件属性扩展、增量变更 diff
  - 建议 ops：`file_attr`、`change_diff`
- 安全与校验（中优先级）
  - 能力：分享 ticket 预获取、验证码/captcha 交互
  - 建议 ops：`share_ticket`、`captcha_verify`
- 账户信息扩展（次优先级）
  - 能力：用户信息详情、空间使用明细
  - 建议 ops：`user_detail`、`space_usage`
- 批处理与编排（次优先级）
  - 能力：异步批处理、状态轮询、失败重试策略
  - 建议 ops：`batch_submit`、`batch_status`

说明：以上为待接入清单，后续将在 `NetdiskClient` 提供对应方法，并将 op 名加入 `/mcp/public/exec` 与 `/mcp/user/exec` 的 allowlist；文档会同步补充示例与约束。

### 验收结果（2025-10-13）
- 成功：
  - quota、list_files、list_images、list_docs、list_videos、list_bt
  - list_all、list_category、file_metas
  - search_filename、search_semantic
  - mkdir、delete、rename、copy
  - upload_text、upload_url
- 说明：
  - move 示例因路径不存在返回 errno=12（请使用真实存在的源/目标路径再测）。
  - 频控提示（如 31034）通过降低频率（≥30–60s）已规避。
  - 所有调用均使用服务端持久化 token；刷新互斥与 WAL 已启用。

### 环境变量（节选）
- `APP_ENC_MASTER_KEY`：AES-GCM 主密钥，至少 32 字符，生产必须修改。
- `APP_BAIDU_CLIENT_ID` / `APP_BAIDU_CLIENT_SECRET`：第三方应用凭据。
- `APP_BAIDU_REDIRECT_URI`：用户授权回调，默认 `http://127.0.0.1:8000/oauth/callback`。
- `APP_ADMIN_SECRET`：管理口令（如 WS 广播、服务态流程）。
- `APP_BAIDU_APP_ID`：分享接口所需 appid。

### 已处理的文档问题
- Swagger 警告 `Duplicate Operation ID me_auth_me_get`：已移除重复路由（`app/api/auth.py` 中的占位 `/auth/me`）。

### 验收标准
- 启动即有 Swagger 文档，主要接口均可在线调试
- JWT 鉴权生效，未授权访问被拦截并返回明确错误码
- Token 加密落库，明文不可见；主密钥仅通过环境变量注入
- WebSocket 能稳定推送进度/回调，断线可重连
- 下载限额按天生效，可配置调整
- 在腾讯云轻量完成可用部署，支持 HTTPS 与 WS 升级
- 基础监控可见（QPS、P95 延迟、错误率、WS 连接数）


---
来源（MCP 压缩包）： 


---
来源（MCP 压缩包）： 



热重载

cd /opt/web
. .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app --reload-dir @netdisk