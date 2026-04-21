"""工具注册表 — 统一管理所有可用工具的生命周期

ToolRegistry 提供注册、查找、列举和注销工具的能力，
支持 MCP 工具的动态注册与注销。
"""
from typing import Dict, List, Optional
from app.tools.base import Tool


class ToolRegistry:
    """工具注册表，维护工具名称到工具实例的映射"""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册单个工具。重名时覆盖旧实例。"""
        self._tools[tool.name] = tool

    def register_many(self, tools: List[Tool]) -> None:
        """批量注册工具"""
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> Optional[Tool]:
        """按名称获取工具，不存在时返回 None"""
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        """返回所有已注册工具的列表（顺序不保证）"""
        return list(self._tools.values())

    def get_schemas(self) -> List[dict]:
        """返回所有工具的 JSON Schema 列表，供 ReAct Prompt 使用"""
        return [tool.get_schema() for tool in self._tools.values()]

    def has(self, name: str) -> bool:
        """判断指定名称的工具是否已注册"""
        return name in self._tools

    def unregister(self, name: str) -> None:
        """注销指定工具（用于 MCP 工具动态注销）。工具不存在时静默忽略。"""
        self._tools.pop(name, None)

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        names = list(self._tools.keys())
        return f"ToolRegistry(tools={names})"
