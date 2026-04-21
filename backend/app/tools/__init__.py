"""app/tools — 工具统一管理顶层模块

将工具定义从 services/agent/tools/ 提升为顶层管理，提供：
- 基础类型：Tool, ToolContext, ToolResult
- 注册表：ToolRegistry（支持动态注册/注销）
- 执行器：ToolExecutor（超时控制 + 指标记录）
- 所有内置工具类

兼容层：services/core/tool_base.py 与 services/agent/tools/__init__.py
均已重定向到本模块，无需修改现有调用代码。
"""
from app.tools.base import Tool, ToolContext, ToolResult
from app.tools.registry import ToolRegistry
from app.tools.executor import ToolExecutor

__all__ = [
    # 基础类型
    "Tool",
    "ToolContext",
    "ToolResult",
    # 注册表 & 执行器
    "ToolRegistry",
    "ToolExecutor",
]
