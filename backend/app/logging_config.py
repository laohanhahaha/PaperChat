"""结构化日志配置

提供统一的日志格式和第三方库日志级别控制
"""
import logging
import sys


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

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # 配置根 logger（避免重复添加 handler）
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 防止重复添加 handler（lifespan 可能被多次调用）
    if not root_logger.handlers:
        root_logger.addHandler(handler)

    # 降低第三方库日志级别，避免刷屏
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)

    return root_logger
