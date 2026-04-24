"""FastAPI 依赖注入

从 app.state 获取服务实例，替代全局单例直接导入。
渐进式迁移：现有 from app.services.xxx import xxx 方式继续可用，
新路由推荐使用 Depends(get_xxx_service) 方式。
"""
from fastapi import Request

from app.services.rag_service import RAGService
from app.services.llm.llm_service import LLMService
from app.services.agent import AgentService  # 新版 agent 模块
from app.tools import ToolRegistry, ToolExecutor
from app.mcp_services import MCPManager
from app.skills import SkillRegistry


def get_rag_service(request: Request) -> RAGService:
    """从 app.state 获取 RAG 服务实例"""
    return request.app.state.rag_service


def get_llm_service(request: Request) -> LLMService:
    """从 app.state 获取 LLM 服务实例"""
    return request.app.state.llm_service


def get_agent_service(request: Request) -> AgentService:
    """从 app.state 获取 Agent 服务实例"""
    return request.app.state.agent_service


def get_tool_registry(request: Request) -> ToolRegistry:
    """从 app.state 获取工具注册表"""
    return request.app.state.tool_registry


def get_tool_executor(request: Request) -> ToolExecutor:
    """从 app.state 获取工具执行器"""
    return request.app.state.tool_executor


def get_mcp_manager(request: Request) -> MCPManager:
    """从 app.state 获取 MCP 管理器"""
    return request.app.state.mcp_manager


def get_skill_registry(request: Request) -> SkillRegistry:
    """从 app.state 获取 Skill 注册表"""
    return request.app.state.skill_registry
