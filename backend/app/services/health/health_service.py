"""通用服务健康监控

并行检查所有核心服务（数据库、LLM、搜索、ChromaDB、MCP）的健康状态，
结果缓存 + 后台定期刷新，前端轮询时不触发实际检查。

性能影响：
  - check_all 使用 asyncio.gather 并行，总延迟 = 最慢的服务
  - 后台检查间隔 60s，CPU 开销可忽略
  - 每个检查都有 5s 超时保护，避免阻塞
  - get_cached_status 为纯内存读取，O(1)
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

import httpx
from sqlalchemy import text

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealth:
    """单个服务的健康检查结果"""
    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    latency_ms: Optional[float] = None
    message: str = ""
    last_checked: Optional[float] = None
    details: Optional[Dict[str, Any]] = field(default_factory=dict)


class HealthService:
    """通用服务健康监控

    用法:
        svc = HealthService()
        await svc.check_all()           # 并行检查所有服务
        svc.get_cached_status()         # 读取最近一次结果（不发起新检查）
        await svc.start_background_check()  # 启动后台定期检查
        await svc.stop_background_check()   # 停止后台检查
    """

    def __init__(self, check_interval: int = 60) -> None:
        self._results: Dict[str, ServiceHealth] = {}
        self._check_interval = check_interval
        self._background_task: Optional[asyncio.Task] = None
        self._app_state: Any = None  # 运行时注入 FastAPI app.state

    def bind_app_state(self, app_state: Any) -> None:
        """绑定 FastAPI app.state，用于获取服务实例"""
        self._app_state = app_state

    # ------------------------------------------------------------------
    # 核心检查
    # ------------------------------------------------------------------

    async def check_all(self) -> Dict[str, ServiceHealth]:
        """并行检查所有服务健康状态

        使用 asyncio.gather 并行执行，总延迟 = 最慢的服务。
        每个检查都有超时保护（5s），结果写入 _results 缓存。
        """
        checks = {
            "database": self._check_database,
            "llm_api": self._check_llm_api,
            "search_service": self._check_search,
            "chromadb": self._check_chromadb,
            "mcp_servers": self._check_mcp_servers,
        }

        names = list(checks.keys())
        coros = [self._safe_check(name, fn) for name, fn in checks.items()]

        await asyncio.gather(*coros, return_exceptions=False)
        return dict(self._results)

    async def _safe_check(self, name: str, fn: Any) -> None:
        """执行单个检查，捕获异常，确保不会影响其他检查"""
        try:
            result = await asyncio.wait_for(fn(), timeout=5.0)
            self._results[name] = result
        except asyncio.TimeoutError:
            self._results[name] = ServiceHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=5000,
                message="检查超时（5s）",
                last_checked=time.time(),
            )
        except Exception as exc:
            self._results[name] = ServiceHealth(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"检查异常: {str(exc)[:100]}",
                last_checked=time.time(),
            )

    # ------------------------------------------------------------------
    # 各服务检查实现
    # ------------------------------------------------------------------

    async def _check_database(self) -> ServiceHealth:
        """检查数据库连接"""
        start = time.monotonic()
        try:
            from app.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
            latency = (time.monotonic() - start) * 1000
            return ServiceHealth(
                name="database",
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency, 1),
                message="数据库连接正常",
                last_checked=time.time(),
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return ServiceHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 1),
                message=f"数据库连接失败: {str(exc)[:80]}",
                last_checked=time.time(),
            )

    async def _check_llm_api(self) -> ServiceHealth:
        """检查 LLM API（DeepSeek）可用性"""
        start = time.monotonic()
        try:
            from app.config import settings
            api_key = settings.DEEPSEEK_API_KEY
            if not api_key:
                return ServiceHealth(
                    name="llm_api",
                    status=HealthStatus.DEGRADED,
                    message="未配置 DeepSeek API Key",
                    last_checked=time.time(),
                )

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.deepseek.com/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )

            latency = (time.monotonic() - start) * 1000

            if resp.status_code == 200:
                return ServiceHealth(
                    name="llm_api",
                    status=HealthStatus.HEALTHY,
                    latency_ms=round(latency, 1),
                    message="LLM API 可用",
                    last_checked=time.time(),
                )
            elif resp.status_code in (401, 403):
                return ServiceHealth(
                    name="llm_api",
                    status=HealthStatus.DEGRADED,
                    latency_ms=round(latency, 1),
                    message=f"LLM API 认证失败（HTTP {resp.status_code}）",
                    last_checked=time.time(),
                )
            else:
                return ServiceHealth(
                    name="llm_api",
                    status=HealthStatus.DEGRADED,
                    latency_ms=round(latency, 1),
                    message=f"LLM API 异常（HTTP {resp.status_code}）",
                    last_checked=time.time(),
                )
        except httpx.TimeoutException:
            latency = (time.monotonic() - start) * 1000
            return ServiceHealth(
                name="llm_api",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 1),
                message="LLM API 超时（5s）",
                last_checked=time.time(),
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return ServiceHealth(
                name="llm_api",
                status=HealthStatus.UNKNOWN,
                latency_ms=round(latency, 1),
                message=f"LLM API 检查异常: {str(exc)[:80]}",
                last_checked=time.time(),
            )

    async def _check_search(self) -> ServiceHealth:
        """检查搜索服务（DuckDuckGo）"""
        start = time.monotonic()
        try:
            from duckduckgo_search import DDGS
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: list(DDGS().text("health check", max_results=1)),
                ),
                timeout=5.0,
            )
            latency = (time.monotonic() - start) * 1000
            return ServiceHealth(
                name="search_service",
                status=HealthStatus.HEALTHY if result else HealthStatus.DEGRADED,
                latency_ms=round(latency, 1),
                message="搜索服务正常" if result else "搜索服务返回空结果",
                last_checked=time.time(),
            )
        except asyncio.TimeoutError:
            latency = (time.monotonic() - start) * 1000
            return ServiceHealth(
                name="search_service",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 1),
                message="搜索服务超时（5s）",
                last_checked=time.time(),
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return ServiceHealth(
                name="search_service",
                status=HealthStatus.DEGRADED,
                latency_ms=round(latency, 1),
                message=f"搜索服务异常: {str(exc)[:80]}",
                last_checked=time.time(),
            )

    async def _check_chromadb(self) -> ServiceHealth:
        """检查 ChromaDB 向量数据库"""
        start = time.monotonic()
        try:
            import chromadb
            client = chromadb.PersistentClient(
                path=str(
                    __import__("pathlib").Path(__file__).parent.parent.parent / "chroma_db"
                )
            )
            # heartbeat 检查
            heartbeat = client.heartbeat()
            latency = (time.monotonic() - start) * 1000

            if heartbeat:
                collections = client.list_collections()
                return ServiceHealth(
                    name="chromadb",
                    status=HealthStatus.HEALTHY,
                    latency_ms=round(latency, 1),
                    message=f"ChromaDB 正常（{len(collections)} 个集合）",
                    last_checked=time.time(),
                    details={"collections": len(collections)},
                )
            else:
                return ServiceHealth(
                    name="chromadb",
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=round(latency, 1),
                    message="ChromaDB heartbeat 失败",
                    last_checked=time.time(),
                )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return ServiceHealth(
                name="chromadb",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 1),
                message=f"ChromaDB 异常: {str(exc)[:80]}",
                last_checked=time.time(),
            )

    async def _check_mcp_servers(self) -> ServiceHealth:
        """检查所有 MCP Server（复用 MCPManager.health_check_all）"""
        start = time.monotonic()
        try:
            mcp_manager = getattr(self._app_state, "mcp_manager", None) if self._app_state else None
            if mcp_manager is None:
                return ServiceHealth(
                    name="mcp_servers",
                    status=HealthStatus.UNKNOWN,
                    message="MCPManager 未初始化",
                    last_checked=time.time(),
                )

            statuses = await mcp_manager.health_check_all()
            latency = (time.monotonic() - start) * 1000
            total = len(statuses)
            healthy = sum(1 for ok in statuses.values() if ok)

            if total == 0:
                status = HealthStatus.UNKNOWN
                message = "无 MCP Server 已配置"
            elif healthy == total:
                status = HealthStatus.HEALTHY
                message = f"所有 {total} 个 MCP Server 正常"
            elif healthy > 0:
                status = HealthStatus.DEGRADED
                message = f"{healthy}/{total} 个 MCP Server 正常"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"所有 {total} 个 MCP Server 不可用"

            return ServiceHealth(
                name="mcp_servers",
                status=status,
                latency_ms=round(latency, 1),
                message=message,
                last_checked=time.time(),
                details={"servers": statuses},
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return ServiceHealth(
                name="mcp_servers",
                status=HealthStatus.UNKNOWN,
                latency_ms=round(latency, 1),
                message=f"MCP 检查异常: {str(exc)[:80]}",
                last_checked=time.time(),
            )

    # ------------------------------------------------------------------
    # 后台定期检查
    # ------------------------------------------------------------------

    async def start_background_check(self) -> None:
        """启动后台定期检查任务"""
        if self._background_task and not self._background_task.done():
            logger.warning("[HealthService] 后台检查任务已在运行")
            return

        # 首次立即检查一次
        try:
            await self.check_all()
        except Exception as exc:
            logger.warning("[HealthService] 初始检查失败: %s", exc)

        self._background_task = asyncio.create_task(
            self._background_loop(),
            name="health-check-background",
        )
        logger.info(
            "[HealthService] 后台检查已启动，间隔 %ds", self._check_interval
        )

    async def stop_background_check(self) -> None:
        """停止后台检查任务"""
        if self._background_task and not self._background_task.done():
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None
            logger.info("[HealthService] 后台检查已停止")

    async def _background_loop(self) -> None:
        """后台检查循环"""
        while True:
            try:
                await asyncio.sleep(self._check_interval)
                await self.check_all()
                logger.debug("[HealthService] 后台检查完成")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("[HealthService] 后台检查异常: %s", exc)

    # ------------------------------------------------------------------
    # 缓存查询
    # ------------------------------------------------------------------

    def get_cached_status(self) -> Dict[str, ServiceHealth]:
        """获取最近一次检查结果（不发起新检查，O(1) 内存读取）"""
        return dict(self._results)


# 全局单例
health_service = HealthService()
