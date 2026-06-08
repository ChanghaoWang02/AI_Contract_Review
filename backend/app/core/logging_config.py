"""集中式日志配置 — 整个应用统一初始化入口

用法：在 main.py 启动时调用一次 `setup_logging()`。
各模块使用 `logging.getLogger(__name__)` 获取 logger，无需再次 import 本模块。
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional


# 默认格式：带时间戳、模块名、级别
CONSOLE_FORMAT = (
    "%(asctime)s.%(msecs)03d | %(levelname)-7s | %(name)s | %(message)s"
)
CONSOLE_DATE_FORMAT = "%H:%M:%S"

FILE_FORMAT = (
    "%(asctime)s.%(msecs)03d | %(levelname)-7s | %(name)s:%(lineno)d | %(message)s"
)
FILE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 颜色映射 (ANSI)，仅用于终端输出
LEVEL_COLORS: dict[int, str] = {
    logging.DEBUG: "\033[36m",     # 青色
    logging.INFO: "\033[32m",      # 绿色
    logging.WARNING: "\033[33m",   # 黄色
    logging.ERROR: "\033[31m",     # 红色
    logging.CRITICAL: "\033[35m",  # 紫色
}
RESET = "\033[0m"


class _ColoredFormatter(logging.Formatter):
    """终端带颜色的格式化器（仅 stderr 输出时启用）"""

    def format(self, record: logging.LogRecord) -> str:
        color = LEVEL_COLORS.get(record.levelno, "")
        if color and sys.stderr.isatty():
            record.levelname = f"{color}{record.levelname}{RESET}"
            record.name = f"\033[1m{record.name}{RESET}"
        return super().format(record)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_dir: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    console_enabled: bool = True,
) -> None:
    """
    初始化全局日志系统。

    Args:
        log_level: 全局最低日志级别 (DEBUG / INFO / WARNING / ERROR)
        log_file: 日志文件名（不含路径），如 "atcr.log"。为 None 则不写文件。
        log_dir: 日志文件目录，默认 "项目根目录/logs/"
        max_bytes: 单个日志文件最大字节数，超限自动轮转
        backup_count: 保留的轮转文件数量
        console_enabled: 是否输出到 stderr（开发环境建议开启）
    """
    root = logging.getLogger()

    # 清除已有 handler，避免重复初始化
    root.handlers.clear()

    level = getattr(logging, log_level.upper(), logging.INFO)
    root.setLevel(level)

    # ── 控制台 handler (stderr) ──
    if console_enabled:
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(level)
        console.setFormatter(
            _ColoredFormatter(CONSOLE_FORMAT, datefmt=CONSOLE_DATE_FORMAT)
        )
        root.addHandler(console)

    # ── 文件 handler (RotatingFileHandler) ──
    if log_file:
        if log_dir is None:
            # 默认放到项目根目录的 logs/ 下
            log_dir = str(Path(__file__).resolve().parent.parent.parent / "logs")
        log_path = Path(log_dir) / log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            str(log_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(
            logging.Formatter(FILE_FORMAT, datefmt=FILE_DATE_FORMAT)
        )
        root.addHandler(file_handler)

    # ── 抑制第三方库的 DEBUG 日志 ──
    for noisy in ("urllib3", "httpx", "openai", "dashscope", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # 记录日志系统启动
    logger = logging.getLogger(__name__)
    handlers_desc = []
    if console_enabled:
        handlers_desc.append("stderr")
    if log_file:
        handlers_desc.append(str(log_path))
    logger.info(
        "日志系统已初始化 | 级别=%s | 输出=%s",
        log_level.upper(),
        ", ".join(handlers_desc) if handlers_desc else "none",
    )


def get_logger(name: str) -> logging.Logger:
    """便捷方法：获取指定名称的 logger（等效于 logging.getLogger(name)）"""
    return logging.getLogger(name)
