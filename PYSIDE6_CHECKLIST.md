# PySide6 桌面应用开发检查清单

## ✅ 后端API完全暴露

### 🔧 **CORS配置**
- ✅ 已添加CORS中间件
- ✅ 支持PySide6桌面应用访问：
  - `http://localhost:*` (本地所有端口)
  - `http://127.0.0.1:*` (本地IP所有端口)
  - `file://*` (本地文件协议)
  - `*` (开发环境允许所有来源)
- ✅ 允许所有HTTP方法和请求头
- ✅ 支持凭据传递

### 📡 **API接口状态**
- ✅ 健康检查：`GET /health`
- ✅ API文档：`GET /docs` (Swagger UI)
- ✅ 认证接口：`POST /auth/login`, `POST /auth/register`
- ✅ 用户信息：`GET /auth/me`
- ✅ OAuth授权：`POST /oauth/device/start`, `POST /oauth/device/poll`
- ✅ MCP代理：`POST /mcp/user/exec`, `POST /mcp/public/exec`
- ✅ WebSocket：`ws://127.0.0.1:8000/ws`

### 🔑 **认证流程**
- ✅ JWT认证：`Authorization: Bearer <token>`
- ✅ 用户注册/登录
- ✅ 百度网盘扫码授权
- ✅ Token自动刷新

### 🖥️ **PySide6集成要点**

#### 1. **基础配置**
```python
import requests
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication, QMainWindow

class BaiduNetdiskClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.user_jwt: Optional[str] = None
        self.baidu_token: Optional[Dict[str, Any]] = None
        self.session = requests.Session()
```

#### 2. **认证流程**
```python
# 1. 用户注册/登录获取JWT
def login(self, username: str, password: str) -> bool:
    response = self.session.post(
        f"{self.base_url}/auth/login",
        json={"username": username, "password": password}
    )
    if response.status_code == 200:
        data = response.json()
        self.user_jwt = data.get("access_token")
        return True
    return False

# 2. 扫码授权获取百度token
def start_qr_auth(self) -> Optional[Dict[str, Any]]:
    response = self.session.post(
        f"{self.base_url}/oauth/device/start",
        headers={"Authorization": f"Bearer {self.user_jwt}"}
    )
    return response.json() if response.status_code == 200 else None

# 3. 轮询获取百度token
def poll_auth_status(self, device_code: str) -> Optional[Dict[str, Any]]:
    response = self.session.post(
        f"{self.base_url}/oauth/device/poll",
        params={"device_code": device_code},
        headers={"Authorization": f"Bearer {self.user_jwt}"}
    )
    return response.json() if response.status_code == 200 else None
```

#### 3. **API调用**
```python
# 调用百度网盘功能
def call_api(self, operation: str, args: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    response = self.session.post(
        f"{self.base_url}/mcp/user/exec",
        json={"op": operation, "args": args or {}},
        headers={"Authorization": f"Bearer {self.user_jwt}"}
    )
    return response.json() if response.status_code == 200 else None
```

#### 4. **二维码显示**
```python
import qrcode
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel
from io import BytesIO

class QRCodeWidget(QLabel):
    def set_qr_code(self, qr_url: str):
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue())
        self.setPixmap(pixmap.scaled(300, 300))
```

#### 5. **异步轮询**
```python
from PySide6.QtCore import QThread, Signal

class AuthThread(QThread):
    auth_success = Signal(dict)
    auth_failed = Signal(str)
    
    def run(self):
        max_attempts = 120  # 10分钟
        attempts = 0
        
        while self.running and attempts < max_attempts:
            result = self.client.poll_auth_status(self.device_code)
            
            if result:
                if result.get("status") == "ok":
                    self.auth_success.emit(result.get("data", {}))
                    break
                elif result.get("status") == "error":
                    self.auth_failed.emit(result.get("error", "授权失败"))
                    break
            
            self.msleep(5000)  # 5秒间隔
            attempts += 1
```

### 🚀 **可用的API操作**

#### 基础功能
- `quota` - 配额查询
- `list_files` - 文件列表
- `list_images` - 图片列表
- `list_docs` - 文档列表
- `list_videos` - 视频列表

#### 文件管理
- `mkdir` - 创建目录
- `delete` - 删除文件
- `move` - 移动文件
- `rename` - 重命名
- `copy` - 复制文件

#### 上传功能
- `upload_local` - 本地文件上传
- `upload_url` - URL文件上传
- `upload_text` - 文本内容上传
- `upload_batch_local` - 批量本地文件上传
- `upload_batch_url` - 批量URL文件上传
- `upload_batch_text` - 批量文本内容上传

#### 搜索功能
- `search_filename` - 文件名搜索
- `search_semantic` - 语义搜索

#### 分享功能
- `share_create` - 创建分享链接

#### 离线下载
- `offline_add` - 添加离线下载任务
- `offline_status` - 查询任务状态
- `offline_cancel` - 取消任务

### 🔧 **PySide6开发建议**

1. **依赖安装**：
   ```bash
   pip install PySide6 requests qrcode[pil]
   ```

2. **UI设计**：
   - 使用Qt Designer设计界面
   - 合理使用布局管理器
   - 添加进度条和状态提示

3. **异步处理**：
   - 使用QThread处理耗时操作
   - 避免阻塞UI线程
   - 合理使用信号槽机制

4. **错误处理**：
   - 所有网络请求都应该包含异常处理
   - 使用QMessageBox显示错误信息
   - 实现重试机制

5. **用户体验**：
   - 添加加载状态指示
   - 实现拖拽上传
   - 支持多文件选择

### 📝 **测试命令**

```bash
# 测试健康检查
curl http://127.0.0.1:8000/health

# 测试CORS
curl -H "Origin: http://localhost:8080" -X OPTIONS http://127.0.0.1:8000/health

# 测试API文档
open http://127.0.0.1:8000/docs
```

### 📁 **示例文件**

- `examples/pyside6_integration.py` - 完整的PySide6集成示例
- 包含：登录、扫码授权、文件管理、上传功能

## 🎉 **PySide6桌面应用可以开始开发了！**

后端API完全暴露，CORS配置正确，所有接口都可以正常调用。
PySide6桌面应用可以直接使用requests库调用后端API。
