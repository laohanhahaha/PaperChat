"""
[DEPRECATED] 此文件已被新版模块替代，保留仅为过渡期兼容。
替代模块: app.services.agent/ (agent_service.py, intent.py, tools/, react_agent.py, planner.py)
请勿在新代码中导入此文件。
"""
"""Agent 核心服务 - 意图识别、工具调用、任务规划

Agent 多步推理每多一步需要额外一次 LLM 调用：
- 意图识别：约 500ms + 200 tokens
- 任务规划：约 1-2s + 500 tokens
- 每步工具调用：取决于具体工具
- 结果聚合：约 1-2s + 500-2000 tokens

总体性能影响：
- 简单请求增加约 1s（只做意图识别后直接走 RAG 问答）
- 复杂请求增加 3-8s
"""
from typing import AsyncGenerator, Optional, List
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json

from langchain_core.messages import SystemMessage, HumanMessage

from app.services.llm_service import llm_service
from app.config import settings


# ============ 工具上下文和结果定义 ============

@dataclass
class ToolContext:
    """统一的工具执行上下文"""
    db: Optional[object] = None  # AsyncSession
    paper_id: Optional[int] = None
    paper_ids: List[int] = field(default_factory=list)
    user_id: Optional[int] = None
    session_id: Optional[int] = None

@dataclass
class ToolResult:
    """统一的工具返回值"""
    success: bool = True
    data: dict = field(default_factory=dict)
    error: Optional[str] = None


# ============ 工具基类 ============

class Tool(ABC):
    name: str
    description: str
    
    @abstractmethod
    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        pass


# ============ 具体工具实现 ============

class SearchTextTool(Tool):
    """搜索论文文本"""
    name = "search_text"
    description = "在论文中搜索与查询相关的文本段落，返回最相关的文本块及其页码"
    
    async def execute(self, ctx: ToolContext, query: str, top_k: int = 5, paper_id: int = None) -> ToolResult:
        from app.services.rag_service import rag_service
        # 优先使用传入的paper_id，否则从ctx获取
        pid = paper_id if paper_id is not None else ctx.paper_id
        if pid is None:
            return ToolResult(success=False, error="需要提供paper_id")
        results = await rag_service.search(pid, query, top_k)
        return ToolResult(data={
            "results": results,
            "count": len(results)
        })


class ExtractKeyPointsTool(Tool):
    """提取核心知识点"""
    name = "extract_key_points"
    description = "从论文文本中提取核心知识点、关键概念和重要发现"
    
    async def execute(self, ctx: ToolContext, text: str, max_points: int = 5) -> ToolResult:
        """使用 LLM 提取关键知识点"""
        prompt = f"""请从以下学术文本中提取 {max_points} 个核心知识点或关键概念。

要求：
1. 每个知识点包含：概念名称、简要解释、在文本中的重要性
2. 优先提取专业术语、方法论、核心发现
3. 以 JSON 数组格式返回

文本内容：
{text[:8000]}

请返回 JSON 格式：
[{{"concept": "概念名称", "explanation": "解释", "importance": "重要性说明"}}, ...]
"""
        messages = [
            SystemMessage(content="你是学术知识提取专家，擅长从论文中提取核心概念。"),
            HumanMessage(content=prompt)
        ]
        
        # 使用非流式调用获取完整结果
        response = await llm_service.llm.ainvoke(messages)
        
        # 尝试解析 JSON
        try:
            content = response.content
            # 提取 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            points = json.loads(content.strip())
            return ToolResult(data={"points": points, "count": len(points)})
        except Exception as e:
            return ToolResult(success=False, error=str(e), data={
                "points": [{"concept": "提取失败", "explanation": str(e), "importance": "N/A"}],
                "count": 0,
                "raw_response": response.content
            })


class SummarizeTool(Tool):
    """文本摘要"""
    name = "summarize"
    description = "对指定文本进行摘要，保留核心论点和关键数据"
    
    async def execute(self, ctx: ToolContext, text: str, max_length: int = 500) -> ToolResult:
        """调用 llm_service 的 summarize_text 方法（非流式版本）"""
        # 收集流式结果
        full_summary = ""
        async for chunk in llm_service.summarize_text(text):
            full_summary += chunk
        
        return ToolResult(data={
            "summary": full_summary[:max_length] if max_length else full_summary,
            "full_summary": full_summary
        })


