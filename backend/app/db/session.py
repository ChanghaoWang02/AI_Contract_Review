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
        ("contracts", "source", "NVARCHAR(20) DEFAULT 'upload'", "'upload'"),
        ("contracts", "parent_contract_id", "INTEGER NULL", None),
        ("contracts", "source_lang", "NVARCHAR(10) NULL", None),
        ("contracts", "target_lang", "NVARCHAR(10) NULL", None),
    ]
    # 外键迁移（与列迁移分开 — FK 需要单独处理，幂等）
    fk_migrations = [
        (
            "contracts",
            "FK_contracts_parent",
            "FOREIGN KEY (parent_contract_id) REFERENCES contracts(id) ON DELETE CASCADE",
        ),
    ]

    try:
        with engine.connect() as conn:
            for table, col, col_spec, backfill in migrations:
                try:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD {col} {col_spec}")
                    conn.commit()
                    logger.info("DB 迁移: %s ADD %s %s", table, col, col_spec)
                except Exception:
                    conn.rollback()
                # 回填已有行的 NULL 值（仅当指定了回填值时）
                if backfill is not None:
                    try:
                        conn.exec_driver_sql(
                            f"UPDATE {table} SET {col} = {backfill} WHERE {col} IS NULL"
                        )
                        conn.commit()
                        logger.info("DB 回填: %s SET %s = %s WHERE NULL", table, col, backfill)
                    except Exception:
                        conn.rollback()
            for table, fk_name, fk_def in fk_migrations:
                try:
                    conn.exec_driver_sql(
                        f"ALTER TABLE {table} ADD CONSTRAINT {fk_name} {fk_def}"
                    )
                    conn.commit()
                    logger.info("DB FK 迁移: %s ADD %s", table, fk_name)
                except Exception:
                    conn.rollback()
    except Exception as e:
        logger.debug("DB 迁移跳过（可能未就绪）: %s", e)
