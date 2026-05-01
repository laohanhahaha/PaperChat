"""ConfigAgent 专用工具集

提供 5 个配置管理工具，供 ConfigAgent 通过 ReAct 循环调用。
工具通过闭包注入 MCPManager / HealthService / SettingsService 等服务引用，
无需修改 ToolContext 定义。

性能影响：
- list_available_services / get_service_status：纯内存读取 + O(1) 查找，<5ms
- configure_service：启动 MCP Server 子进程，约 1-3s
- validate_service：HTTP 健康检查，约 200ms-2s
- update_api_key：HTTP 验证 + DB 写入，约 300ms-2s
"""
import os
import logging
from typing import Optional

from app.tools.base import Tool, ToolContext, ToolResult
from app.mcp_services.academic_config import get_mcp_server_configs

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# 服务元数据（名称、描述、是否需要 API Key、环境变量映射）
# ------------------------------------------------------------------

_SERVICE_REGISTRY = {
    "academic_mcp": {
        "display_name": "Academic MCP",
        "description": "学术论文搜索、下载与阅读，覆盖 arXiv、PubMed、Google Scholar 等 18 个平台（免费，无需 API Key）",
        "requires_api_key": False,
        "env_vars": {},
    },
    "open_websearch": {
        "display_name": "Open WebSearch",
        "description": "通用网络搜索，支持 9 个搜索引擎（免费，无需 API Key）",
        "requires_api_key": False,
        "env_vars": {},
    },
}


class ListAvailableServicesTool(Tool):
    """列出所有可配置的外部服务及其状态"""

    name = "list_available_services"
    description = "列出所有可配置的外部服务及其状态，包括是否已配置、是否需要 API Key"
    parameters = {"type": "object", "properties": {}, "required": []}

    def __init__(self, mcp_manager=None):
        self._mcp_manager = mcp_manager

    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        services = []
        for svc_name, meta in _SERVICE_REGISTRY.items():
            configured = False
            if self._mcp_manager:
                configured = svc_name in self._mcp_manager._clients

            services.append({
                "name": svc_name,
                "display_name": meta["display_name"],
                "description": meta["description"],
                "requires_api_key": meta.get("requires_api_key", False),
                "optional_api_key": meta.get("optional_api_key", False),
                "is_configured": configured,
            })

        return ToolResult(success=True, data={"services": services, "total": len(services)})


