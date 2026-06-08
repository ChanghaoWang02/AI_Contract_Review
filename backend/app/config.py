"""应用配置管理"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache
from urllib.parse import quote_plus


class Settings(BaseSettings):
    # 应用
    app_name: str = "ATCR - AI 合同审核系统"
    debug: bool = True

    # 数据库 (SQL Server)
    db_server: str = "localhost"
    db_port: int = 1433
    db_name: str = "ATCR"
    db_user: str = "sa"
    db_password: str = ""
    db_driver: str = "ODBC Driver 17 for SQL Server"

    # LLM 默认配置
    llm_default_provider: str = "claude"
    llm_fallback_providers: list[str] = ["openai", "qwen"]

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_default_model: str = "claude-sonnet-4-6"

    # OpenAI
    openai_api_key: str = ""
    openai_default_model: str = "gpt-4o"

    # 通义千问 (DashScope)
    dashscope_api_key: str = ""
    qwen_default_model: str = "qwen-max"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_default_model: str = "deepseek-chat"

    # 文件上传
    max_upload_size_mb: int = 20
    allowed_extensions: list[str] = ["pdf", "docx", "txt"]

    # 日志
    log_level: str = "INFO"         # DEBUG | INFO | WARNING | ERROR
    log_file: str = "atcr.log"      # 日志文件名；设为空字符串 "" 则只输出到终端
    log_dir: str = ""               # 日志目录；空字符串 = 自动使用 backend/logs/
    log_max_bytes: int = 10_485_760 # 单文件最大 10 MB
    log_backup_count: int = 5       # 保留 5 个轮转文件

    # 审核
    review_default_temperature: float = 0.3
    review_max_tokens: int = 16384

    @property
    def database_url(self) -> str:
        # 本地连接不指定端口，让 ODBC 走共享内存
        host = self.db_server if self.db_server != "localhost" else "localhost"
        port_suffix = f":{self.db_port}" if host != "localhost" else ""
        return (
            f"mssql+pyodbc://{self.db_user}:{quote_plus(self.db_password)}"
            f"@{host}{port_suffix}/{self.db_name}"
            f"?driver={self.db_driver.replace(' ', '+')}"
        )

    @property
    def database_url_sync(self) -> str:
        """同步驱动 (用于 Alembic)"""
        return self.database_url

    class Config:
        env_file = str(Path(__file__).resolve().parent.parent / ".env")
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
