文件数据库导出说明
==================================================

导出时间: 2025-10-13 11:36:52
数据库文件: exported_files_20251013_113643.db

表结构说明:
- exported_files: 导出的文件信息表

字段说明:
- id: 自增主键
- file_name: 文件名
- file_path: 文件路径
- file_size: 文件大小（字节）
- fs_id: 百度网盘文件ID
- create_time: 创建时间（时间戳）
- modify_time: 修改时间（时间戳）
- file_md5: 文件MD5值
- category: 文件类别
- sync_id: 同步任务ID
- status: 文件状态
- export_time: 导出时间（时间戳）

使用方法:
1. 使用SQLite工具打开数据库文件
2. 查询所有文件: SELECT * FROM exported_files;
3. 按路径查询: SELECT * FROM exported_files WHERE file_path LIKE '/共享图集%';
4. 按类别查询: SELECT * FROM exported_files WHERE category = 4;
5. 按大小查询: SELECT * FROM exported_files WHERE file_size > 1000000;

注意事项:
- 此数据库仅包含文件元数据，不包含实际文件内容
- 文件路径为百度网盘中的完整路径
- fs_id可用于通过百度网盘API获取文件下载链接