class TranslateTool(Tool):
    """翻译"""
    name = "translate"
    description = "翻译学术文本，保留专业术语准确性"
    
    async def execute(self, ctx: ToolContext, text: str, target_lang: str = "zh") -> ToolResult:
        """调用 llm_service 的 translate_text 方法"""
        full_translation = ""
        async for chunk in llm_service.translate_text(text, target_lang):
            full_translation += chunk
        
        return ToolResult(data={
            "translation": full_translation,
            "source_lang": "auto",
            "target_lang": target_lang
        })


class ExplainTermTool(Tool):
    """术语解释"""
    name = "explain_term"
    description = "解释学术术语，结合上下文提供准确解释"
    
    async def execute(self, ctx: ToolContext, term: str, context: str = "") -> ToolResult:
        """调用 llm_service 的 explain_term 方法"""
        full_explanation = ""
        async for chunk in llm_service.explain_term(term, context):
            full_explanation += chunk
        
        return ToolResult(data={
            "term": term,
            "explanation": full_explanation
        })


class GetPaperInfoTool(Tool):
    """获取论文信息"""
    name = "get_paper_info"
    description = "获取论文的元数据信息（标题、作者、摘要等）"
    
    async def execute(self, ctx: ToolContext, paper_id: int = None) -> ToolResult:
        """从数据库查询论文信息"""
        db = ctx.db
        if db is None:
            return ToolResult(success=False, error="需要提供数据库会话")
        
        # 优先使用传入的paper_id，否则从ctx获取
        pid = paper_id if paper_id is not None else ctx.paper_id
        if pid is None:
            return ToolResult(success=False, error="需要提供paper_id")
        
        from sqlalchemy import select
        from app.models.paper import Paper
        
        result = await db.execute(select(Paper).where(Paper.id == pid))
        paper = result.scalar_one_or_none()
        
        if not paper:
            return ToolResult(success=False, error=f"未找到论文 ID: {pid}")
        
        return ToolResult(data={
            "id": paper.id,
            "title": paper.title,
            "authors": paper.authors,
            "abstract": paper.abstract,
            "doi": paper.doi,
            "page_count": paper.page_count,
            "category": paper.category,
            "reading_status": paper.reading_status
        })


class CompareContentTool(Tool):
    """对比内容"""
    name = "compare_content"
    description = "对比多篇论文的特定内容维度"
    
    async def execute(self, ctx: ToolContext, paper_contents: list[dict], dimension: str = "general") -> ToolResult:
        """
        paper_contents: [{"title": "论文1", "text": "内容"}, ...]
        dimension: 对比维度 (methodology/results/contributions/general)
        """
        # 构建论文文本列表
        papers_text = []
        for p in paper_contents:
            papers_text.append({
                "title": p.get("title", "未知论文"),
                "text": p.get("text", "")[:5000]  # 限制长度
            })
        
        # 收集流式结果
        full_comparison = ""
        async for chunk in llm_service.compare_papers(papers_text):
            full_comparison += chunk
        
        return ToolResult(data={
            "dimension": dimension,
            "comparison": full_comparison,
            "paper_count": len(paper_contents)
        })


class GenerateOutlineTool(Tool):
    """生成提纲"""
    name = "generate_outline"
    description = "基于论文内容生成研究报告或文献综述的提纲"
    
    async def execute(self, ctx: ToolContext, topic: str, context: str = "", paper_ids: list[int] = None) -> ToolResult:
        """使用 LLM 生成提纲"""
        # 优先使用传入的paper_ids，否则从ctx获取
        pids = paper_ids if paper_ids is not None else ctx.paper_ids
        
        prompt = f"""请为以下主题生成一份详细的研究报告提纲：

主题：{topic}

{f"相关论文内容：\n{context[:5000]}" if context else ""}

要求：
1. 提纲结构清晰，层级分明
2. 包含引言、主体章节、结论
3. 每个章节提供简要说明
4. 适合作为研究报告或文献综述的框架

请直接输出提纲内容。"""
        
        messages = [
            SystemMessage(content="你是学术研究专家，擅长构建清晰的研究报告结构。"),
            HumanMessage(content=prompt)
        ]
        
        response = await llm_service.llm.ainvoke(messages)
        
        return ToolResult(data={
            "topic": topic,
            "outline": response.content,
            "paper_count": len(pids) if pids else 0
        })


