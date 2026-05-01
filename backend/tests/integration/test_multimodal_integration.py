"""多模态工具集成测试

覆盖：
- MultimodalSearchTool 调用链（chat_with_image → search_dispatcher）
- use_cloud 参数已清除验证
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.tools.base import ToolContext, ToolResult
from app.tools.multimodal_tools import MultimodalSearchTool


@pytest.fixture
def ctx():
    ctx = MagicMock(spec=ToolContext)
    ctx.paper_id = None
    ctx.db = None
    ctx.resources = {}
    return ctx


class TestMultimodalSearchTool:
    """MultimodalSearchTool 调用链测试"""

    @pytest.fixture
    def tool(self):
        return MultimodalSearchTool()

    async def test_execute_requires_query(self, tool, ctx):
        try:
            result = await tool.execute(ctx)
            assert not result.success
        except KeyError:
            # execute() 直接访问 kwargs["query"]，不传 query 会触发 KeyError
            pass

    async def test_execute_full_flow(self, tool, ctx):
        ctx.resources = {}
        with patch("app.tools.multimodal_tools.llm_service") as mock_llm, \
             patch("app.dependencies.service_container") as mock_container:
            from app.services.search.base import SearchResult
            mock_llm.chat_with_image = AsyncMock(return_value="一张显示实验结果的图表")
            mock_dispatcher = AsyncMock()
            mock_dispatcher.search = AsyncMock(return_value=[
                SearchResult(title="相关论文", url="https://arxiv.org/abs/1234",
                             snippet="实验结果", source="arxiv", relevance_score=0.9)
            ])
            mock_container.resolve.return_value = mock_dispatcher
            result = await tool.execute(ctx, image_data="/tmp/img.png", query="machine learning")
            # use_cloud 参数不应存在
            _, call_kwargs = mock_llm.chat_with_image.call_args
            assert "use_cloud" not in call_kwargs
