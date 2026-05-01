"""配置服务 API 路由

提供 MCP 服务状态查询、一键配置、手动配置等 REST API 端点。
ConfigAgent 的对话交互走 WebSocket（unified_handler），此处仅提供管理类 API。
"""
import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.database import get_db
from app.services.auth_service import get_current_user
from app.models.user import User
from app.services.settings_service import settings_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/config", tags=["config"])


class ConfigureServiceRequest(BaseModel):
    """配置服务请求体"""
    service_name: str
    api_key: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class AutoSetupResponse(BaseModel):
    """一键配置响应体"""
    configured: list[str]
    failed: list[str]


def _get_mcp_manager(request: Request):
    """从 app.state 获取 MCPManager"""
    return request.app.state.mcp_manager



@router.get("/services/status")
async def get_service_status(request: Request):
    """获取所有服务的配置状态

    返回每个服务的 healthy/unhealthy/not_configured 状态。
    性能影响：并发健康检查，总延迟 = 最慢的服务（通常 <2s）。
    """
    from app.tools.config_tools import GetServiceStatusTool

    mcp_manager = _get_mcp_manager(request)
    health_service = getattr(request.app.state, "health_service", None)

    tool = GetServiceStatusTool(
        mcp_manager=mcp_manager,
        health_service=health_service,
    )

    from app.tools.base import ToolContext
    ctx = ToolContext()
    result = await tool.execute(ctx)

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return result.data


@router.post("/services/configure")
async def configure_service(
    req: ConfigureServiceRequest,
    request: Request,
):
    """配置指定的外部服务

    设置 API Key、环境变量，并启动 MCP Server 连接。
    性能影响：启动 MCP Server 子进程约 1-3s。
    """
    from app.tools.config_tools import ConfigureServiceTool

    mcp_manager = _get_mcp_manager(request)

    tool = ConfigureServiceTool(
        mcp_manager=mcp_manager,
    )

    from app.tools.base import ToolContext
    ctx = ToolContext()
    result = await tool.execute(
        ctx,
        service_name=req.service_name,
        api_key=req.api_key or "",
        settings=req.settings or {},
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return result.data


@router.post("/services/auto-setup")
async def auto_setup_free_services(request: Request):
    """一键配置所有免费服务（Academic MCP / Open WebSearch）

    自动配置无需 API Key 的 MCP Server。
    性能影响：并发启动 2 个 MCP Server 子进程，约 2-4s。
    """
    from app.tools.config_tools import ConfigureServiceTool

    mcp_manager = _get_mcp_manager(request)

    tool = ConfigureServiceTool(
        mcp_manager=mcp_manager,
    )

    free_services = ["academic_mcp", "open_websearch"]
    configured = []
    failed = []

    from app.tools.base import ToolContext
    ctx = ToolContext()

    for svc_name in free_services:
        try:
            result = await tool.execute(ctx, service_name=svc_name)
            if result.success:
                configured.append(svc_name)
            else:
                failed.append(svc_name)
                logger.warning(f"一键配置 {svc_name} 失败: {result.error}")
        except Exception as e:
            failed.append(svc_name)
            logger.error(f"一键配置 {svc_name} 异常: {e}")

    return AutoSetupResponse(configured=configured, failed=failed)


@router.post("/services/validate")
async def validate_service(
    req: ConfigureServiceRequest,
    request: Request,
):
    """验证指定服务的连通性

    检查 MCP Server 健康状态或搜索适配器 API Key 有效性。
    性能影响：健康检查约 200ms-2s。
    """
    from app.tools.config_tools import ValidateServiceTool

    mcp_manager = _get_mcp_manager(request)
    health_service = getattr(request.app.state, "health_service", None)

    tool = ValidateServiceTool(
        mcp_manager=mcp_manager,
        health_service=health_service,
        settings_service=settings_service,
    )

    from app.tools.base import ToolContext
    ctx = ToolContext()
    result = await tool.execute(ctx, service_name=req.service_name)

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return result.data
