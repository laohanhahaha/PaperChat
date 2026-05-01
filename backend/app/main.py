"""FastAPI 应用入口

创建 FastAPI 应用实例，配置中间件、路由和生命周期事件
"""
import sys
import asyncio

# Windows 下强制 ProactorEventLoop（支持 asyncio.create_subprocess_exec）
# 必须在任何 asyncio 事件循环创建前设置
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

import logging

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import init_db, close_db
from app.logging_config import setup_logging
from app.middleware import setup_error_handlers
from app.rate_limiter import limiter

logger = logging.getLogger(__name__)
from app.routers.feedback import router as feedback_router
from app.routers.backup import router as backup_router
from app.routers.feature_flags import router as feature_flags_router
from app.routers import papers_router, highlights_router, notes_router, ws_router, reading_router, analysis_router, chat_router, knowledge_router, writing_router, recommendations_router, settings_router, batch_analysis_router, cost_router, health_router, citations_router, config_router, upload_router, precache_router, model_config_router, routing_router, export_router, folder_import_router, subagent_router



async def _load_mcp_config_from_db(app: FastAPI):
    """从数据库加载用户已配置的 MCP Server 列表并启动

    在 lifespan 中调用，确保 MCPManager 和 ToolRegistry 已初始化。
    如果没有已配置的服务（首次使用场景），跳过。

    性能影响：每个 MCP Server 启动约 1-3s，并发启动总耗时 ≈ 最慢的单个服务。
    """
    mcp_manager = getattr(app.state, "mcp_manager", None)
    tool_registry = getattr(app.state, "tool_registry", None)

    # 诊断日志：打印 app.state 中关键属性的类型
    state_attrs = [a for a in dir(app.state) if not a.startswith('_')]
    logger.info(f"[lifespan] _load_mcp_config_from_db 入口: state attrs={state_attrs}")
    logger.info(f"[lifespan] mcp_manager type={type(mcp_manager).__name__}, is None={mcp_manager is None}")
    logger.info(f"[lifespan] tool_registry type={type(tool_registry).__name__}, is None={tool_registry is None}, len={len(tool_registry) if tool_registry is not None else 'N/A'}")

    if mcp_manager is None:
        logger.warning("[lifespan] MCPManager 未就绪（None），跳过 MCP 配置加载")
        return
    if tool_registry is None:
        logger.warning("[lifespan] ToolRegistry 未就绪（None），跳过 MCP 配置加载")
        return

    logger.info("[lifespan] 开始加载 MCP 配置...")

    try:
        from app.database import AsyncSessionLocal
        from app.services.settings_service import settings_service
        from app.config import settings as app_settings
        from app.mcp_services.academic_config import get_mcp_server_configs
        from app.mcp_services.bridge import MCPToolBridge

        # 获取用户存储的 mcp 配置值
        async with AsyncSessionLocal() as db:
            settings_values = await settings_service.get_setting_values(
                user_id=app_settings.DEFAULT_USER_ID, db=db
            )

        mcp_values = settings_values.get("mcp", {})
        logger.info(f"[lifespan] DB 中 MCP 配置: {bool(mcp_values)}, keys={list(mcp_values.keys())}")

        if not mcp_values:
            # 首次使用：自动启用免费 MCP 服务并持久化
            free_services = ["academic_mcp", "open_websearch"]
            logger.info(f"[lifespan] 自动启用免费 MCP 服务: {', '.join(free_services)}")

            import json
            mcp_config = {"enabled_services": free_services}
            async with AsyncSessionLocal() as db_write:
                await settings_service.update_setting_values(
                    user_id=app_settings.DEFAULT_USER_ID,
                    db=db_write,
                    values={"mcp": {"status": json.dumps(mcp_config)}},
                )
            mcp_values = {"status": json.dumps(mcp_config)}

        # 解析已启用服务列表（mcp.status 字段存储 JSON 格式配置）
        import json
        enabled_services = []
        status_str = mcp_values.get("status", "")
        if status_str:
            try:
                mcp_config = json.loads(status_str) if isinstance(status_str, str) else status_str
                enabled_services = mcp_config.get("enabled_services", [])
                logger.info(f"[lifespan] 已启用 MCP 服务: {enabled_services}")
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"[lifespan] MCP 配置解析失败: {status_str[:100]}")
                return

        if not enabled_services:
            logger.info("[lifespan] 没有已启用的 MCP 服务，跳过")
            return

        # 从 academic_config 中匹配已启用服务并启动
        all_configs = get_mcp_server_configs()
        known_names = {cfg.name for cfg in all_configs}
        # 过滤掉数据库中残留的已废弃服务名称
        stale = [s for s in enabled_services if s not in known_names]
        if stale:
            logger.warning("[lifespan] DB 中包含已废弃的 MCP 服务名称 %s，将被忽略", stale)

        # 如果所有已启用的服务名称都已废弃，自动重置为默认免费服务
        valid_services = [s for s in enabled_services if s in known_names]
        if not valid_services and stale:
            logger.warning("[lifespan] 所有已启用服务均已废弃，自动重置为默认免费服务")
            valid_services = ["academic_mcp", "open_websearch"]
            # 持久化修正后的配置
            try:
                import json as _json
                corrected_config = {"enabled_services": valid_services}
                async with AsyncSessionLocal() as db_fix:
                    await settings_service.update_setting_values(
                        user_id=app_settings.DEFAULT_USER_ID,
                        db=db_fix,
                        values={"mcp": {"status": _json.dumps(corrected_config)}},
                    )
                logger.info("[lifespan] 已将 MCP 配置重置为: %s", valid_services)
            except Exception as e:
                logger.warning("[lifespan] 持久化修正配置失败: %s", e)

        started = []
        for cfg in all_configs:
            if cfg.name in valid_services:
                cfg.enabled = True
                logger.info(
                    "[lifespan] 正在启动 MCP Server: %s (cmd=%s, args=%s)",
                    cfg.name, cfg.command, cfg.args,
                )
                # 注入环境变量（如 API Key）
                import os
                for env_key in cfg.env:
                    if env_key in os.environ and os.environ[env_key]:
                        cfg.env[env_key] = os.environ[env_key]
                try:
                    success = await mcp_manager.add_server(cfg)
                    if success:
                        started.append(cfg.name)
                        logger.info(f"[lifespan] MCP Server {cfg.name} 启动成功")
                    else:
                        logger.warning(f"[lifespan] MCP Server {cfg.name} 启动失败")
                except Exception as e:
                    logger.error(f"[lifespan] 启动 MCP Server {cfg.name} 异常: {e}")

        logger.info(f"[lifespan] MCP 启动结果: {started} (成功 {len(started)}/{len(valid_services)} 个)")

        # 对失败的服务重试一次（延迟 2s 后，给子进程更多启动时间）
        failed_services = [s for s in valid_services if s not in started]
        if failed_services:
            logger.info(f"[lifespan] 尝试重连失败的 MCP 服务: {failed_services}")
            await asyncio.sleep(2)
            for cfg in all_configs:
                if cfg.name in failed_services:
                    try:
                        success = await mcp_manager.add_server(cfg)
                        if success:
                            started.append(cfg.name)
                            logger.info(f"[lifespan] MCP Server {cfg.name} 重连成功")
                    except Exception as e:
                        logger.error(f"[lifespan] MCP Server {cfg.name} 重连失败: {e}")
            if len(started) > len(started) - len(failed_services):
                logger.info(f"[lifespan] 重连后结果: {started}")

        # 桥接 MCP 工具到 ToolRegistry
        if started and tool_registry is not None:
            try:
                bridge = MCPToolBridge(mcp_manager)
                mcp_tools = await bridge.bridge_all()
                tool_registry.register_many(mcp_tools)
                logger.info(f"[lifespan] MCP 配置加载完成：已启动 {started}，桥接 {len(mcp_tools)} 个工具")
            except Exception as e:
                logger.error(f"[lifespan] MCP 工具桥接失败: {e}")
        elif not started:
            logger.warning("[lifespan] 没有成功启动任何 MCP Server，跳过工具桥接")

    except Exception as e:
        logger.error(f"[lifespan] 加载 MCP 配置失败（非阻断）: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时（通过 StartupManager 分 3 阶段）:
        Phase 1: 日志 + DB 连接 + 表创建
        Phase 2: 并行初始化 RAG / LLM / Agent / 设置
        Phase 3: 懒加载 ToolRegistry / MCPManager / SkillRegistry

    关闭时:
        - 关闭数据库连接
    """
    from app.startup import StartupManager
    from app.dependencies import service_container
    from app.config import config_service

    manager = StartupManager(app)
    await manager.run()

    # 将 ConfigService 挂载到 app.state（供 get_config_service 依赖使用）
    app.state.config_service = config_service
    service_container.register_instance("config_service", config_service)

    # --- 初始化预置子智能体 ---
    from app.routers.subagent import init_preset_subagents
    from app.database import AsyncSessionLocal as _SubAgentSessionLocal
    async with _SubAgentSessionLocal() as _sa_db:
        await init_preset_subagents(_sa_db)
    logger.info("[lifespan] 预置子智能体初始化完成")

    # --- 启动时加载用户 MCP 配置并桥接工具 ---
    await _load_mcp_config_from_db(app)

    # 初始化 HealthService 并绑定 app.state
    from app.services.health import HealthService
    health_svc = HealthService()
    health_svc.bind_app_state(app.state)
    app.state.health_service = health_svc
    service_container.register_instance("health_service", health_svc)

    # 启动后台健康检查（首次立即检查 + 60s 间隔）
    await health_svc.start_background_check()

    # 初始化 EncryptionService 和 KeyRotationService
    from app.services.security.encryption import (
        EncryptionService, set_encryption_service,
    )
    from app.services.security.key_rotation import (
        KeyRotationService, set_key_rotation_service,
    )
    encryption_svc = EncryptionService()
    set_encryption_service(encryption_svc)
    app.state.encryption_service = encryption_svc
    service_container.register_instance("encryption_service", encryption_svc)
    logger.info("[lifespan] EncryptionService 已初始化")

    key_rotation_svc = KeyRotationService()
    set_key_rotation_service(key_rotation_svc)
    app.state.key_rotation_service = key_rotation_svc
    service_container.register_instance("key_rotation_service", key_rotation_svc)

    # 注册已配置的 Key 到轮换服务
    try:
        from app.services.settings_service import settings_service
        from app.database import AsyncSessionLocal
        from app.config import settings as app_settings
        async with AsyncSessionLocal() as db:
            vals = await settings_service.get_setting_values(
                user_id=app_settings.DEFAULT_USER_ID, db=db,
            )
        # 检测所有含 api_key 的分类并注册
        for cat, cfg in vals.items():
            if isinstance(cfg, dict) and cfg.get("api_key"):
                key_rotation_svc.register_key(cat)
    except Exception as e:
        logger.warning(f"[lifespan] 注册 Key 轮换元数据失败（非阻断）: {e}")

    # 启动 Key 轮换后台检查
    await key_rotation_svc.start()
    logger.info("[lifespan] KeyRotationService 已启动")

    # 启动预缓存后台任务
    from app.services.precache_service import precache_service
    await precache_service.start()

    # 将核心服务同步注册到 ServiceContainer（便于后续按名解析）
    for _name in (
        "rag_service", "llm_service", "agent_service", "event_bus",
        "tool_registry", "tool_executor", "mcp_manager", "skill_registry",
    ):
        _instance = getattr(app.state, _name, None)
        if _instance is not None:
            service_container.register_instance(_name, _instance)

    # 注册事件订阅者（所有服务就绪后）
    manager.register_event_subscribers()

    logger.info(f"Starting {settings.APP_NAME}...")

    yield

    # 优雅关停
    logger.info("正在关闭服务...")

    # 停止后台健康检查
    try:
        health_svc = getattr(app.state, "health_service", None)
        if health_svc:
            await health_svc.stop_background_check()
            logger.info("后台健康检查已停止")
    except Exception as e:
        logger.error(f"停止后台健康检查失败: {e}")

    # 停止 KeyRotationService
    try:
        key_rotation_svc = getattr(app.state, "key_rotation_service", None)
        if key_rotation_svc:
            await key_rotation_svc.stop()
            logger.info("KeyRotationService 已停止")
    except Exception as e:
        logger.error(f"停止 KeyRotationService 失败: {e}")

    # 停止预缓存后台任务
    try:
        from app.services.precache_service import precache_service
        await precache_service.stop()
        logger.info("预缓存服务已停止")
    except Exception as e:
        logger.error(f"停止预缓存服务失败: {e}")

    # 关闭 RAG 线程池 + Worker
    try:
        from app.services.rag_service import rag_service
        if hasattr(rag_service, '_executor'):
            rag_service._executor.shutdown(wait=True, cancel_futures=True)
            logger.info("RAG 线程池已关闭")
        if hasattr(rag_service, '_worker_task') and rag_service._worker_task:
            rag_service._worker_task.cancel()
    except Exception as e:
        logger.error(f"关闭 RAG 线程池失败: {e}")

    # 清空缓存
    try:
        from app.services.chat.message_service import invalidate_full_text_cache
        invalidate_full_text_cache()
        logger.info("全文缓存已清空")
    except Exception as e:
        logger.error(f"清空缓存失败: {e}")

    # 关闭数据库
    await close_db()
    logger.info("Database connection closed")
    logger.info("服务已关闭")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """添加安全响应头的中间件"""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def create_app() -> FastAPI:
    """
    创建并配置 FastAPI 应用实例

    Returns:
        配置好的 FastAPI 应用实例
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version="3.1.0",
        description="PaperChat API - 学术论文智能阅读与问答系统",
        lifespan=lifespan,
        debug=settings.DEBUG
    )

    # 安全响应头中间件
    app.add_middleware(SecurityHeadersMiddleware)

    # 配置 CORS（精确配置）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    )

    # 设置全局异常处理
    setup_error_handlers(app)

    # 配置请求限流
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # 注册路由（全部已迁移到 /api/v1 前缀）
    app.include_router(papers_router)
    app.include_router(highlights_router)
    app.include_router(notes_router)
    app.include_router(ws_router)
    app.include_router(reading_router)
    app.include_router(analysis_router)
    app.include_router(chat_router)
    app.include_router(knowledge_router)
    app.include_router(recommendations_router)
    app.include_router(writing_router)
    app.include_router(settings_router)
    app.include_router(feedback_router)
    app.include_router(backup_router)
    app.include_router(feature_flags_router)
    app.include_router(batch_analysis_router)
    app.include_router(cost_router)
    app.include_router(health_router)
    app.include_router(citations_router)
    app.include_router(config_router)
    app.include_router(upload_router)
    app.include_router(precache_router)
    app.include_router(model_config_router)
    app.include_router(routing_router)
    app.include_router(export_router)
    app.include_router(folder_import_router)
    app.include_router(subagent_router)

    # 旧路径向后兼容重定向：/api/xxx → /api/v1/xxx
    _LEGACY_PREFIXES = [
        "papers", "chat", "analysis", "writing", "highlights", "notes",
        "reading", "recommendations", "settings", "feedback", "knowledge", "auth",
        "backup", "features", "health", "citations", "config"
    ]

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def legacy_redirect(request: Request, path: str):
        """将旧版 /api/xxx 请求重定向到 /api/v1/xxx"""
        for prefix in _LEGACY_PREFIXES:
            if path == prefix or path.startswith(prefix + "/"):
                new_url = str(request.url.replace_path(f"/api/v1/{path}"))
                return RedirectResponse(url=new_url, status_code=308)
        # 不匹配任何已知前缀的路径，返回 404
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    return app


# 创建应用实例
app = create_app()


@app.get("/api/health")
async def health_check_legacy():
    """旧版健康检查端点（向后兼容）"""
    return {
        "status": "ok",
        "message": f"{settings.APP_NAME} API v3.1 (WebSocket + LangChain + SQLAlchemy)",
        "hint": "This endpoint is deprecated, use /api/v1/health instead"
    }