class AssessQualityTool(Tool):
    """评估质量"""
    name = "assess_quality"
    description = "评估论文的研究质量和方法论严谨性"
    
    async def execute(self, ctx: ToolContext, paper_text: str, paper_title: str = "") -> ToolResult:
        """使用 LLM 评估论文质量"""
        prompt = f"""请对以下学术论文进行质量评估：

{f"论文标题：{paper_title}" if paper_title else ""}

论文内容：
{paper_text[:8000]}

请从以下维度进行评估（1-5分）：
1. 研究创新性
2. 方法论严谨性
3. 实验设计合理性
4. 数据分析充分性
5. 结论可信度
6. 写作规范性

请返回 JSON 格式：
{{
    "scores": {{
        "innovation": 分数,
        "methodology": 分数,
        "experimental_design": 分数,
        "data_analysis": 分数,
        "conclusion_validity": 分数,
        "writing_quality": 分数
    }},
    "total_score": 总分,
    "assessment": "总体评价",
    "strengths": ["优点1", "优点2"],
    "weaknesses": ["不足1", "不足2"],
    "recommendations": "改进建议"
}}"""
        
        messages = [
            SystemMessage(content="你是学术论文评审专家，擅长评估研究质量和方法论。"),
            HumanMessage(content=prompt)
        ]
        
        response = await llm_service.llm.ainvoke(messages)
        
        try:
            content = response.content
            # 提取 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            assessment = json.loads(content.strip())
            return ToolResult(data=assessment)
        except Exception as e:
            return ToolResult(success=False, error=str(e), data={
                "raw_response": response.content,
                "scores": {},
                "assessment": "评估解析失败"
            })


# ============ Agent 核心服务 ============

INTENT_CLASSIFICATION_PROMPT = """你是用户意图识别专家。请分析用户的请求，判断其意图类型和复杂度。

用户请求：{message}

请分析并返回 JSON 格式：
{{
    "intent": "simple_qa|analysis|comparison|search|writing|multi_step",
    "requires_tools": ["需要的工具名称列表"],
    "complexity": "low|medium|high",
    "reasoning": "简要说明判断理由"
}}

意图类型说明：
- simple_qa: 简单问答，可直接用 RAG 回答
- analysis: 分析类请求（总结、解释、评估）
- comparison: 对比多篇论文
- search: 搜索特定信息
- writing: 生成内容（提纲、综述）
- multi_step: 复杂多步任务

工具列表：
- search_text: 搜索论文文本
- summarize: 摘要生成
- explain_term: 术语解释
- translate: 翻译
- extract_key_points: 提取知识点
- compare_content: 对比内容
- generate_outline: 生成提纲
- assess_quality: 质量评估
- get_paper_info: 获取论文信息"""


