"""结构化日志配置

提供统一的日志格式和第三方库日志级别控制
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def setup_logging(debug: bool = False) -> logging.Logger:
    """配置结构化日志系统

    Args:
        debug: 是否启用 DEBUG 级别，默认 INFO

    Returns:
        配置好的根 logger
    """
    level = logging.DEBUG if debug else logging.INFO

    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台 handler（stdout）
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    # 文件 handler（RotatingFileHandler，写入 backend/server.log）
    log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # 配置根 logger（避免重复添加 handler）
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 防止重复添加 handler（lifespan 可能被多次调用）
    if not root_logger.handlers:
        root_logger.addHandler(stream_handler)
        root_logger.addHandler(file_handler)

    # 降低第三方库日志级别，避免刷屏
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)

    return root_logger
