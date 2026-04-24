"""多模态工具烟雾测试

验证 AnalyzeChartTool 和 MultimodalSearchTool 的调用链：
- mock pdf_service / llm_service / search_dispatcher
- 使用 AsyncMock 模拟异步方法
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.tools.base import ToolContext
from app.tools.multimodal_tools import AnalyzeChartTool, MultimodalSearchTool


class TestAnalyzeChartTool:
    """AnalyzeChartTool 调用链测试"""

    @pytest.fixture
    def tool(self):
        return AnalyzeChartTool()

    @pytest.fixture
    def mock_db_with_paper(self):
        """构造带有 Paper 返回的 mock DB session"""
        mock_paper = MagicMock()
        mock_paper.file_path = "/tmp/test_paper.pdf"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_paper

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        return mock_db

    @pytest.mark.asyncio
    async def test_analyze_chart_tool(self, tool, mock_db_with_paper):
        """验证完整调用链：DB 查询 -> 图片提取 -> LLM 分析"""
        ctx = ToolContext(db=mock_db_with_paper, paper_id=1)

        with patch("app.tools.multimodal_tools.pdf_service") as mock_pdf, \
             patch("app.tools.multimodal_tools.llm_service") as mock_llm:

            # mock PDF 服务
            mock_pdf.get_page_count = AsyncMock(return_value=5)
            mock_pdf.detect_figures_and_tables = AsyncMock(
                side_effect=lambda fp, page: [
                    {"type": "figure", "label": "Fig 1"}
                ] if page == 2 else []
            )
            mock_pdf.extract_page_images = AsyncMock(return_value=[
                {
                    "base64": "fake_base64_data",
                    "bbox": [0, 0, 100, 100],
                    "type": "png",
                    "index": 0,
                    "width": 100,
                    "height": 100,
                }
            ])

            # mock LLM 服务
            mock_llm.analyze_chart = AsyncMock(return_value={
                "chart_type": "bar",
                "data_summary": " summary",
                "key_findings": ["finding1"],
                "raw_description": "desc",
            })

            result = await tool.execute(ctx, paper_id=1)

            assert result.success is True
            assert result.data["paper_id"] == 1
            assert result.data["page_num"] == 2  # 自动检测到第 2 页
            assert result.data["image_index"] == 0
            assert "analysis" in result.data

            # 验证调用链
            mock_db_with_paper.execute.assert_awaited_once()
            mock_pdf.get_page_count.assert_awaited_once_with("/tmp/test_paper.pdf")
            mock_pdf.detect_figures_and_tables.assert_awaited()
            mock_pdf.extract_page_images.assert_awaited_once_with("/tmp/test_paper.pdf", 2)
            mock_llm.analyze_chart.assert_awaited_once_with(
                "fake_base64_data",
                chart_type_hint="",
                question="",
            )

    @pytest.mark.asyncio
    async def test_analyze_chart_tool_explicit_page(self, tool, mock_db_with_paper):
        """验证显式传入 page_num 时跳过自动检测"""
        ctx = ToolContext(db=mock_db_with_paper, paper_id=1)

        with patch("app.tools.multimodal_tools.pdf_service") as mock_pdf, \
             patch("app.tools.multimodal_tools.llm_service") as mock_llm:

            mock_pdf.extract_page_images = AsyncMock(return_value=[
                {"base64": "img_data", "bbox": [0, 0, 50, 50], "type": "png", "index": 0, "width": 50, "height": 50}
            ])
            mock_llm.analyze_chart = AsyncMock(return_value={"chart_type": "line"})

            result = await tool.execute(ctx, paper_id=1, page_num=3, image_index=0, question="这是什么图表？")

            assert result.success is True
            assert result.data["page_num"] == 3
            mock_pdf.get_page_count.assert_not_called()
            mock_pdf.detect_figures_and_tables.assert_not_called()
            mock_pdf.extract_page_images.assert_awaited_once_with("/tmp/test_paper.pdf", 3)
            mock_llm.analyze_chart.assert_awaited_once_with(
                "img_data", chart_type_hint="", question="这是什么图表？"
            )

    @pytest.mark.asyncio
    async def test_analyze_chart_no_paper_id(self, tool):
        """验证缺少 paper_id 时返回错误"""
        ctx = ToolContext()
        result = await tool.execute(ctx)
        assert result.success is False
        assert "paper_id" in result.error

    @pytest.mark.asyncio
    async def test_analyze_chart_no_images(self, tool, mock_db_with_paper):
        """验证页面无图片时返回错误"""
        ctx = ToolContext(db=mock_db_with_paper, paper_id=1)

        with patch("app.tools.multimodal_tools.pdf_service") as mock_pdf:
            mock_pdf.extract_page_images = AsyncMock(return_value=[])

            result = await tool.execute(ctx, paper_id=1, page_num=0)

            assert result.success is False
            assert "未找到图片" in result.error


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
                use_cloud=True,
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
