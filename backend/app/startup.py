"""应用启动管理器

分 3 阶段初始化服务，优化启动性能：
  Phase 1（关键路径，同步）: 日志 + DB 连接 + 表创建
  Phase 2（后台并行，asyncio.gather）: RAG / LLM / Agent / 设置加载
  Phase 3（懒加载）: ToolRegistry / SkillRegistry / MCPManager 等非关键服务
"""
import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class StartupManager:
    """分阶段启动管理器，管理服务初始化顺序与耗时日志"""

    def __init__(self, app: "FastAPI"):
        self.app = app
        self._phase2_done = asyncio.Event()

    # ------------------------------------------------------------------
    # 公共入口
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """执行完整 3 阶段初始化"""
        total_start = time.monotonic()

        await self._phase1()
        await self._phase2()
        self._phase3_register()

        elapsed = time.monotonic() - total_start
        logger.info(f"[Startup] 全部阶段完成，总耗时 {elapsed:.2f}s")

    # ------------------------------------------------------------------
    # Phase 1: 关键路径（同步初始化）
    # ------------------------------------------------------------------

    async def _phase1(self) -> None:
        t = time.monotonic()
        logger.info("[Startup] Phase 1 开始：日志 + 数据库")

        from app.logging_config import setup_logging
        from app.config import settings
        from app.database import init_db

        setup_logging(debug=settings.DEBUG)

        if settings.JWT_SECRET_KEY == "your-secret-key-change-in-production":
            logger.warning("⚠️  JWT_SECRET_KEY 使用默认值！请在 .env 中设置安全的密钥")

        await init_db()
        logger.info(f"[Startup] Phase 1 完成，耗时 {time.monotonic() - t:.2f}s（DB 已就绪）")

    # ------------------------------------------------------------------
    # Phase 2: 后台并行初始化
    # ------------------------------------------------------------------

    async def _phase2(self) -> None:
        t = time.monotonic()
        logger.info("[Startup] Phase 2 开始：并行初始化核心服务")

        results = await asyncio.gather(
            self._init_rag_service(),
            self._init_llm_service(),
            self._init_agent_service(),
            self._init_user_settings(),
            self._init_context_compressor_wrapper(),
            return_exceptions=True,
        )

        # 记录任何初始化失败（非阻断性）
        service_names = ["RAG", "LLM", "Agent", "Settings", "ContextCompressor"]
        for name, result in zip(service_names, results):
            if isinstance(result, Exception):
                logger.warning(f"[Startup] Phase 2 {name} 初始化失败（非阻断）: {result}")

        # 注册事件总线到 app.state
        from app.services.event_bus import event_bus
        self.app.state.event_bus = event_bus

        self._phase2_done.set()
        logger.info(f"[Startup] Phase 2 完成，耗时 {time.monotonic() - t:.2f}s（核心服务就绪）")

    async def _init_rag_service(self):
        t = time.monotonic()
        from app.services.rag_service import rag_service
        # 启动 RAG 索引队列 Worker
        if hasattr(rag_service, 'start_worker'):
            await rag_service.start_worker()
        self.app.state.rag_service = rag_service
        logger.info(f"[Startup]   RAG Service 就绪，耗时 {time.monotonic() - t:.2f}s")

    async def _init_llm_service(self):
        t = time.monotonic()
        from app.services.llm.llm_service import llm_service
        self.app.state.llm_service = llm_service
        logger.info(f"[Startup]   LLM Service 就绪，耗时 {time.monotonic() - t:.2f}s")

    async def _init_agent_service(self):
        t = time.monotonic()
        from app.services.agent import agent_service
        self.app.state.agent_service = agent_service
        logger.info(f"[Startup]   Agent Service 就绪，耗时 {time.monotonic() - t:.2f}s")

    async def _init_user_settings(self):
        t = time.monotonic()
        try:
            from app.config import settings
            from app.database import AsyncSessionLocal
            from app.services.settings_service import settings_service
            async with AsyncSessionLocal() as db:
                settings_values = await settings_service.get_setting_values(
                    user_id=settings.DEFAULT_USER_ID, db=db
                )
                await settings_service.apply_settings(settings_values)
            logger.info(f"[Startup]   用户配置加载完成，耗时 {time.monotonic() - t:.2f}s")
        except Exception as e:
            logger.warning(f"[Startup]   用户配置加载失败（非阻断）: {e}")

    async def _init_context_compressor_wrapper(self):
        """等待 LLM 服务绑定后初始化 ContextCompressor（最多等 5s）"""
        t = time.monotonic()
        deadline = time.monotonic() + 5.0
        while not hasattr(self.app.state, 'llm_service'):
            if time.monotonic() > deadline:
                logger.warning("[Startup]   ContextCompressor 初始化跳过（LLM 未就绪）")
                return
            await asyncio.sleep(0.1)
        from app.services.context_compressor import init_compressor
        init_compressor(self.app.state.llm_service)
        logger.info(f"[Startup]   ContextCompressor 就绪，耗时 {time.monotonic() - t:.2f}s")

    # ------------------------------------------------------------------
    # Phase 3: 懒加载（注册工厂，首次 Depends 时实例化）
    # ------------------------------------------------------------------

    def _phase3_register(self) -> None:
        """向 app.state 注册懒加载占位，在 dependencies.py 中按需实例化"""
        t = time.monotonic()
        logger.info("[Startup] Phase 3 开始：注册懒加载服务")

        from app.tools import ToolRegistry, ToolExecutor
        from app.mcp_services import MCPManager
        from app.skills import SkillRegistry, LiteratureReviewSkill, PaperAnalysisSkill

        self.app.state.tool_registry = ToolRegistry()
        self.app.state.tool_executor = ToolExecutor(self.app.state.tool_registry)
        self.app.state.mcp_manager = MCPManager()
        self.app.state.skill_registry = SkillRegistry()
        self.app.state.skill_registry.register(LiteratureReviewSkill())
        self.app.state.skill_registry.register(PaperAnalysisSkill())

        logger.info(f"[Startup] Phase 3 完成，耗时 {time.monotonic() - t:.2f}s（ToolRegistry/MCPManager/SkillRegistry 就绪）")

    # ------------------------------------------------------------------
    # 事件订阅（在所有服务就绪后调用）
    # ------------------------------------------------------------------

    def register_event_subscribers(self) -> None:
        """注册所有事件订阅者（应在 Phase 2 完成后调用）"""
        from app.services.event_bus import event_bus, Event, EventTypes

        # 通用日志记录
        async def log_event_handler(event: Event):
            logger.info(f"Event: {event.type}", extra={"event_data": event.data})

        event_bus.subscribe(EventTypes.PAPER_UPLOADED, log_event_handler)
        event_bus.subscribe(EventTypes.PAPER_DELETED, log_event_handler)
        event_bus.subscribe(EventTypes.ANALYSIS_COMPLETED, log_event_handler)
        event_bus.subscribe(EventTypes.INDEX_REBUILD_STARTED, log_event_handler)
        event_bus.subscribe(EventTypes.INDEX_REBUILD_COMPLETED, log_event_handler)

        # SESSION_UPDATED -> 后台预压缩
        from app.services.core.event_bus import (
            event_bus as core_event_bus,
            EventTypes as CoreEventTypes,
        )
        from app.services.context_compressor import context_compressor
        from app.services.chat.message_service import load_chat_history as _load_history

        async def _on_session_updated(event: Event):
            session_id = event.data.get("session_id")
            if not session_id:
                return
            try:
                from app.database import AsyncSessionLocal
                from langchain_core.messages import SystemMessage

                async with AsyncSessionLocal() as db:
                    history = await _load_history(db, session_id, limit=30)
                    if history and history.messages:
                        msgs = [SystemMessage(content="[placeholder]")] + list(history.messages)
                        asyncio.create_task(
                            context_compressor.background_precompress(str(session_id), msgs)
                        )
            except Exception as e:
                logger.warning(f"L3 预压缩触发失败（非阻塞）: {e}")

        core_event_bus.subscribe(CoreEventTypes.SESSION_UPDATED, _on_session_updated)

        # PAPER_UPLOADED -> 知识图谱更新
        from app.services.knowledge.graph_service import GraphService as _GraphService

        _graph_service = _GraphService()

        async def _on_paper_uploaded_update_graph(event: Event):
            paper_id = event.data.get("paper_id")
            user_id = event.data.get("user_id")
            if not paper_id or not user_id:
                return
            try:
                from app.database import AsyncSessionLocal

                async with AsyncSessionLocal() as db:
                    result = await _graph_service.update_graph(paper_id, user_id, db)
                    logger.info(
                        "知识图谱自动更新完成", extra={"paper_id": paper_id, **result}
                    )
            except Exception as e:
                logger.warning(f"知识图谱自动更新失败（非阻断）: {e}")

        event_bus.subscribe(EventTypes.PAPER_UPLOADED, _on_paper_uploaded_update_graph)

        # CONFIG_UPDATED -> WebSocket 广播
        async def _on_config_updated(event: Event):
            """配置变更时，通过事件总线转发到 WebSocket

            由于 event_bus 没有直接访问 ws 的能力，
            将配置变更事件存入 app.state 供前端轮询或 ws 独立推送。
            此处仅做日志记录，实际 ws 推送在 unified_handler 中通过 ctx 传递。
            """
            svc = event.data.get("service", "unknown")
            logger.info(f"[EventBus] 配置变更事件: {svc}")

        event_bus.subscribe(EventTypes.CONFIG_UPDATED, _on_config_updated)

        logger.info("[Startup] 所有事件订阅者已注册")
