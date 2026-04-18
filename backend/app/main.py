"""FastAPI 应用入口

创建 FastAPI 应用实例，配置中间件、路由和生命周期事件
"""
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
from app.routers import papers_router, highlights_router, notes_router, ws_router, reading_router, analysis_router, chat_router, knowledge_router, writing_router, recommendations_router, settings_router
from app.routers.feedback import router as feedback_router
from app.routers.backup import router as backup_router
from app.routers.feature_flags import router as feature_flags_router



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    启动时:
        - 初始化数据库连接
        - 创建数据库表
        - 加载默认用户配置并应用
    
    关闭时:
        - 关闭数据库连接
    """
    # 启动：初始化日志系统
    setup_logging(debug=settings.DEBUG)
    logger.info(f"Starting {settings.APP_NAME}...")

    # JWT 密钥安全检查
    if settings.JWT_SECRET_KEY == "your-secret-key-change-in-production":
        logger.warning("⚠️ JWT_SECRET_KEY 使用默认值！请在 .env 中设置安全的密钥")

    await init_db()
    logger.info("Database initialized")
    
    # 加载默认用户配置并应用
    try:
        from app.database import AsyncSessionLocal
        from app.services.settings_service import settings_service
        
        async with AsyncSessionLocal() as db:
            # 加载默认用户的配置
            settings_values = await settings_service.get_setting_values(user_id=settings.DEFAULT_USER_ID, db=db)
            await settings_service.apply_settings(settings_values)
            logger.info("User settings loaded and applied")
    except Exception as e:
        logger.warning(f"Failed to load user settings: {e}")
    
    # 初始化服务到 app.state（依赖注入）
    from app.services.rag_service import rag_service
    from app.services.llm.llm_service import llm_service
    from app.services.agent_service import agent_service
    from app.services.event_bus import event_bus, Event, EventTypes

    app.state.rag_service = rag_service
    app.state.llm_service = llm_service
    app.state.agent_service = agent_service
    app.state.event_bus = event_bus
    logger.info("Services registered to app.state (DI)")

    # 注册事件订阅者（日志记录）
    async def log_event_handler(event: Event):
        logger.info(f"Event: {event.type}", extra={"event_data": event.data})

    event_bus.subscribe(EventTypes.PAPER_UPLOADED, log_event_handler)
    event_bus.subscribe(EventTypes.PAPER_DELETED, log_event_handler)
    event_bus.subscribe(EventTypes.ANALYSIS_COMPLETED, log_event_handler)
    event_bus.subscribe(EventTypes.INDEX_REBUILD_STARTED, log_event_handler)
    event_bus.subscribe(EventTypes.INDEX_REBUILD_COMPLETED, log_event_handler)
    logger.info("Event bus subscribers registered")
    
    yield

    # 优雅关停
    logger.info("正在关闭服务...")

    # 关闭 RAG 线程池
    try:
        from app.services.rag_service import rag_service
        if hasattr(rag_service, '_executor'):
            rag_service._executor.shutdown(wait=True, cancel_futures=True)
            logger.info("RAG 线程池已关闭")
    except Exception as e:
        logger.error(f"关闭 RAG 线程池失败: {e}")

    # 清空缓存
    try:
        from app.services.message_service import invalidate_full_text_cache
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
    
    # 旧路径向后兼容重定向：/api/xxx → /api/v1/xxx
    _LEGACY_PREFIXES = [
        "papers", "chat", "analysis", "writing", "highlights", "notes",
        "reading", "recommendations", "settings", "feedback", "knowledge", "auth",
        "backup", "features"
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


@app.get("/api/v1/health")
async def health_check():
    """
    健康检查端点
    
    返回:
        - 应用状态信息
    """
    return {
        "status": "ok",
        "message": f"{settings.APP_NAME} API v3.1 (WebSocket + LangChain + SQLAlchemy)"
    }


@app.get("/api/health")
async def health_check_legacy():
    """旧版健康检查端点（向后兼容，重定向到 /api/v1/health）"""
    return {
        "status": "ok",
        "message": f"{settings.APP_NAME} API v3.1 (WebSocket + LangChain + SQLAlchemy)",
        "hint": "This endpoint is deprecated, use /api/v1/health instead"
    }
