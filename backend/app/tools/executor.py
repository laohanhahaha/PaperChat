"""工具执行器 — 统一的工具调用入口，提供超时控制与指标记录

ToolExecutor 封装单次/批量工具调用，保证：
- asyncio.wait_for 超时控制（默认 30s）
- perf_counter 耗时计量
- 异常捕获并包装为 ToolResult(success=False)
- 结构化日志（工具名、耗时、成功/失败）

性能说明：
- 超时控制通过 asyncio.wait_for 实现，无额外线程开销
- 指标记录仅使用 logging，无第三方依赖
- execute_many 采用串行执行，避免共享 AsyncSession 的并发问题
"""
import asyncio
import logging
from time import perf_counter
from typing import List, Tuple

from app.tools.base import Tool, ToolContext, ToolResult
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutor:
    """工具执行器，提供超时控制、异常保护和指标记录"""

    def __init__(self, registry: ToolRegistry, timeout: float = 30.0) -> None:
        self.registry = registry
        self.timeout = timeout

    async def execute(self, tool_name: str, ctx: ToolContext, **kwargs) -> ToolResult:
        """执行单个工具调用。

        Args:
            tool_name: 工具名称（需已注册）
            ctx: 工具执行上下文
            **kwargs: 传递给工具 execute 方法的参数

        Returns:
            ToolResult，失败时 success=False 并附带 error 信息
        """
        tool: Tool | None = self.registry.get(tool_name)
        if tool is None:
            logger.warning("ToolExecutor: unknown tool '%s'", tool_name)
            return ToolResult(success=False, error=f"未找到工具: {tool_name}")

        start = perf_counter()
        try:
            result: ToolResult = await asyncio.wait_for(
                tool.execute(ctx, **kwargs),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            elapsed = perf_counter() - start
            logger.error(
                "ToolExecutor: tool '%s' timed out after %.2fs", tool_name, elapsed
            )
            return ToolResult(success=False, error=f"工具 {tool_name} 执行超时（{self.timeout}s）")
        except Exception as exc:
            elapsed = perf_counter() - start
            logger.exception(
                "ToolExecutor: tool '%s' raised exception after %.2fs: %s",
                tool_name, elapsed, exc,
            )
            return ToolResult(success=False, error=str(exc))
        else:
            elapsed = perf_counter() - start
            status = "ok" if result.success else "fail"
            logger.info(
                "ToolExecutor: tool='%s' status=%s elapsed=%.3fs",
                tool_name, status, elapsed,
            )
            return result

    async def execute_many(
        self,
        calls: List[Tuple[str, dict]],
        ctx: ToolContext,
    ) -> List[ToolResult]:
        """串行执行多个工具调用，返回与 calls 等长的结果列表。

        串行而非并发，避免共享 AsyncSession 的并发写入问题。

        Args:
            calls: [(tool_name, kwargs_dict), ...] 调用序列
            ctx:   共享的工具执行上下文

        Returns:
            List[ToolResult]，顺序与 calls 一致
        """
        results: List[ToolResult] = []
        for tool_name, kwargs in calls:
            result = await self.execute(tool_name, ctx, **kwargs)
            results.append(result)
        return results
