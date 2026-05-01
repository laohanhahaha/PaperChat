"""FastAPI 依赖注入

从 app.state 获取服务实例，替代全局单例直接导入。
渐进式迁移：现有 from app.services.xxx import xxx 方式继续可用，
新路由推荐使用 Depends(get_xxx_service) 方式。

新增：ServiceContainer 提供作用域管理（SINGLETON / REQUEST）
- singleton 服务在 app 启动时注册一次
- request-scoped 服务每次请求创建新实例
- 保持现有 Depends(get_xxx_service) 接口向后兼容
"""
from __future__ import annotations

import enum
import logging
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from fastapi import Request

from app.services.rag_service import RAGService
from app.services.llm.llm_service import LLMService
from app.services.agent import AgentService  # 新版 agent 模块
from app.tools import ToolRegistry, ToolExecutor
from app.mcp_services import MCPManager
from app.skills import SkillRegistry
from app.services.health import HealthService

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# ServiceScope 枚举
# ---------------------------------------------------------------------------

class ServiceScope(enum.Enum):
    """服务作用域"""
    SINGLETON = "singleton"   # 全局单例，随 app 生命周期
    REQUEST = "request"       # 请求级别，每次请求新实例


# ---------------------------------------------------------------------------
# ServiceContainer
# ---------------------------------------------------------------------------

class ServiceContainer:
    """服务容器：管理服务的注册与作用域

    用法：
        container = ServiceContainer()
        container.register("rag_service", lambda: rag_service, ServiceScope.SINGLETON)
        container.register("db_session", create_session_factory, ServiceScope.REQUEST)

        # 从 app.state 获取
        svc = container.resolve("rag_service")
    """

    def __init__(self) -> None:
        # {name: (factory_or_instance, scope)}
        self._registry: Dict[str, tuple] = {}
        # singleton 缓存
        self._singletons: Dict[str, Any] = {}

    def register(
        self,
        name: str,
        factory: Callable[[], Any],
        scope: ServiceScope = ServiceScope.SINGLETON,
    ) -> None:
        """注册服务

        Args:
            name: 服务名称（与 app.state 属性名保持一致）
            factory: 无参工厂函数，返回服务实例
            scope: SINGLETON（默认）或 REQUEST
        """
        self._registry[name] = (factory, scope)
        logger.debug(f"[ServiceContainer] 注册服务: {name} ({scope.value})")

    def register_instance(self, name: str, instance: Any) -> None:
        """直接注册已存在的单例实例（快捷方式）"""
        self._registry[name] = (lambda: instance, ServiceScope.SINGLETON)
        self._singletons[name] = instance

    def resolve(self, name: str) -> Any:
        """解析服务

        - SINGLETON: 首次调用时初始化并缓存
        - REQUEST: 每次调用均调用工厂创建新实例
        """
        if name not in self._registry:
            raise KeyError(f"[ServiceContainer] 未注册的服务: {name}")
        factory, scope = self._registry[name]
        if scope == ServiceScope.SINGLETON:
            if name not in self._singletons:
                self._singletons[name] = factory()
                logger.debug(f"[ServiceContainer] 单例初始化: {name}")
            return self._singletons[name]
        # REQUEST scope: 每次创建新实例
        return factory()

    def bind_to_app_state(self, app_state: Any) -> None:
        """将所有已注册的 singleton 服务绑定到 app.state（方便向后兼容）"""
        for name, (factory, scope) in self._registry.items():
            if scope == ServiceScope.SINGLETON:
                instance = self.resolve(name)
                setattr(app_state, name, instance)
                logger.debug(f"[ServiceContainer] 已绑定到 app.state.{name}")


# 全局服务容器（在 main.py lifespan 中由 StartupManager 填充）
service_container = ServiceContainer()


# ---------------------------------------------------------------------------
# 向后兼容的依赖函数（保持原有 Depends 接口不变）
# ---------------------------------------------------------------------------

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


def get_config_service(request: Request):
    """从 app.state 获取 ConfigService（四层覆盖链配置服务）

    用法:
        from app.dependencies import get_config_service
        from fastapi import Depends

        @router.get("/...")
        async def endpoint(cfg = Depends(get_config_service)):
            debug = cfg.get("DEBUG", False)
            chunk_size = cfg.get("rag.chunk_size", 512)
    """
    from app.config import ConfigService  # 延迟导入，避免循环依赖
    return request.app.state.config_service


def get_health_service(request: Request) -> HealthService:
    """从 app.state 获取 HealthService（通用服务健康监控）

    用法:
        from app.dependencies import get_health_service
        from fastapi import Depends

        @router.get("/...")
        async def endpoint(health = Depends(get_health_service)):
            status = health.get_cached_status()
    """
    return request.app.state.health_service


