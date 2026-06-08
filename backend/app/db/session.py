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
    _migrate_columns()


def _migrate_columns():
    """对已有表补充新列（幂等：列已存在则跳过）。"""
    migrations = [
        ("contracts", "source", "NVARCHAR(20) DEFAULT 'upload'"),
    ]

    try:
        with engine.connect() as conn:
            for table, col, col_spec in migrations:
                try:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD {col} {col_spec}")
                    conn.commit()
                    logger.info("DB 迁移: %s ADD %s %s", table, col, col_spec)
                except Exception:
                    conn.rollback()
                # 回填已有行的 NULL 值
                try:
                    conn.exec_driver_sql(
                        f"UPDATE {table} SET {col} = 'upload' WHERE {col} IS NULL"
                    )
                    conn.commit()
                    logger.info("DB 回填: %s SET %s = 'upload' WHERE NULL", table, col)
                except Exception:
                    conn.rollback()
    except Exception as e:
        logger.debug("DB 迁移跳过（可能未就绪）: %s", e)