class ConfigureServiceTool(Tool):
    """配置指定的外部服务"""

    name = "configure_service"
    description = "配置指定的外部服务，设置 API Key 和环境变量，并启动服务"
    parameters = {
        "type": "object",
        "properties": {
            "service_name": {"type": "string", "description": "服务名称（如 academic_mcp, open_websearch）"},
            "api_key": {"type": "string", "description": "API Key（如需要）"},
            "settings": {"type": "object", "description": "额外配置参数（如 Zotero 的 library_id）"},
        },
        "required": ["service_name"],
    }

    def __init__(self, mcp_manager=None, tool_registry=None, event_bus=None):
        self._mcp_manager = mcp_manager
        self._tool_registry = tool_registry
        self._event_bus = event_bus

    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        service_name = kwargs.get("service_name", "").lower().strip()
        api_key = kwargs.get("api_key", "")
        extra_settings = kwargs.get("settings", {})

        if service_name not in _SERVICE_REGISTRY:
            available = ", ".join(_SERVICE_REGISTRY.keys())
            return ToolResult(
                success=False,
                error=f"未知服务: {service_name}。可用服务: {available}",
            )

        meta = _SERVICE_REGISTRY[service_name]

        # MCP Server 配置
        return await self._configure_mcp_server(service_name, api_key, extra_settings, meta)

    async def _configure_mcp_server(self, service_name, api_key, extra_settings, meta):
        """配置 MCP Server 类服务"""
        if self._mcp_manager is None:
            return ToolResult(success=False, error="MCPManager 未初始化")

        # 查找 academic_config 中对应的 MCPServerConfig
        server_configs = get_mcp_server_configs()
        target_config = None
        for cfg in server_configs:
            if cfg.name == service_name:
                target_config = cfg
                break

        if target_config is None:
            return ToolResult(
                success=False,
                error=f"在 academic_config 中未找到服务: {service_name}",
            )

        # 设置 API Key 和环境变量
        env_updates = {}
        if api_key:
            for env_key in meta.get("env_vars", {}):
                if "API_KEY" in env_key:
                    env_updates[env_key] = api_key
                    os.environ[env_key] = api_key

        # 处理额外配置
        if extra_settings:
            for key, val in extra_settings.items():
                env_updates[key.upper()] = str(val)
                os.environ[key.upper()] = str(val)

        # 更新 config 的 env 和 enabled
        updated_env = {**target_config.env, **env_updates}
        target_config.env = updated_env
        target_config.enabled = True

        # 如果已存在，先移除再添加
        if service_name in self._mcp_manager._clients:
            await self._mcp_manager.remove_server(service_name)

        # 调用 MCPManager.add_server() 启动
        try:
            await self._mcp_manager.add_server(target_config)

            # 配置成功后联动：桥接 MCP 工具到 ToolRegistry
            await self._bridge_mcp_tools(service_name)

            # 持久化配置到数据库
            await self._persist_mcp_config(service_name)

            # 通过事件总线推送 config_update 事件
            await self._notify_config_update(service_name, meta)

            return ToolResult(
                success=True,
                data={
                    "service": service_name,
                    "status": "configured",
                    "message": f"{meta['display_name']} 已配置并启动",
                    "env_updated": list(env_updates.keys()),
                },
            )
        except Exception as e:
            logger.error(f"[ConfigureServiceTool] 配置 {service_name} 失败: {e}")
            return ToolResult(
                success=False,
                error=f"配置 {meta['display_name']} 失败: {str(e)[:200]}",
            )

    # ------------------------------------------------------------------
    # 配置联动辅助方法
    # ------------------------------------------------------------------

    async def _bridge_mcp_tools(self, service_name: str):
        """将新配置服务的 MCP 工具桥接到 ToolRegistry

        性能影响：list_tools 调用约 200-500ms，register_many O(n) <1ms。
        """
        if self._tool_registry is None or self._mcp_manager is None:
            logger.debug(f"[ConfigureServiceTool] ToolRegistry 或 MCPManager 不可用，跳过桥接")
            return

        try:
            from app.mcp_services.bridge import MCPToolBridge
            bridge = MCPToolBridge(self._mcp_manager)
            mcp_tools = await bridge.bridge_all()
            if mcp_tools:
                self._tool_registry.register_many(mcp_tools)
                logger.info(f"[ConfigureServiceTool] 已桥接 {len(mcp_tools)} 个 MCP 工具到 ToolRegistry")
        except Exception as e:
            logger.error(f"[ConfigureServiceTool] MCP 工具桥接失败: {e}")

    async def _persist_mcp_config(self, service_name: str):
        """将已配置的服务持久化到 user_settings 的 mcp 分组

        mcp.status 字段以 JSON 格式存储 {"enabled_services": [...]}
        """
        try:
            from app.database import AsyncSessionLocal
            from app.services.settings_service import settings_service
            from app.config import settings as app_settings
            import json

            async with AsyncSessionLocal() as db:
                values = await settings_service.get_setting_values(
                    user_id=app_settings.DEFAULT_USER_ID, db=db
                )

            mcp_values = values.get("mcp", {})
            status_str = mcp_values.get("status", "")

            # 解析已有配置
            if status_str:
                try:
                    mcp_config = json.loads(status_str) if isinstance(status_str, str) else status_str
                except (json.JSONDecodeError, TypeError):
                    mcp_config = {}
            else:
                mcp_config = {}

            enabled = list(set(mcp_config.get("enabled_services", []) + [service_name]))
            mcp_config["enabled_services"] = enabled

            # 回写
            async with AsyncSessionLocal() as db:
                await settings_service.update_settings(
                    user_id=app_settings.DEFAULT_USER_ID,
                    settings={"mcp": {"status": json.dumps(mcp_config)}},
                    db=db,
                )
            logger.info(f"[ConfigureServiceTool] 已持久化 MCP 配置: {service_name}")
        except Exception as e:
            logger.error(f"[ConfigureServiceTool] 持久化 MCP 配置失败（非阻断）: {e}")

    async def _notify_config_update(self, service_name: str, meta: dict):
        """通过事件总线推送 config_update 事件"""
        try:
            from app.services.event_bus import event_bus, Event, EventTypes

            # 定义 CONFIG_UPDATED 事件类型（如不存在则直接使用字符串）
            event_type = getattr(EventTypes, "CONFIG_UPDATED", "config_updated")
            await event_bus.publish(Event(
                type=event_type,
                data={
                    "service": service_name,
                    "display_name": meta.get("display_name", service_name),
                    "action": "configured",
                },
            ))
            logger.info(f"[ConfigureServiceTool] config_update 事件已发布: {service_name}")
        except Exception as e:
            logger.error(f"[ConfigureServiceTool] config_update 事件发布失败（非阻断）: {e}")


