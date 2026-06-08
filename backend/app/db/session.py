"""数据库连接管理"""

import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# SQL Server 需要特殊配置
connect_args = {
    "timeout": 30,
    "TrustServerCertificate": "yes",
}

engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args=connect_args,
    pool_size=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)

logger.info("数据库引擎已创建 | server=%s | db=%s | pool=%d", settings.db_server, settings.db_name, 10)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI 依赖: 获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)
