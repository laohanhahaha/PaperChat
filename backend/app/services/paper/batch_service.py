"""批量论文分析服务

串行执行多篇论文的分析，支持 WebSocket 进度推送和汇总报告生成
"""
import json
import logging
from typing import Callable, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.paper import Paper, PaperTextBlock
from app.models.paper_analysis import PaperAnalysisCache
from app.services.llm_service import llm_service
from app.services.chat.session_service import save_paper_section_analysis

logger = logging.getLogger(__name__)

# 单篇论文最大文本长度（与现有分析逻辑一致）
MAX_PAPER_TEXT_LENGTH = 3000


class BatchService:
    """批量论文分析服务"""

    async def batch_analyze(
        self,
        paper_ids: list[int],
        user_id: int,
        db: AsyncSession,
        ws_callback: Optional[Callable] = None,
    ) -> dict:
        """批量分析论文

        串行执行，避免并发 LLM 过载；每篇约 5-10s。

        Args:
            paper_ids: 论文ID列表
            user_id: 用户ID（权限验证）
            db: 数据库会话
            ws_callback: WebSocket 进度回调函数，签名为 async callback(dict) -> None

        Returns:
            {"results": [...], "summary": "汇总报告"}
        """
        results = []

        for i, paper_id in enumerate(paper_ids):
            try:
                # 查询论文（需属于当前用户）
                result = await db.execute(
                    select(Paper).where(
                        and_(Paper.id == paper_id, Paper.user_id == user_id)
                    )
                )
                paper = result.scalar_one_or_none()

                if not paper:
                    results.append({"paper_id": paper_id, "status": "not_found"})
                    if ws_callback:
                        await ws_callback({
                            "type": "batch_progress",
                            "current": i + 1,
                            "total": len(paper_ids),
                            "paper_id": paper_id,
                            "paper_title": f"Paper {paper_id}",
                            "status": "not_found",
                        })
                    continue

                # 调用单篇分析
                analysis_result = await self._analyze_single(paper, db)
                results.append({
                    "paper_id": paper_id,
                    "status": "success",
                    "paper_title": paper.title or f"Paper {paper_id}",
                    "result": analysis_result,
                })

                if ws_callback:
                    await ws_callback({
                        "type": "batch_progress",
                        "current": i + 1,
                        "total": len(paper_ids),
                        "paper_id": paper_id,
                        "paper_title": paper.title or f"Paper {paper_id}",
                        "status": "success",
                    })

            except Exception as e:
                logger.error(f"批量分析论文 {paper_id} 失败: {e}")
                results.append({
                    "paper_id": paper_id,
                    "status": "error",
                    "error": str(e),
                })
                if ws_callback:
                    await ws_callback({
                        "type": "batch_progress",
                        "current": i + 1,
                        "total": len(paper_ids),
                        "paper_id": paper_id,
                        "status": "error",
                        "error": str(e),
                    })

        # 生成汇总报告（1 次额外 LLM 调用）
        summary = await self.generate_summary_report(results)

        if ws_callback:
            await ws_callback({
                "type": "batch_complete",
                "total": len(paper_ids),
                "success_count": sum(1 for r in results if r["status"] == "success"),
                "error_count": sum(1 for r in results if r["status"] == "error"),
                "not_found_count": sum(1 for r in results if r["status"] == "not_found"),
                "summary": summary,
            })

        return {"results": results, "summary": summary}

    async def _analyze_single(self, paper: Paper, db: AsyncSession) -> dict:
        """分析单篇论文（提取关键信息）

        复用现有 llm_service.analyze_paper 的逻辑，
        收集完整输出后解析为结构化结果。

        Args:
            paper: Paper ORM 对象
            db: 数据库会话

        Returns:
            {"title", "abstract", "methods", "conclusions", "key_findings"}
        """
        # 获取论文文本块
        result = await db.execute(
            select(PaperTextBlock)
            .where(PaperTextBlock.paper_id == paper.id)
            .order_by(PaperTextBlock.page_number, PaperTextBlock.y0)
        )
        blocks = result.scalars().all()

        # 拼接并截断文本
        full_text = "\n".join(block.text for block in blocks)
        if len(full_text) > MAX_PAPER_TEXT_LENGTH:
            truncated = full_text[:MAX_PAPER_TEXT_LENGTH]
            for sep in ["\n\n", "。", "？", "!", "\n"]:
                last_sep = truncated.rfind(sep)
                if last_sep > MAX_PAPER_TEXT_LENGTH * 0.8:
                    truncated = truncated[: last_sep + 1]
                    break
            full_text = truncated + "\n[内容已截断...]"

        if not full_text.strip():
            return {
                "title": paper.title,
                "abstract": None,
                "methods": None,
                "conclusions": None,
                "key_findings": None,
            }

        # 使用 LLM 一次性提取结构化信息（非流式，收集完整输出）
        prompt = f"""请对以下论文内容进行分析，严格按 JSON 格式输出以下字段：
- "title": 论文标题（如有）
- "abstract": 摘要概述（2-3句话）
- "methods": 研究方法概述（2-3句话）
- "conclusions": 主要结论（2-3句话）
- "key_findings": 关键发现（列出 2-4 条，每条一句话）

只输出一个 JSON 对象，不要输出其他内容。

论文内容：
{full_text}"""

        full_response = ""
        async for chunk in llm_service.analyze_paper(full_text):
            if chunk:
                full_response += chunk

        # 尝试解析 LLM 输出为结构化结果
        try:
            # 尝试从回复中提取 JSON（LLM 可能输出 Markdown 代码块包裹的 JSON）
            json_str = full_response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            parsed = json.loads(json_str)
            return {
                "title": parsed.get("title", paper.title),
                "abstract": parsed.get("abstract"),
                "methods": parsed.get("methods"),
                "conclusions": parsed.get("conclusions"),
                "key_findings": parsed.get("key_findings"),
            }
        except (json.JSONDecodeError, IndexError):
            # JSON 解析失败，将完整回复作为 abstract 存储
            return {
                "title": paper.title,
                "abstract": full_response[:500] if full_response else None,
                "methods": None,
                "conclusions": None,
                "key_findings": None,
            }

    async def generate_summary_report(self, results: list) -> str:
        """使用 LLM 生成多篇论文汇总报告

        收集所有成功分析的结果，构造 prompt 让 LLM 生成对比分析报告。
        需要 1 次额外 LLM 调用。

        Args:
            results: batch_analyze 的结果列表

        Returns:
            汇总报告文本（Markdown 格式）
        """
        # 收集成功分析的结果
        success_results = [r for r in results if r["status"] == "success"]

        if not success_results:
            return "无成功分析的论文，无法生成汇总报告。"

        if len(success_results) == 1:
            r = success_results[0]
            title = r.get("paper_title", f"Paper {r['paper_id']}")
            analysis = r.get("result", {})
            return f"## 单篇论文分析\n\n### {title}\n\n{json.dumps(analysis, ensure_ascii=False, indent=2)}"

        # 构造汇总 prompt
        papers_info = []
        for r in success_results:
            title = r.get("paper_title", f"Paper {r['paper_id']}")
            analysis = r.get("result", {})
            papers_info.append(f"【论文：{title}】\n{json.dumps(analysis, ensure_ascii=False, indent=2)}")

        papers_content = "\n\n".join(papers_info)

        summary_prompt = f"""你是一个专业的学术论文汇总分析助手。请基于以下多篇论文的分析结果，生成一份结构化的汇总报告。

要求：
1. 概括这些论文的共同研究主题
2. 对比各论文的研究方法和主要发现
3. 总结研究趋势和关键洞察
4. 用 Markdown 格式输出，包含标题、小标题和列表

以下是需要汇总的论文分析结果：

{papers_content}"""

        # 非流式调用 LLM 生成汇总
        from langchain_core.messages import SystemMessage, HumanMessage

        messages = [
            SystemMessage(content="你是一个专业的学术论文汇总分析助手，擅长对多篇论文进行综合分析和对比。"),
            HumanMessage(content=summary_prompt),
        ]

        full_response = ""
        try:
            async for chunk in llm_service.llm.astream(messages):
                if chunk.content:
                    full_response += chunk.content
        except Exception as e:
            logger.error(f"生成汇总报告失败: {e}")
            return f"汇总报告生成失败: {str(e)}"

        return full_response if full_response else "汇总报告生成失败：LLM 未返回内容。"


# 单例
batch_service = BatchService()
