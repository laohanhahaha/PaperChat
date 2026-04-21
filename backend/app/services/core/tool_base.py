"""兼容层 — 工具基类已迁移至 app.tools.base

本模块保留以向后兼容，所有定义从 app.tools.base 重导出。
新代码请直接从 app.tools 或 app.tools.base 导入。
"""
from app.tools.base import Tool, ToolContext, ToolResult  # noqa: F401

__all__ = ["Tool", "ToolContext", "ToolResult"]
