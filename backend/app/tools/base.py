"""工具基类定义 — app/tools 顶层模块的核心抽象

提供 Tool、ToolContext、ToolResult 三个基础类型。
原始定义来自 services/core/tool_base.py，提升为顶层管理。
"""
from typing import Optional, List, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolContext:
    """统一的工具执行上下文"""
    db: Optional[object] = None  # AsyncSession
    paper_id: Optional[int] = None
    paper_ids: List[int] = field(default_factory=list)
    user_id: Optional[int] = None
    session_id: Optional[int] = None
    mcp_manager: Optional[Any] = None
    enable_search: bool = False


@dataclass
class ToolResult:
    """统一的工具返回值"""
    success: bool = True
    data: dict = field(default_factory=dict)
    error: Optional[str] = None


class Tool(ABC):
    name: str
    description: str
    parameters: dict = {}  # JSON Schema 描述参数

    def get_schema(self) -> dict:
        """返回工具的完整 schema，供 ReAct Prompt 使用"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

    @abstractmethod
    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        pass
