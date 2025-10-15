"""
数据库初始化脚本 - 更新检查相关表
"""
from sqlalchemy import create_engine, text
from app.core.config import settings
from app.core.db import Base, engine
from app.models.update import AppVersion, UpdateCheck

def init_update_tables():
    """初始化更新检查相关表"""
    try:
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        print("✅ 更新检查相关表创建成功")
        
        # 插入一些示例数据
        insert_sample_data()
        
    except Exception as e:
        print(f"❌ 创建表失败: {e}")
        raise

def insert_sample_data():
    """插入示例数据"""
    from sqlalchemy.orm import sessionmaker
    from datetime import datetime
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # 检查是否已有数据
        existing_version = db.query(AppVersion).first()
        if existing_version:
            print("📝 示例数据已存在，跳过插入")
            return
        
        # 插入示例版本数据
        sample_versions = [
            AppVersion(
                version="1.0.0-web",
                version_code=10000,
                platform="web",
                release_notes="Web版初始版本发布",
                download_url="https://example.com/downloads/app-v1.0.0.zip",
                file_size=52428800,  # 50MB
                file_hash="sha256:abc123def456",
                is_force_update=False,
                is_latest=False,
                created_at=datetime.now()
            ),
            AppVersion(
                version="1.1.0-web",
                version_code=10100,
                platform="web",
                release_notes="""Web版新功能：
- 添加了文件搜索功能
- 优化了上传速度
- 修复了已知问题

修复：
- 修复了登录状态丢失的问题
- 修复了文件下载失败的问题""",
                download_url="https://example.com/downloads/app-v1.1.0.zip",
                file_size=52428800,  # 50MB
                file_hash="sha256:def456ghi789",
                is_force_update=False,
                is_latest=True,
                created_at=datetime.now()
            ),
            AppVersion(
                version="1.0.0-desktop",
                version_code=10000,
                platform="desktop",
                release_notes="桌面版初始发布",
                download_url="https://example.com/downloads/app-desktop-v1.0.0.exe",
                file_size=104857600,  # 100MB
                file_hash="sha256:ghi789jkl012",
                is_force_update=False,
                is_latest=True,
                created_at=datetime.now()
            )
        ]
        
        for version in sample_versions:
            db.add(version)
        
        db.commit()
        print("✅ 示例数据插入成功")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 插入示例数据失败: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    init_update_tables()
