"""多模态分析工具

性能影响:
- MultimodalSearchTool: 3-8s（LLM 图片描述 + 搜索调度）
"""
import logging

from app.tools.base import Tool, ToolContext, ToolResult
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


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

        # 3. 调用 open-webSearch MCP 服务
        import json as _json
        from app.dependencies import service_container
        try:
            mcp_manager = service_container.resolve("mcp_manager")
        except Exception:
            return ToolResult(success=False, error="MCPManager 未初始化")

        try:
            raw_result = await mcp_manager.call_tool(
                server_name="open_websearch",
                tool_name="search",
                arguments={"query": combined_query, "limit": 5}
            )
            if isinstance(raw_result, str):
                search_data = _json.loads(raw_result)
            else:
                search_data = raw_result
            results_list = search_data.get("results", []) if isinstance(search_data, dict) else []
        except Exception as e:
            logger.error(f"[MultimodalSearchTool] 搜索失败: {e}")
            return ToolResult(success=False, error=f"搜索执行失败: {e}")

        # 4. 序列化结果
        serialized = []
        for r in results_list:
            serialized.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("description", ""),
                "source": "open-webSearch",
                "relevance_score": 0.0,
            })

        return ToolResult(data={
            "query": combined_query,
            "original_query": query,
            "image_description": image_description,
            "search_mode": search_mode,
            "results": serialized,
            "count": len(serialized)
        })
