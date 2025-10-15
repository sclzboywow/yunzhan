# 创建新版本范例

## 📦 场景：发布新版本 v1.2.0

假设您有一个新的安装包 `myapp-v1.2.0.zip`，需要发布给用户。

### 1. 准备文件信息

```bash
# 查看文件大小
ls -l myapp-v1.2.0.zip
# 输出：-rw-r--r-- 1 user user 52428800 Jan 15 14:30 myapp-v1.2.0.zip

# 计算文件哈希值
sha256sum myapp-v1.2.0.zip
# 输出：a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456  myapp-v1.2.0.zip
```

### 2. 上传安装包到服务器

```bash
# 上传到您的服务器
scp myapp-v1.2.0.zip user@yourdomain.com:/var/www/downloads/

# 确保可以通过HTTP访问
# 例如：https://yourdomain.com/downloads/myapp-v1.2.0.zip
```

### 3. 创建新版本记录

```bash
curl -X POST "http://localhost:8000/update/versions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -d '{
    "version": "1.2.0",
    "version_code": 10200,
    "platform": "web",
    "release_notes": "版本 1.2.0 更新内容：

新功能：
- 添加了文件搜索功能
- 新增批量下载功能
- 优化了用户界面

修复：
- 修复了登录状态丢失的问题
- 修复了文件上传失败的问题
- 修复了内存泄漏问题

性能优化：
- 提升了文件加载速度
- 减少了内存占用
- 优化了网络请求",
    "download_url": "https://yourdomain.com/downloads/myapp-v1.2.0.zip",
    "file_size": 52428800,
    "file_hash": "sha256:a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
    "is_force_update": false,
    "is_latest": true
  }'
```

### 4. 成功响应示例

```json
{
  "version": "1.2.0",
  "version_code": 10200,
  "platform": "web",
  "release_notes": "版本 1.2.0 更新内容：\n\n新功能：\n- 添加了文件搜索功能\n- 新增批量下载功能\n- 优化了用户界面\n\n修复：\n- 修复了登录状态丢失的问题\n- 修复了文件上传失败的问题\n- 修复了内存泄漏问题\n\n性能优化：\n- 提升了文件加载速度\n- 减少了内存占用\n- 优化了网络请求",
  "download_url": "https://yourdomain.com/downloads/myapp-v1.2.0.zip",
  "file_size": 52428800,
  "file_hash": "sha256:a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
  "is_force_update": false,
  "is_latest": true,
  "created_at": "2025-01-15T14:30:00.000000"
}
```

### 5. 验证新版本

```bash
# 检查更新（使用旧版本号）
curl "http://localhost:8000/update/check?client_version=1.1.0&client_platform=web"

# 应该返回有更新
{
  "has_update": true,
  "current_version": "1.1.0",
  "latest_version": "1.2.0",
  "latest_version_info": {
    "version": "1.2.0",
    "version_code": 10200,
    "platform": "web",
    "release_notes": "版本 1.2.0 更新内容：...",
    "download_url": "https://yourdomain.com/downloads/myapp-v1.2.0.zip",
    "file_size": 52428800,
    "file_hash": "sha256:a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
    "is_force_update": false,
    "is_latest": true,
    "created_at": "2025-01-15T14:30:00.000000"
  },
  "force_update": false,
  "message": "发现新版本"
}
```

## 🔧 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `version` | 版本号（唯一） | "1.2.0" |
| `version_code` | 版本代码（用于比较） | 10200 |
| `platform` | 平台类型 | "web", "desktop", "mobile" |
| `release_notes` | 发布说明 | 详细的更新内容 |
| `download_url` | 下载链接 | 完整的HTTP/HTTPS链接 |
| `file_size` | 文件大小（字节） | 52428800 |
| `file_hash` | 文件哈希值 | "sha256:..." |
| `is_force_update` | 是否强制更新 | true/false |
| `is_latest` | 是否为最新版本 | true/false |

## 📝 版本代码计算

版本号 `x.y.z` 转换为版本代码：
- `1.2.0` → `10200` (1×10000 + 2×100 + 0)
- `1.2.1` → `10201` (1×10000 + 2×100 + 1)
- `2.0.0` → `20000` (2×10000 + 0×100 + 0)

## ⚠️ 注意事项

1. **版本号唯一性**：每个版本号只能存在一次
2. **最新版本标记**：设置 `is_latest=true` 会自动将同平台其他版本设为 `false`
3. **强制更新**：谨慎使用 `is_force_update=true`，会强制用户更新
4. **下载链接**：确保链接有效且可访问
5. **文件哈希**：用于验证文件完整性