INTENT_KEYWORDS = {
    "chapter_overview": {
        "keywords": ["章节概述", "概述", "章节总结", "文章结构", "目录", " outline ", "章节内容", "各章节", "章节介绍", "结构分析"],
        "intent": "chapter_overview",
        "tool": "analyze_paper"
    },
    "deep_analysis": {
        "keywords": ["深度分析", "深入分析", "详细分析", "深层分析", "分析", "研究分析", "学术分析", "critical analysis", "detailed analysis"],
        "intent": "deep_analysis",
        "tool": "deep_analyze_paper"
    },
    "key_points": {
        "keywords": ["核心知识点", "关键点", "重点", "核心要点", "主要观点", "关键概念", "核心概念", "知识点", "key points", "main points", "核心思想"],
        "intent": "key_points",
        "tool": "extract_key_points"
    },
    "compare": {
        "keywords": ["对比", "比较", "差异", "异同", "对照", "compare", "comparison", "versus", "vs "],
        "intent": "comparison",
        "tool": "compare_content"
    },
    "summary": {
        "keywords": ["摘要", "总结", "概括", "提炼", "summarize", "summary", "概括"],
        "intent": "summary",
        "tool": "summarize"
    },
    "translate": {
        "keywords": ["翻译", "译成", "translate", "中译", "英译"],
        "intent": "translate",
        "tool": "translate"
    },
    "explain": {
        "keywords": ["解释", "说明", "什么是", "含义", "定义", "explain", "definition", "definition of"],
        "intent": "explain",
        "tool": "explain_term"
    },
    "cross_doc": {
        "keywords": ["跨文档", "跨论文", "多篇论文", "多文档", "across papers", "multiple papers"],
        "intent": "cross_doc",
        "tool": "cross_doc_chat"
    },
    "quality_assessment": {
        "keywords": ["质量评估", "评估", "好不好", "优缺点", "优劣势", "assess", "quality", "评估质量"],
        "intent": "quality_assessment",
        "tool": "assess_quality"
    },
    "outline": {
        "keywords": ["提纲", "大纲", "结构", "写报告", "写综述", "outline", "structure", "报告大纲"],
        "intent": "outline",
        "tool": "generate_outline"
    },
    "save_card": {
        "keywords": ["保存", "记下", "收藏知识", "保存知识点", "记住这个"],
        "intent": "save_card",
        "tool": "save_card"
    },
    "search_cards": {
        "keywords": ["笔记", "知识卡片", "之前的笔记", "我记过", "知识点"],
        "intent": "search_cards",
        "tool": "search_cards"
    },
    "recent_papers": {
        "keywords": ["最近读", "最近论文", "阅读历史", "最近上传"],
        "intent": "recent_papers",
        "tool": "recent_papers"
    },
    "search_papers": {
        "keywords": ["找论文", "搜索论文", "推荐论文", "相关论文", "有没有论文"],
        "intent": "search_papers",
        "tool": "search_papers"
    }
}


def classify_by_keywords(message: str) -> dict:
    """基于关键词的意图识别（快速识别，用于直接功能触发）
    
    Args:
        message: 用户消息
        
    Returns:
        {"matched": True, "intent": "...", "tool": "...", "confidence": "high|medium|low"}
        或
        {"matched": False}
    """
    message_lower = message.lower()
    
    best_match = None
    best_score = 0
    
    for intent_name, config in INTENT_KEYWORDS.items():
        score = 0
        for keyword in config["keywords"]:
            if keyword.lower() in message_lower:
                score += 1
        
        if score > 0 and score > best_score:
            best_score = score
            best_match = {
                "intent": config["intent"],
                "tool": config["tool"],
                "confidence": "high" if score >= 2 else "medium"
            }
    
    if best_match:
        return {"matched": True, **best_match}
    
    return {"matched": False}


TASK_PLANNING_PROMPT = """你是任务规划专家。请将用户的复杂请求拆解为有序的子任务。

用户请求：{message}
意图分析：{intent}
上下文：{context}

可用工具：
- search_text: 搜索论文文本，参数: paper_id, query, top_k
- summarize: 摘要生成，参数: text
- explain_term: 术语解释，参数: term, context
- translate: 翻译，参数: text, target_lang
- extract_key_points: 提取知识点，参数: text
- compare_content: 对比内容，参数: paper_contents, dimension
- generate_outline: 生成提纲，参数: topic, context
- assess_quality: 质量评估，参数: paper_text
- get_paper_info: 获取论文信息，参数: paper_id

请返回任务计划 JSON 格式：
[
    {{
        "step": 1,
        "tool": "工具名称",
        "params": {{"参数名": "参数值"}},
        "description": "步骤描述",
        "depends_on": []  // 依赖的步骤编号
    }},
    ...
]

注意：
1. 步骤按执行顺序排列
2. 简单请求可能只需 1-2 步
3. 复杂请求可能需要 3-5 步
4. 参数值中可以使用 {{previous_result}} 引用前序步骤结果"""


