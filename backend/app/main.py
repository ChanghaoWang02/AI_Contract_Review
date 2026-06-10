"""FastAPI 应用入口"""

import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.config import get_settings
from app.core.logging_config import setup_logging
from app.db.session import init_db, SessionLocal
from app.api import contracts, reviews, chat, rules, draft, translate

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    settings = get_settings()

    # 初始化日志系统（最先执行，确保后续代码有日志可用）
    setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file or None,
        log_dir=settings.log_dir or None,
        max_bytes=settings.log_max_bytes,
        backup_count=settings.log_backup_count,
    )

    logger.info("启动 %s | 默认 LLM: %s", settings.app_name, settings.llm_default_provider)

    # 自动创建数据库表 + 导入默认规则
    try:
        init_db()
        logger.info("数据库表已就绪")
        from app.db.init_db import seed_default_rules
        seed_default_rules()
    except Exception as e:
        logger.warning("数据库初始化跳过 (SQL Server 可能未启动): %s", e)

    yield

    logger.info("应用已关闭")


app = FastAPI(
    title=get_settings().app_name,
    description="基于生成式 AI 的合同审核系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境全允许
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(contracts.router, prefix="/api/contracts", tags=["合同管理"])
app.include_router(reviews.router, prefix="/api/reviews", tags=["审核管理"])
app.include_router(chat.router, prefix="/api/chat", tags=["AI 对话"])
app.include_router(rules.router, prefix="/api/rules", tags=["审核规则"])
app.include_router(draft.router, prefix="/api/draft", tags=["合同起草"])
app.include_router(translate.router, prefix="/api/translate", tags=["合同翻译"])


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """请求日志中间件：记录每个 HTTP 请求的方法、路径、状态码、耗时"""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000

    # /api/health 和静态资源不记录，避免噪音
    if request.url.path not in ("/api/health", "/", "/favicon.ico"):
        logger.info(
            "%s %s → %d | %.0fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

    return response


@app.get("/")
async def root():
    return RedirectResponse(url="/docs")

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": get_settings().app_name}
