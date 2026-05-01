"""多模态工具烟雾测试

验证 MultimodalSearchTool 的调用链：
- mock llm_service / search_dispatcher
- 使用 AsyncMock 模拟异步方法
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.tools.base import ToolContext
from app.tools.multimodal_tools import MultimodalSearchTool


class TestMultimodalSearchTool:
    """MultimodalSearchTool 调用链测试"""

    @pytest.fixture
    def tool(self):
        return MultimodalSearchTool()

    @pytest.fixture
    def mock_search_dispatcher(self):
        mock = AsyncMock()
        mock.search = AsyncMock(return_value=[
            MagicMock(title="Result 1", url="http://example.com/1", snippet="snippet1", source="duckduckgo", relevance_score=0.9),
            MagicMock(title="Result 2", url="http://example.com/2", snippet="snippet2", source="bing", relevance_score=0.8),
        ])
        return mock

    @pytest.mark.asyncio
    async def test_multimodal_search_tool(self, tool, mock_search_dispatcher):
        """验证完整调用链：图片描述 -> 组合查询 -> 搜索调度"""
        ctx = ToolContext()

        with patch("app.tools.multimodal_tools.llm_service") as mock_llm, \
             patch("app.dependencies.service_container") as mock_container:

            mock_llm.chat_with_image = AsyncMock(return_value="这是一张展示神经网络架构的图表")
            mock_container.resolve.return_value = mock_search_dispatcher

            result = await tool.execute(
                ctx,
                query="神经网络架构",
                image_data="fake_image_base64",
                search_mode="text_with_visual"
            )

            assert result.success is True
            assert result.data["original_query"] == "神经网络架构"
            assert result.data["image_description"] == "这是一张展示神经网络架构的图表"
            assert result.data["search_mode"] == "text_with_visual"
            assert result.data["count"] == 2

            # 验证 LLM 被调用生成图片描述
            mock_llm.chat_with_image.assert_awaited_once_with(
                "fake_image_base64",
                prompt="请详细描述这张图片的内容，包括其中可能包含的图表、数据、公式或关键视觉信息",
                image_type="base64",
            )

            # 验证搜索调度器被调用
            mock_container.resolve.assert_called_once_with("search_dispatcher")
            mock_search_dispatcher.search.assert_awaited_once()
            call_args = mock_search_dispatcher.search.call_args
            assert "神经网络架构" in call_args[0][0]
            assert "图片内容描述" in call_args[0][0]
            assert call_args[1]["search_type"] == "general"

    @pytest.mark.asyncio
    async def test_multimodal_search_text_only(self, tool, mock_search_dispatcher):
        """验证 text_only 模式不调用图片描述"""
        ctx = ToolContext()

        with patch("app.tools.multimodal_tools.llm_service") as mock_llm, \
             patch("app.dependencies.service_container") as mock_container:

            mock_container.resolve.return_value = mock_search_dispatcher

            result = await tool.execute(
                ctx,
                query="深度学习",
                search_mode="text_only"
            )

            assert result.success is True
            mock_llm.chat_with_image.assert_not_called()
            mock_search_dispatcher.search.assert_awaited_once_with(
                "深度学习",
                search_type="general",
                max_results=5,
            )

    @pytest.mark.asyncio
    async def test_multimodal_search_visual_only(self, tool, mock_search_dispatcher):
        """验证 visual_only 模式仅使用图片描述搜索"""
        ctx = ToolContext()

        with patch("app.tools.multimodal_tools.llm_service") as mock_llm, \
             patch("app.dependencies.service_container") as mock_container:

            mock_llm.chat_with_image = AsyncMock(return_value="图片描述内容")
            mock_container.resolve.return_value = mock_search_dispatcher

            result = await tool.execute(
                ctx,
                query="",
                image_data="fake_image_base64",
                search_mode="visual_only"
            )

            assert result.success is True
            assert result.data["query"] == "图片描述内容"
            mock_search_dispatcher.search.assert_awaited_once_with(
                "图片描述内容",
                search_type="general",
                max_results=5,
            )

    @pytest.mark.asyncio
    async def test_multimodal_search_dispatcher_unavailable(self, tool):
        """验证 SearchDispatcher 未初始化时返回错误"""
        ctx = ToolContext()

        with patch("app.tools.multimodal_tools.service_container", create=True) as mock_container:
            mock_container.resolve.side_effect = KeyError("search_dispatcher")

            result = await tool.execute(ctx, query="测试")

            assert result.success is False
            assert "SearchDispatcher 未初始化" in result.error