class ValidateServiceTool(Tool):
    """验证指定服务的连通性和配置正确性"""

    name = "validate_service"
    description = "验证指定服务的连通性和配置正确性，检查服务是否可正常使用"
    parameters = {
        "type": "object",
        "properties": {
            "service_name": {"type": "string", "description": "服务名称"},
        },
        "required": ["service_name"],
    }

    def __init__(self, mcp_manager=None, health_service=None, settings_service=None):
        self._mcp_manager = mcp_manager
        self._health_service = health_service
        self._settings_service = settings_service

    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        service_name = kwargs.get("service_name", "").lower().strip()

        if service_name not in _SERVICE_REGISTRY:
            available = ", ".join(_SERVICE_REGISTRY.keys())
            return ToolResult(success=False, error=f"未知服务: {service_name}。可用服务: {available}")

        meta = _SERVICE_REGISTRY[service_name]

        # MCP Server 健康检查
        return await self._validate_mcp_server(service_name, meta)

    async def _validate_mcp_server(self, service_name, meta):
        """通过 MCPManager 健康检查验证 MCP Server"""
        if self._mcp_manager is None:
            return ToolResult(success=False, error="MCPManager 未初始化")

        if service_name not in self._mcp_manager._clients:
            return ToolResult(
                success=True,
                data={
                    "service": service_name,
                    "valid": False,
                    "message": f"{meta['display_name']} 未配置",
                },
            )

        try:
            health_results = await self._mcp_manager.health_check_all()
            is_healthy = health_results.get(service_name, False)

            return ToolResult(
                success=True,
                data={
                    "service": service_name,
                    "valid": is_healthy,
                    "message": f"{meta['display_name']} {'连通正常' if is_healthy else '连接异常'}",
                },
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"健康检查失败: {str(e)[:200]}",
            )


class GetServiceStatusTool(Tool):
    """获取所有已配置服务的运行状态"""

    name = "get_service_status"
    description = "获取所有已配置服务的运行状态，返回每个服务的健康状态"
    parameters = {"type": "object", "properties": {}, "required": []}

    def __init__(self, mcp_manager=None, health_service=None):
        self._mcp_manager = mcp_manager
        self._health_service = health_service

    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        statuses = {}

        # MCP Server 状态
        mcp_health = {}
        if self._mcp_manager:
            try:
                mcp_health = await self._mcp_manager.health_check_all()
            except Exception as e:
                logger.warning(f"[GetServiceStatusTool] MCP 健康检查失败: {e}")

        for svc_name, meta in _SERVICE_REGISTRY.items():
            # MCP Server 状态
            if svc_name in mcp_health:
                is_healthy = mcp_health[svc_name]
                statuses[svc_name] = {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "display_name": meta["display_name"],
                }
            elif self._mcp_manager and svc_name in self._mcp_manager._clients:
                statuses[svc_name] = {
                    "status": "unknown",
                    "display_name": meta["display_name"],
                }
            else:
                statuses[svc_name] = {
                    "status": "not_configured",
                    "display_name": meta["display_name"],
                }

        return ToolResult(success=True, data={"statuses": statuses})


class UpdateApiKeyTool(Tool):
    """更新指定服务的 API Key"""

    name = "update_api_key"
    description = "更新指定服务的 API Key，验证后替换旧 Key"
    parameters = {
        "type": "object",
        "properties": {
            "service_name": {"type": "string", "description": "服务名称"},
            "api_key": {"type": "string", "description": "新的 API Key"},
        },
        "required": ["service_name", "api_key"],
    }

    def __init__(self, settings_service=None, mcp_manager=None):
        self._settings_service = settings_service
        self._mcp_manager = mcp_manager

    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        service_name = kwargs.get("service_name", "").lower().strip()
        api_key = kwargs.get("api_key", "").strip()

        if not service_name:
            return ToolResult(success=False, error="service_name 不能为空")
        if not api_key:
            return ToolResult(success=False, error="api_key 不能为空")

        if service_name not in _SERVICE_REGISTRY:
            available = ", ".join(_SERVICE_REGISTRY.keys())
            return ToolResult(success=False, error=f"未知服务: {service_name}。可用服务: {available}")

        meta = _SERVICE_REGISTRY[service_name]

        # 使用 SettingsService 轮换 API Key（如果有 DB 上下文）
        if self._settings_service and ctx.db and ctx.user_id:
            try:
                result = await self._settings_service.rotate_api_key(
                    user_id=ctx.user_id,
                    service_name=service_name,
                    new_key=api_key,
                    db=ctx.db,
                )
                if not result["success"]:
                    return ToolResult(success=False, error=result["message"])
            except Exception as e:
                logger.warning(f"[UpdateApiKeyTool] rotate_api_key 失败，降级为环境变量设置: {e}")

        # 同时设置环境变量（确保 MCP Server 启动时能读取）
        env_key = f"{service_name.upper()}_API_KEY"
        if service_name == "semantic_scholar":
            env_key = "S2_API_KEY"
        os.environ[env_key] = api_key

        # 如果 MCP Server 已运行，更新其环境变量（需要重启才能生效）
        if self._mcp_manager and service_name in self._mcp_manager._clients:
            try:
                await self._mcp_manager.remove_server(service_name)
                # 重新配置并启动
                server_configs = get_mcp_server_configs()
                for cfg in server_configs:
                    if cfg.name == service_name:
                        cfg.env = {**cfg.env, env_key: api_key}
                        cfg.enabled = True
                        await self._mcp_manager.add_server(cfg)
                        break
            except Exception as e:
                logger.error(f"[UpdateApiKeyTool] 重启 {service_name} 失败: {e}")
                return ToolResult(success=False, error=f"重启 {meta['display_name']} 失败: {str(e)[:200]}")

        return ToolResult(
            success=True,
            data={
                "service": service_name,
                "message": f"{meta['display_name']} API Key 已更新",
            },
        )
