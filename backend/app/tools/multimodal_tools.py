"""多模态分析工具

性能影响:
- AnalyzeChartTool: 单次 2-5s（云端 LLM），含 PDF 提取 + 图表分析
- MultimodalSearchTool: 3-8s（LLM 图片描述 + 搜索调度）
"""
import logging

from sqlalchemy import select

from app.tools.base import Tool, ToolContext, ToolResult
from app.services.llm_service import llm_service
from app.services.pdf_service import pdf_service

logger = logging.getLogger(__name__)


class AnalyzeChartTool(Tool):
    name = "analyze_chart"
    description = "分析 PDF 论文中的图表，识别图表类型、提取数据摘要和关键发现"
    parameters = {
        "type": "object",
        "properties": {
            "paper_id": {"type": "integer", "description": "论文 ID"},
            "page_num": {"type": "integer", "description": "页码（从0开始），不传则自动检测"},
            "image_index": {"type": "integer", "description": "该页第几张图（从0开始），默认0"},
            "question": {"type": "string", "description": "针对图表的具体问题"}
        },
        "required": ["paper_id"]
    }

    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        paper_id = kwargs.get("paper_id") or ctx.paper_id
        page_num = kwargs.get("page_num")
        image_index = kwargs.get("image_index", 0)
        question = kwargs.get("question", "")

        if paper_id is None:
            return ToolResult(success=False, error="需要提供 paper_id")

        db = ctx.db
        if db is None:
            return ToolResult(success=False, error="需要提供数据库会话")

        # 1. 获取论文文件路径
        from app.models.paper import Paper
        result = await db.execute(select(Paper).where(Paper.id == paper_id))
        paper = result.scalar_one_or_none()
        if not paper:
            return ToolResult(success=False, error=f"未找到论文 ID: {paper_id}")

        file_path = paper.file_path

        # 2. 自动检测页码（如果未提供）
        if page_num is None:
            page_num = await self._detect_first_figure_page(file_path)
            if page_num is None:
                return ToolResult(success=False, error="未能在论文中检测到包含图表的页面")
            logger.info(f"[AnalyzeChartTool] 自动检测到图表页: {page_num}")

        # 3. 提取图片
        try:
            images = await pdf_service.extract_page_images(file_path, page_num)
        except Exception as e:
            logger.error(f"[AnalyzeChartTool] 提取图片失败: {e}")
            return ToolResult(success=False, error=f"提取图片失败: {e}")

        if not images:
            return ToolResult(success=False, error=f"第 {page_num} 页未找到图片")

        if image_index >= len(images):
            return ToolResult(
                success=False,
                error=f"image_index {image_index} 超出范围（该页共 {len(images)} 张图片）"
            )

        image_data = images[image_index]["base64"]

        # 4. 分析图片
        try:
            analysis = await llm_service.analyze_chart(
                image_data,
                chart_type_hint="",
                question=question
            )
        except Exception as e:
            logger.error(f"[AnalyzeChartTool] LLM 分析失败: {e}")
            return ToolResult(success=False, error=f"图表分析失败: {e}")

        return ToolResult(data={
            "paper_id": paper_id,
            "page_num": page_num,
            "image_index": image_index,
            "analysis": analysis
        })

    async def _detect_first_figure_page(self, file_path: str) -> int | None:
        """自动检测第一个包含图表的页面

        性能: 每页 ~200ms，通常前 5 页即可命中
        """
        try:
            total_pages = await pdf_service.get_page_count(file_path)
        except Exception:
            return None

        # 优先检查前 10 页（多数论文图表在前半部分）
        for page in range(min(total_pages, 10)):
            try:
                figures = await pdf_service.detect_figures_and_tables(file_path, page)
                if any(f.get("type") == "figure" for f in figures):
                    return page
            except Exception:
                continue

        #  fallback: 检查全部页面
        for page in range(10, total_pages):
            try:
                figures = await pdf_service.detect_figures_and_tables(file_path, page)
                if any(f.get("type") == "figure" for f in figures):
                    return page
            except Exception:
                continue

        return None


class MultimodalSearchTool(Tool):
    name = "multimodal_search"
    description = "基于图片和文本进行多模态搜索，先用 LLM 描述图片内容，再结合文本查询进行搜索"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索查询文本"},
            "image_data": {"type": "string", "description": "base64 编码的图片（可选）"},
            "search_mode": {
                "type": "string",
                "enum": ["text_with_visual", "visual_only", "text_only"],
                "description": "搜索模式"
            }
        },
        "required": ["query"]
    }

    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        query = kwargs["query"]
        image_data = kwargs.get("image_data")
        search_mode = kwargs.get("search_mode", "text_with_visual")

        # 1. 如果有图片且不是纯文本模式，用 LLM 生成描述
        image_description = ""
        if image_data and search_mode != "text_only":
            try:
                image_description = await llm_service.chat_with_image(
                    image_data,
                    prompt="请详细描述这张图片的内容，包括其中可能包含的图表、数据、公式或关键视觉信息",
                    image_type="base64",
                    use_cloud=True
                )
            except Exception as e:
                logger.error(f"[MultimodalSearchTool] 图片描述失败: {e}")
                # 图片描述失败时降级为纯文本搜索
                image_description = ""
                search_mode = "text_only"

        # 2. 组合查询
        if search_mode == "visual_only":
            combined_query = image_description or query
        elif search_mode == "text_only" or not image_description:
            combined_query = query
        else:
            combined_query = f"{query}\n\n图片内容描述：{image_description}"

        # 3. 调用 SearchDispatcher
        from app.dependencies import service_container
        try:
            search_dispatcher = service_container.resolve("search_dispatcher")
        except KeyError:
            return ToolResult(success=False, error="SearchDispatcher 未初始化")

        try:
            results = await search_dispatcher.search(
                combined_query,
                search_type="general",
                max_results=5
            )
        except Exception as e:
            logger.error(f"[MultimodalSearchTool] 搜索失败: {e}")
            return ToolResult(success=False, error=f"搜索执行失败: {e}")

        # 4. 序列化结果
        serialized = []
        for r in results:
            serialized.append({
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "source": r.source,
                "relevance_score": r.relevance_score,
            })

        return ToolResult(data={
            "query": combined_query,
            "original_query": query,
            "image_description": image_description,
            "search_mode": search_mode,
            "results": serialized,
            "count": len(serialized)
        })