class AgentService:
    """Agent 核心服务"""
    
    def __init__(self):
        self.tools = self._register_tools()
    
    def _register_tools(self) -> dict[str, Tool]:
        """注册所有可用工具"""
        from app.tools.knowledge_tools import SaveCardTool, SearchCardsTool
        from app.tools.query_tools import RecentPapersTool, SearchPapersTool
        tools = [
            SearchTextTool(),
            ExtractKeyPointsTool(),
            SummarizeTool(),
            TranslateTool(),
            ExplainTermTool(),
            GetPaperInfoTool(),
            CompareContentTool(),
            GenerateOutlineTool(),
            AssessQualityTool(),
            SaveCardTool(),
            SearchCardsTool(),
            RecentPapersTool(),
            SearchPapersTool(),
        ]
        return {t.name: t for t in tools}
    
    async def classify_intent(self, user_message: str) -> dict:
        """意图识别
        
        使用 LLM 判断用户请求类型，返回：
        {
            "intent": "simple_qa|analysis|comparison|search|writing|multi_step",
            "requires_tools": ["search_text", "summarize"],
            "complexity": "low|medium|high",
            "reasoning": "判断理由"
        }
        
        性能：约 500ms + 200 tokens
        """
        prompt = INTENT_CLASSIFICATION_PROMPT.format(message=user_message)
        
        messages = [
            SystemMessage(content="你是用户意图识别专家。"),
            HumanMessage(content=prompt)
        ]
        
        response = await llm_service.llm.ainvoke(messages)
        
        try:
            content = response.content
            # 提取 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            intent = json.loads(content.strip())
            return intent
        except Exception as e:
            # 解析失败返回默认意图
            return {
                "intent": "simple_qa",
                "requires_tools": ["search_text"],
                "complexity": "low",
                "reasoning": f"解析失败，使用默认意图: {str(e)}"
            }
    
    async def plan_tasks(self, user_message: str, intent: dict, context: dict = None) -> list[dict]:
        """任务规划
        
        对于复杂请求，拆解为有序的子任务列表：
        [
            {"step": 1, "tool": "search_text", "params": {...}, "description": "搜索相关内容"},
            {"step": 2, "tool": "summarize", "params": {...}, "description": "生成摘要"},
            ...
        ]
        
        简单请求：直接返回单步计划
        复杂请求：使用 LLM 进行多步规划
        
        性能：约 1-2s + 500 tokens
        """
        context = context or {}
        complexity = intent.get("complexity", "low")
        intent_type = intent.get("intent", "simple_qa")
        
        # 简单请求：直接生成单步计划
        if complexity == "low" or intent_type == "simple_qa":
            paper_id = context.get("paper_id")
            if paper_id:
                return [{
                    "step": 1,
                    "tool": "search_text",
                    "params": {"paper_id": paper_id, "query": user_message, "top_k": 5},
                    "description": "搜索相关内容并直接回答",
                    "depends_on": []
                }]
            else:
                return [{
                    "step": 1,
                    "tool": "explain_term",
                    "params": {"term": user_message, "context": ""},
                    "description": "直接回答用户问题",
                    "depends_on": []
                }]
        
        # 复杂请求：使用 LLM 规划
        prompt = TASK_PLANNING_PROMPT.format(
            message=user_message,
            intent=json.dumps(intent, ensure_ascii=False),
            context=json.dumps(context, ensure_ascii=False)
        )
        
        messages = [
            SystemMessage(content="你是任务规划专家。"),
            HumanMessage(content=prompt)
        ]
        
        response = await llm_service.llm.ainvoke(messages)
        
        try:
            content = response.content
            # 提取 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            plan = json.loads(content.strip())
            
            # 注入上下文参数
            paper_id = context.get("paper_id")
            if paper_id:
                for step in plan:
                    if "paper_id" in step.get("params", {}):
                        step["params"]["paper_id"] = paper_id
            
            return plan
        except Exception as e:
            # 解析失败返回默认计划
            paper_id = context.get("paper_id")
            if paper_id:
                return [{
                    "step": 1,
                    "tool": "search_text",
                    "params": {"paper_id": paper_id, "query": user_message, "top_k": 5},
                    "description": "搜索相关内容（规划失败后的默认步骤）",
                    "depends_on": []
                }]
            return []
    
    async def execute_plan(self, plan: list[dict], context: dict) -> AsyncGenerator[dict, None]:
        """执行任务计划
        
        逐步执行，每步返回进度和结果：
        yield {"type": "step_start", "step": 1, "description": "搜索相关内容"}
        yield {"type": "step_result", "step": 1, "result": {...}}
        ...
        yield {"type": "final_answer", "content": "最终整合答案"}
        
        性能：取决于具体工具调用
        """
        step_results = {}
        db = context.get("db")
        paper_id = context.get("paper_id")
        paper_ids = context.get("paper_ids", [])
        user_id = context.get("user_id")
        session_id = context.get("session_id")
        
        # 创建统一的工具执行上下文
        ctx = ToolContext(
            db=db,
            paper_id=paper_id,
            paper_ids=paper_ids,
            user_id=user_id,
            session_id=session_id
        )
        
        for step in plan:
            step_num = step.get("step", 1)
            tool_name = step.get("tool", "")
            params = step.get("params", {})
            description = step.get("description", f"执行步骤 {step_num}")
            
            # 发送步骤开始事件
            yield {
                "type": "step_start",
                "step": step_num,
                "description": description,
                "tool": tool_name
            }
            
            try:
                # 获取工具并执行
                tool = self.tools.get(tool_name)
                if not tool:
                    result = {"error": f"未知工具: {tool_name}"}
                else:
                    tool_result = await tool.execute(ctx, **params)
                    # 将 ToolResult 转换为 dict 以保持兼容性
                    result = {
                        "success": tool_result.success,
                        **tool_result.data
                    }
                    if tool_result.error:
                        result["error"] = tool_result.error
                
                step_results[step_num] = result
                
                # 发送步骤结果
                yield {
                    "type": "step_result",
                    "step": step_num,
                    "result": result,
                    "status": "success" if result.get("success", True) and not result.get("error") else "error"
                }
                
            except Exception as e:
                error_result = {"error": str(e), "success": False}
                step_results[step_num] = error_result
                yield {
                    "type": "step_result",
                    "step": step_num,
                    "result": error_result,
                    "status": "error"
                }
        
        # 聚合结果生成最终答案
        async for chunk in self.aggregate_results(step_results, context.get("original_question", "")):
            yield {
                "type": "final_answer_chunk",
                "content": chunk
            }
    
    async def aggregate_results(self, step_results: dict, original_question: str) -> AsyncGenerator[str, None]:
        """结果聚合
        
        将多步工具调用结果整合为连贯的最终回答
        使用 LLM 流式输出
        
        性能：约 1-2s + 500-2000 tokens
        """
        if not step_results:
            yield "抱歉，没有获取到任何结果。"
            return
        
        # 构建结果摘要
        results_summary = []
        for step_num, result in sorted(step_results.items()):
            # 简化结果用于提示词
            simplified = self._simplify_result(result)
            results_summary.append(f"步骤 {step_num}: {simplified}")
        
        prompt = f"""请基于以下工具执行结果，回答用户的问题。

用户问题：{original_question}

工具执行结果：
{chr(10).join(results_summary)}

要求：
1. 整合所有步骤的结果，给出完整、连贯的回答
2. 保持学术性和专业性
3. 使用中文回答
4. 如有具体数据或引用，请保留

请直接输出最终答案："""
        
        messages = [
            SystemMessage(content="你是学术问答专家，擅长整合信息并给出清晰的回答。"),
            HumanMessage(content=prompt)
        ]
        
        async for chunk in llm_service.llm.astream(messages):
            if chunk.content:
                yield chunk.content
    
    def _simplify_result(self, result: dict, max_length: int = 500) -> str:
        """简化结果用于提示词，避免过长"""
        if "error" in result:
            return f"错误: {result['error']}"
        
        # 提取关键信息
        if "summary" in result:
            return f"摘要: {result['summary'][:max_length]}"
        if "explanation" in result:
            return f"解释: {result['explanation'][:max_length]}"
        if "translation" in result:
            return f"翻译: {result['translation'][:max_length]}"
        if "results" in result and isinstance(result["results"], list):
            count = len(result["results"])
            return f"检索到 {count} 条结果"
        if "points" in result:
            count = len(result["points"])
            return f"提取了 {count} 个知识点"
        if "comparison" in result:
            return f"对比结果: {result['comparison'][:max_length]}"
        if "outline" in result:
            return f"提纲: {result['outline'][:max_length]}"
        if "assessment" in result:
            return f"评估: {result['assessment'][:max_length]}"
        
        # 默认返回 JSON 字符串
        return json.dumps(result, ensure_ascii=False)[:max_length]


# 全局单例
agent_service = AgentService()
