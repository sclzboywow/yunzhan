"""
文件服务
"""
import sqlite3
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from app.models.file import FileInfo, FileListRequest, FileListResponse, FileStatsResponse
from app.core.config import settings

logger = logging.getLogger(__name__)


class FileService:
    """文件服务类"""
    
    def __init__(self):
        self.db_path = Path(settings.data_dir) / "baidu_netdisk.db"
        if not self.db_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
        return conn
    
    def get_file_list(self, request: FileListRequest) -> FileListResponse:
        """获取文件列表（分页）"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建WHERE条件
                where_conditions = []
                params = []
                
                if request.file_path:
                    where_conditions.append("file_path LIKE ?")
                    params.append(f"%{request.file_path}%")
                
                if request.category is not None:
                    where_conditions.append("category = ?")
                    params.append(request.category)
                
                if request.file_size_min is not None:
                    where_conditions.append("file_size >= ?")
                    params.append(request.file_size_min)
                
                if request.file_size_max is not None:
                    where_conditions.append("file_size <= ?")
                    params.append(request.file_size_max)
                
                if request.status:
                    where_conditions.append("status = ?")
                    params.append(request.status)
                
                where_clause = ""
                if where_conditions:
                    where_clause = "WHERE " + " AND ".join(where_conditions)
                
                # 获取总数
                count_sql = f"SELECT COUNT(*) FROM exported_files {where_clause}"
                cursor.execute(count_sql, params)
                total = cursor.fetchone()[0]
                
                # 计算分页信息
                total_pages = (total + request.page_size - 1) // request.page_size
                offset = (request.page - 1) * request.page_size
                
                # 构建ORDER BY子句
                order_by = request.order_by
                if order_by not in ["id", "file_name", "file_path", "file_size", "create_time", "modify_time", "export_time"]:
                    order_by = "id"
                
                order_direction = "DESC" if request.order_desc else "ASC"
                order_clause = f"ORDER BY {order_by} {order_direction}"
                
                # 获取分页数据
                sql = f"""
                    SELECT id, file_name, file_path, file_size, fs_id, create_time, 
                           modify_time, file_md5, category, sync_id, status, export_time
                    FROM exported_files 
                    {where_clause}
                    {order_clause}
                    LIMIT ? OFFSET ?
                """
                cursor.execute(sql, params + [request.page_size, offset])
                
                files = []
                for row in cursor.fetchall():
                    file_info = FileInfo(
                        id=row["id"],
                        file_name=row["file_name"],
                        file_path=row["file_path"],
                        file_size=row["file_size"],
                        fs_id=row["fs_id"],
                        create_time=row["create_time"],
                        modify_time=row["modify_time"],
                        file_md5=row["file_md5"],
                        category=row["category"],
                        sync_id=row["sync_id"],
                        status=row["status"],
                        export_time=row["export_time"]
                    )
                    files.append(file_info)
                
                return FileListResponse(
                    files=files,
                    total=total,
                    page=request.page,
                    page_size=request.page_size,
                    total_pages=total_pages,
                    has_next=request.page < total_pages,
                    has_prev=request.page > 1
                )
                
        except Exception as e:
            logger.error(f"获取文件列表失败: {e}")
            raise
    
    def get_file_stats(self) -> FileStatsResponse:
        """获取文件统计信息"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 总文件数和总大小
                cursor.execute("SELECT COUNT(*), SUM(file_size) FROM exported_files")
                total_files, total_size = cursor.fetchone()
                total_size = total_size or 0
                
                # 按类别统计
                cursor.execute("SELECT category, COUNT(*) FROM exported_files GROUP BY category")
                category_stats = {row[0]: row[1] for row in cursor.fetchall()}
                
                # 按状态统计
                cursor.execute("SELECT status, COUNT(*) FROM exported_files GROUP BY status")
                status_stats = {row[0]: row[1] for row in cursor.fetchall()}
                
                # 按路径统计（前10个）
                cursor.execute("""
                    SELECT 
                        CASE 
                            WHEN file_path LIKE '/%' THEN 
                                '/' || substr(file_path, 2, instr(substr(file_path, 2), '/') - 1)
                            ELSE '根目录'
                        END as path_prefix,
                        COUNT(*) as count
                    FROM exported_files 
                    GROUP BY path_prefix
                    ORDER BY count DESC
                    LIMIT 10
                """)
                path_stats = {row[0]: row[1] for row in cursor.fetchall()}
                
                return FileStatsResponse(
                    total_files=total_files,
                    total_size=total_size,
                    category_stats=category_stats,
                    status_stats=status_stats,
                    path_stats=path_stats
                )
                
        except Exception as e:
            logger.error(f"获取文件统计失败: {e}")
            raise
    
    def get_file_by_id(self, file_id: int) -> Optional[FileInfo]:
        """根据ID获取文件信息"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, file_name, file_path, file_size, fs_id, create_time, 
                           modify_time, file_md5, category, sync_id, status, export_time
                    FROM exported_files 
                    WHERE id = ?
                """, (file_id,))
                
                row = cursor.fetchone()
                if row:
                    return FileInfo(
                        id=row["id"],
                        file_name=row["file_name"],
                        file_path=row["file_path"],
                        file_size=row["file_size"],
                        fs_id=row["fs_id"],
                        create_time=row["create_time"],
                        modify_time=row["modify_time"],
                        file_md5=row["file_md5"],
                        category=row["category"],
                        sync_id=row["sync_id"],
                        status=row["status"],
                        export_time=row["export_time"]
                    )
                return None
                
        except Exception as e:
            logger.error(f"获取文件信息失败: {e}")
            raise
    
    def search_files(self, keyword: str, limit: int = 100) -> List[FileInfo]:
        """搜索文件"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, file_name, file_path, file_size, fs_id, create_time, 
                           modify_time, file_md5, category, sync_id, status, export_time
                    FROM exported_files 
                    WHERE file_name LIKE ? OR file_path LIKE ?
                    ORDER BY id DESC
                    LIMIT ?
                """, (f"%{keyword}%", f"%{keyword}%", limit))
                
                files = []
                for row in cursor.fetchall():
                    file_info = FileInfo(
                        id=row["id"],
                        file_name=row["file_name"],
                        file_path=row["file_path"],
                        file_size=row["file_size"],
                        fs_id=row["fs_id"],
                        create_time=row["create_time"],
                        modify_time=row["modify_time"],
                        file_md5=row["file_md5"],
                        category=row["category"],
                        sync_id=row["sync_id"],
                        status=row["status"],
                        export_time=row["export_time"]
                    )
                    files.append(file_info)
                
                return files
                
        except Exception as e:
            logger.error(f"搜索文件失败: {e}")
            raise
