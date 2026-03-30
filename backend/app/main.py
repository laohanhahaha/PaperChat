"""FastAPI 应用入口

创建 FastAPI 应用实例，配置中间件、路由和生命周期事件
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, close_db
from app.middleware import setup_error_handlers
from app.routers import papers_router, highlights_router, notes_router, ws_router, reading_router, analysis_router, chat_router, knowledge_router, writing_router, recommendations_router, settings_router


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
    # 启动
    print(f"Starting {settings.APP_NAME}...")
    await init_db()
    print("Database initialized")
    
    # 加载默认用户配置并应用
    try:
        from app.database import AsyncSessionLocal
        from app.services.settings_service import settings_service
        
        async with AsyncSessionLocal() as db:
            # 加载默认用户(id=1)的配置
            settings_values = await settings_service.get_setting_values(user_id=1, db=db)
            await settings_service.apply_settings(settings_values)
            print("User settings loaded and applied")
    except Exception as e:
        print(f"Warning: Failed to load user settings: {e}")
    
    yield
    
    # 关闭
    print("Shutting down...")
    await close_db()
    print("Database connection closed")


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
    
    # 配置 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 设置全局异常处理
    setup_error_handlers(app)
    
    # 注册路由
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
    
    return app


# 创建应用实例
app = create_app()


@app.get("/api/health")
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
