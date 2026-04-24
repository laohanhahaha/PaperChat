"""统一聊天处理器

统一聊天入口 - 根据关键词自动路由到不同功能（RAG问答、分析、跨文档、工具调用等）
"""
import json
import asyncio
import logging

from langchain_core.messages import SystemMessage, HumanMessage

from app.database import AsyncSessionLocal
from app.services.llm_service import llm_service
from app.services.agent.agent_service import (
    classify_by_keywords, classify_by_llm,
)
from app.services.core.tool_base import ToolContext, ToolResult
from app.services.agent.tools import (
    LiteratureReviewTool, CitePaperTool, PolishTextTool,
    SaveCardTool, SearchCardsTool,
    RecentPapersTool, SearchPapersTool,
)
from app.services.chat.session_service import get_or_create_session, auto_title, get_paper_by_id
from app.services.chat.message_service import (
    save_message, get_paper_text_preview,
)
from app.handlers.analyze_handler import handle_analyze, handle_deep_analyze
from app.handlers.rag_handler import handle_rag_chat
from app.handlers.cross_doc_handler import handle_cross_doc_chat
from app.handlers.ws_utils import ChunkBuffer
from app.services.agent.react_agent import react_agent
from app.services.agent.coordinator import ResearchCoordinator
from app.services.chat.context_service import context_service
from app.services.security.security_service import security_service
from app.services.security.clarification_service import clarification_service
from app.services.user.profile_service import profile_service
from app.prompts.chat import GENERAL_CHAT_SYSTEM_PROMPT, THINKING_PROMPT

logger = logging.getLogger(__name__)

# 深度研究模式触发关键词
DEEP_RESEARCH_KEYWORDS = [
    "跨论文", "多篇论文", "对比分析", "方法演进",
    "研究方向", "研究空白", "矛盾", "一致性",
    "深度研究", "深入分析",
]

# 跨论文推理工具（意图识别命中这些工具时自动触发深度研究模式）
CROSS_PAPER_TOOLS = {
    "detect_contradiction", "trace_evolution",
    "verify_consistency", "find_research_gaps",
    "cross_paper_reason",
}


def _is_multi_agent_research(intent: str, message: str) -> bool:
    """判断是否需要多 Agent 研究模式

    触发条件（满足任一）：
    1. 意图为 literature_review 或 deep_analysis
    2. 消息中包含综合研究类关键词
    3. 消息长度 > 50 且包含多个问号（复合问题）
    """
    multi_agent_keywords = ["综合研究", "系统分析", "全面调研", "深入研究", "多角度", "全方位"]

    # 条件1：特定意图
    if intent in ("literature_review", "deep_analysis"):
        return True

    # 条件2：关键词匹配
    for kw in multi_agent_keywords:
        if kw in message:
            return True

    # 条件3：复合问题（长消息含多个问号）
    if len(message) > 50 and message.count("？") + message.count("?") >= 2:
        return True

    return False


def _is_deep_research_request(message: str, intent_result: dict) -> bool:
    """判断是否应路由到深度研究模式

    满足以下任一条件即触发：
    1. 用户消息包含深度研究关键词
    2. 意图识别结果中的工具为跨论文推理工具
    """
    # 检查关键词
    for keyword in DEEP_RESEARCH_KEYWORDS:
        if keyword in message:
            return True

    # 检查意图识别工具是否为跨论文工具
    if intent_result.get("matched"):
        tool = intent_result.get("tool", "")
        if tool in CROSS_PAPER_TOOLS:
            return True

    return False


# 工具单例（避免每次请求重复创建）
_literature_review_tool = LiteratureReviewTool()
_cite_paper_tool = CitePaperTool()
_polish_text_tool = PolishTextTool()
_save_card_tool = SaveCardTool()
_search_cards_tool = SearchCardsTool()
_recent_papers_tool = RecentPapersTool()
_search_papers_tool = SearchPapersTool()


async def _handle_react_agent(websocket, db, state, message, session_id, user_id,
                               paper_id, paper_ids, chat_history, thinking_mode="quick", mode="normal"):
    """使用 ReAct Agent 处理需要多步推理的请求

    Args:
        mode: "normal" 或 "deep_research"（深度研究模式，强制 max_iterations=8 并使用三阶段提示词）
    """
    from app.services.agent.agent_service import ToolContext

    session = await get_or_create_session(db, session_id, user_id, paper_id=paper_id)

    # 保存用户消息
    await save_message(db, session.id, "user", message)

    # 深度研究模式：如果未提供 paper_ids，从 session 关联论文中获取
    effective_paper_ids = list(paper_ids or [])
    if mode == "deep_research" and not effective_paper_ids:
        effective_paper_ids = session.get_related_paper_ids()
        if not effective_paper_ids and paper_id:
            effective_paper_ids = [paper_id]

    # 构建工具上下文
    ctx = ToolContext(
        db=db,
        paper_id=paper_id,
        paper_ids=effective_paper_ids,
        user_id=user_id,
        session_id=session.id
    )

    full_response = ""
    agent_steps = []

    # 运行 ReAct Agent 循环
    async for event in react_agent.run(
        query=message,
        ctx=ctx,
        chat_history=chat_history,
        thinking_mode=thinking_mode,
        mode=mode
    ):
        event_type = event["type"]

        if event_type == "agent_thought":
            await websocket.send_text(json.dumps({
                "type": "agent_thought",
                "step": event["step"],
                "content": event["content"]
            }))
            agent_steps.append(event)

        elif event_type == "agent_action":
            # 安全检查工具权限
            tool_check = security_service.check_tool_permission(event["tool"], message)
            if not tool_check.is_safe:
                await websocket.send_text(json.dumps({
                    "type": "agent_observation",
                    "step": event["step"],
                    "content": f"工具 {event['tool']} 被安全策略拒绝"
                }))
                continue

            await websocket.send_text(json.dumps({
                "type": "agent_action",
                "step": event["step"],
                "tool": event["tool"],
                "input": event["input"]
            }))
            agent_steps.append(event)

        elif event_type == "agent_observation":
            await websocket.send_text(json.dumps({
                "type": "agent_observation",
                "step": event["step"],
                "content": event["content"]
            }))
            agent_steps.append(event)

        elif event_type == "agent_reflection":
            await websocket.send_text(json.dumps({
                "type": "agent_reflection",
                "content": event["content"]
            }))

        elif event_type == "agent_final":
            full_response = event["content"]
            # 先通知前端 Agent 推理结束（触发 agentSteps 持久化）
            await websocket.send_text(json.dumps({
                "type": "agent_final",
                "content": ""
            }))
            # 流式发送最终回答
            chunk_buffer = ChunkBuffer(websocket, interval_ms=50)
            try:
                # 分块发送（模拟打字机效果）
                chunk_size = 20
                for i in range(0, len(full_response), chunk_size):
                    chunk = full_response[i:i+chunk_size]
                    await chunk_buffer.add(chunk, "rag_chat_chunk")
                await chunk_buffer.flush("rag_chat_chunk")
            finally:
                chunk_buffer.close()
            # Agent 完成：发送 agent_chat channel 的 done 事件
            await websocket.send_text(json.dumps({
                "type": "done",
                "channel": "agent_chat",
                "session_id": session.id
            }))

    # 保存 AI 回复
    await save_message(db, session.id, "assistant", full_response)

    # 更新标题
    await auto_title(db, session, message)

    # 发送完成标记
    await websocket.send_text(json.dumps({
        "type": "done",
        "channel": "rag_chat",
        "session_id": session.id
    }))


async def _handle_simple_tool(websocket, db, state, tool_name, message, session_id, user_id,
                               paper_id, paper_ids, thinking_mode="quick", chat_history=""):
    """直通单步工具调用（用于阅读辅助等简单场景，避免 ReAct 开销）"""
    from app.services.agent.agent_service import (
        ToolContext, ExplainTermTool, SummarizeTool, TranslateTool
    )

    _tools = {
        "explain_term": ExplainTermTool(),
        "summarize": SummarizeTool(),
        "translate": TranslateTool(),
    }

    tool_instance = _tools.get(tool_name)
    if not tool_instance:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"未知工具: {tool_name}"
        }))
        return

    session = await get_or_create_session(db, session_id, user_id, paper_id=paper_id)
    await save_message(db, session.id, "user", message)

    ctx = ToolContext(
        db=db,
        paper_id=paper_id,
        paper_ids=paper_ids or [],
        user_id=user_id,
        session_id=session.id
    )

    try:
        # 思考过程（如果是深度模式）
        paper_text = ""
        if paper_id:
            paper_text = await get_paper_text_preview(db, paper_id) or ""
        await _run_thinking(websocket, message, paper_text=paper_text, thinking_mode=thinking_mode)

        # 构建参数
        if tool_name == "explain_term":
            result = await tool_instance.execute(ctx, term=message, context=paper_text[:2000])
            response_text = result.data.get("explanation", "")
        elif tool_name == "summarize":
            result = await tool_instance.execute(ctx, text=message)
            response_text = result.data.get("summary") or result.data.get("full_summary", "")
        elif tool_name == "translate":
            result = await tool_instance.execute(ctx, text=message)
            response_text = result.data.get("translation", "")
        else:
            response_text = "工具执行完成"

        # 流式发送结果
        chunk_buffer = ChunkBuffer(websocket, interval_ms=50)
        try:
            chunk_size = 20
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i+chunk_size]
                await chunk_buffer.add(chunk, "rag_chat_chunk")
            await chunk_buffer.flush("rag_chat_chunk")
        finally:
            chunk_buffer.close()

        await save_message(db, session.id, "assistant", response_text)
        await auto_title(db, session, message)

        await websocket.send_text(json.dumps({
            "type": "done",
            "channel": "rag_chat",
            "session_id": session.id
        }))

    except Exception as e:
        logger.error(f"简单工具 {tool_name} 执行失败: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"工具调用失败: {str(e)}"
        }))


async def _run_thinking(websocket, message, paper_text="", thinking_mode="quick"):
    """在深度思考模式下，先执行思考过程并流式发送 thinking_chunk

    thinking_mode="quick" 时直接返回，不执行任何操作；
    thinking_mode="deep" 时调用 LLM 生成思考过程并流式发送。
    思考过程失败不影响后续回答（catch 后 log warning 继续执行）。
    """
    if thinking_mode != "deep":
        return

    context = f"论文上下文：{paper_text[:500]}..." if paper_text else "当前没有选中论文"
    prompt = THINKING_PROMPT.format(message=message, context=context)

    messages = [HumanMessage(content=prompt)]

    chunk_buffer = ChunkBuffer(websocket, interval_ms=50)
    try:
        async for chunk in llm_service.llm.astream(messages):
            if chunk.content:
                await chunk_buffer.add(chunk.content, "thinking_chunk")
        await chunk_buffer.flush("thinking_chunk")
    except Exception as e:
        logger.warning(f"深度思考过程失败（非阻塞）: {e}")
    finally:
        chunk_buffer.close()

    # 发送思考完成标记
    await websocket.send_text(json.dumps({"type": "thinking_done"}))


async def _handle_general_chat(websocket, db, state, message, session_id, user_id, thinking_mode="quick", chat_history=""):
    """处理无论文的通用对话（闲聊、通用知识问答等）

    直接调用 LLM 进行对话，不使用 RAG 检索。
    相比 RAG 问答省去向量检索 + BM25 约 500ms 开销，响应更快。
    """
    try:
        # 1. 获取或创建会话（paper_id=None）
        session = await get_or_create_session(db, session_id, user_id, paper_id=None)
        state.current_session_id = session.id

        # 2. 保存用户消息
        await save_message(db, session.id, "user", message)

        # 2.5 深度思考模式：在回答前先展示思考过程
        await _run_thinking(websocket, message, paper_text="", thinking_mode=thinking_mode)

        # 3. 构建消息并流式调用 LLM
        # 构建系统 prompt，加入指代消解指令
        system_prompt = GENERAL_CHAT_SYSTEM_PROMPT
        if chat_history:
            context_instruction = context_service.build_context_instruction()
            system_prompt = f"{system_prompt}\n\n{context_instruction}"

        # 构建用户消息，加入对话历史
        user_content = message
        if chat_history:
            user_content = f"{chat_history}\n\n当前问题：{message}"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]

        chunk_buffer = ChunkBuffer(websocket, interval_ms=50)
        full_response = ""
        try:
            async for chunk in llm_service.llm.astream(messages):
                if chunk.content:
                    full_response += chunk.content
                    await chunk_buffer.add(chunk.content, "rag_chat_chunk")
            await chunk_buffer.flush("rag_chat_chunk")
        finally:
            chunk_buffer.close()

        # 4. 保存 AI 回复
        await save_message(db, session.id, "assistant", full_response)

        # 5. 更新会话标题
        await auto_title(db, session, message)

        # 6. 发送完成信号
        await websocket.send_text(json.dumps({
            "type": "done",
            "channel": "rag_chat",
            "session_id": session.id
        }))

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"通用对话处理失败: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"对话失败: {str(e)}"
        }))


def _format_tool_result_text(tool: str, result) -> str:
    """将 ToolResult 转为用户可读的文本，用于 rag_chat_chunk 发送"""
    if not result.success:
        return f"工具调用失败: {result.error}"

    data = result.data

    if tool == "literature_review":
        return data.get("review", "文献综述生成完成")
    elif tool == "cite_paper":
        return data.get("citation", "引用格式化完成")
    elif tool == "polish_text":
        original = data.get("original_text", "")
        polished = data.get("polished_text", "")
        if polished:
            return f"**原文：**\n{original}\n\n**润色后：**\n{polished}"
        return "文本润色完成"
    elif tool == "save_card":
        return f"✅ {data.get('message', '知识卡片已保存')}\n标题: {data.get('title', '')}"
    elif tool == "search_cards":
        cards = data.get("cards", [])
        if not cards:
            return "未找到匹配的知识卡片"
        lines = [f"找到 {len(cards)} 张知识卡片：\n"]
        for i, card in enumerate(cards, 1):
            title = card.get("title", "无标题")
            summary = card.get("summary", card.get("content", ""))[:100]
            lines.append(f"{i}. **{title}**\n   {summary}")
        return "\n".join(lines)
    elif tool == "recent_papers":
        papers = data.get("papers", [])
        if not papers:
            return "暂无论文记录"
        lines = [f"最近 {len(papers)} 篇论文：\n"]
        for i, p in enumerate(papers, 1):
            title = p.get("title", "无标题")
            authors = p.get("authors", "")
            lines.append(f"{i}. **{title}** {f'({authors})' if authors else ''}")
        return "\n".join(lines)
    elif tool == "search_papers":
        papers = data.get("papers", [])
        query = data.get("query", "")
        if not papers:
            return f"未找到与「{query}」相关的论文"
        lines = [f"找到 {len(papers)} 篇与「{query}」相关的论文：\n"]
        for i, p in enumerate(papers, 1):
            title = p.get("title", "无标题")
            authors = p.get("authors", "")
            abstract = p.get("abstract", "")[:100]
            lines.append(f"{i}. **{title}** {f'({authors})' if authors else ''}")
            if abstract:
                lines.append(f"   {abstract}")
        return "\n".join(lines)
    else:
        return json.dumps(data, ensure_ascii=False)[:2000]


async def _handle_writing_tool(websocket, db, state, tool_name, tool_instance, ctx, message, session_id, user_id, paper_id, paper_text="", thinking_mode="quick"):
    """处理写作类工具（literature_review, cite_paper, polish_text）

    流程：
    1. 执行工具
    2. 以 rag_chat_chunk 发送结果文本
    3. 发送 tool_result 结构化数据
    4. 保存消息到数据库
    5. 发送 done
    """
    try:
        session = await get_or_create_session(db, session_id, user_id, paper_id)
        state.current_session_id = session.id

        # 保存用户消息
        await save_message(db, session.id, "user", message)

        # 深度思考模式：在工具执行前先展示思考过程
        await _run_thinking(websocket, message, paper_text=paper_text, thinking_mode=thinking_mode)

        # 执行工具
        if tool_name == "literature_review":
            result = await tool_instance.execute(ctx, topic=message, paper_text=paper_text)
        elif tool_name == "cite_paper":
            result = await tool_instance.execute(ctx, format="apa")
        elif tool_name == "polish_text":
            result = await tool_instance.execute(ctx, text=message, polish_type="academic")
        else:
            result = ToolResult(success=False, error=f"未知写作工具: {tool_name}")

        # 将结果转为文本，通过 rag_chat_chunk 分块发送
        result_text = _format_tool_result_text(tool_name, result)

        chunk_buffer = ChunkBuffer(websocket, interval_ms=50)
        full_response = ""
        try:
            # 按段落分块发送，复用前端 rag_chat_chunk 处理逻辑
            chunk_size = 20
            for i in range(0, len(result_text), chunk_size):
                chunk = result_text[i:i + chunk_size]
                full_response += chunk
                await chunk_buffer.add(chunk, "rag_chat_chunk")
            await chunk_buffer.flush("rag_chat_chunk")
        finally:
            chunk_buffer.close()

        # 发送 tool_result 结构化数据（供前端富文本渲染）
        tool_result_msg = {
            "type": "tool_result",
            "tool": tool_name,
            "result_type": result.data.get("type", "writing") if result.success else "error",
            "content": result.data if result.success else {"error": result.error},
            "session_id": session.id,
        }
        await websocket.send_text(json.dumps(tool_result_msg))

        # 保存 AI 回复到数据库
        await save_message(db, session.id, "assistant", full_response)

        # 更新会话标题
        await auto_title(db, session, message)

        # 发送 done
        await websocket.send_text(json.dumps({
            "type": "done",
            "channel": "rag_chat",
            "session_id": session.id
        }))

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"写作工具 {tool_name} 执行失败: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"工具调用失败: {str(e)}"
        }))


async def _handle_knowledge_tool(websocket, db, state, tool_name, tool_instance, ctx, message, session_id, user_id, paper_id, thinking_mode="quick"):
    """处理知识库工具（save_card, search_cards）

    流程：
    1. 执行工具
    2. 以 rag_chat_chunk 发送结果文本
    3. 发送 tool_result 结构化数据
    4. 保存消息到数据库
    5. 发送 done
    """
    try:
        session = await get_or_create_session(db, session_id, user_id, paper_id)
        state.current_session_id = session.id

        # 保存用户消息
        await save_message(db, session.id, "user", message)

        # 深度思考模式：在工具执行前先展示思考过程
        await _run_thinking(websocket, message, thinking_mode=thinking_mode)

        # 执行工具
        if tool_name == "save_card":
            result = await tool_instance.execute(ctx, content=message, title="")
        elif tool_name == "search_cards":
            result = await tool_instance.execute(ctx, query=message)
        else:
            result = ToolResult(success=False, error=f"未知知识库工具: {tool_name}")

        # 将结果转为文本
        result_text = _format_tool_result_text(tool_name, result)

        chunk_buffer = ChunkBuffer(websocket, interval_ms=50)
        full_response = ""
        try:
            chunk_size = 20
            for i in range(0, len(result_text), chunk_size):
                chunk = result_text[i:i + chunk_size]
                full_response += chunk
                await chunk_buffer.add(chunk, "rag_chat_chunk")
            await chunk_buffer.flush("rag_chat_chunk")
        finally:
            chunk_buffer.close()

        # 发送 tool_result 结构化数据
        tool_result_msg = {
            "type": "tool_result",
            "tool": tool_name,
            "result_type": result.data.get("type", "knowledge") if result.success else "error",
            "content": result.data if result.success else {"error": result.error},
            "session_id": session.id,
        }
        await websocket.send_text(json.dumps(tool_result_msg))

        # 保存 AI 回复到数据库
        await save_message(db, session.id, "assistant", full_response)

        # 更新会话标题
        await auto_title(db, session, message)

        # 发送 done
        await websocket.send_text(json.dumps({
            "type": "done",
            "channel": "rag_chat",
            "session_id": session.id
        }))

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"知识库工具 {tool_name} 执行失败: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"工具调用失败: {str(e)}"
        }))


async def _handle_paper_query_tool(websocket, db, state, tool_name, tool_instance, ctx, message, session_id, user_id, paper_id, thinking_mode="quick"):
    """处理论文查询工具（recent_papers, search_papers）

    流程：
    1. 执行工具
    2. 以 rag_chat_chunk 发送结果文本
    3. 发送 tool_result 结构化数据
    4. 保存消息到数据库
    5. 发送 done
    """
    try:
        session = await get_or_create_session(db, session_id, user_id, paper_id)
        state.current_session_id = session.id

        # 保存用户消息
        await save_message(db, session.id, "user", message)

        # 深度思考模式：在工具执行前先展示思考过程
        await _run_thinking(websocket, message, thinking_mode=thinking_mode)

        # 执行工具
        if tool_name == "recent_papers":
            result = await tool_instance.execute(ctx, limit=10)
        elif tool_name == "search_papers":
            result = await tool_instance.execute(ctx, query=message)
        else:
            result = ToolResult(success=False, error=f"未知论文查询工具: {tool_name}")

        # 将结果转为文本
        result_text = _format_tool_result_text(tool_name, result)

        chunk_buffer = ChunkBuffer(websocket, interval_ms=50)
        full_response = ""
        try:
            chunk_size = 20
            for i in range(0, len(result_text), chunk_size):
                chunk = result_text[i:i + chunk_size]
                full_response += chunk
                await chunk_buffer.add(chunk, "rag_chat_chunk")
            await chunk_buffer.flush("rag_chat_chunk")
        finally:
            chunk_buffer.close()

        # 发送 tool_result 结构化数据
        tool_result_msg = {
            "type": "tool_result",
            "tool": tool_name,
            "result_type": result.data.get("type", "papers") if result.success else "error",
            "content": result.data if result.success else {"error": result.error},
            "session_id": session.id,
        }
        await websocket.send_text(json.dumps(tool_result_msg))

        # 保存 AI 回复到数据库
        await save_message(db, session.id, "assistant", full_response)

        # 更新会话标题
        await auto_title(db, session, message)

        # 发送 done
        await websocket.send_text(json.dumps({
            "type": "done",
            "channel": "rag_chat",
            "session_id": session.id
        }))

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"论文查询工具 {tool_name} 执行失败: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"工具调用失败: {str(e)}"
        }))


async def _handle_multi_agent_research(
    websocket, db, state, message,
    paper_id, paper_ids, chat_history, session, thinking_mode="quick"
):
    """多 Agent 研究模式处理

    流程：
    1. 构建工具上下文
    2. 创建 ResearchCoordinator
    3. 遍历 coordinator.run() 事件流并转发到 WebSocket
    4. agent_final 时保存消息到数据库并发送 done

    性能说明：完整流程约 8-25s（比单 ReAct 深度模式多 30-60% 开销）。
    多角色协同可获得更深入、结构化的研究报告，适合复杂综合性问题。
    """
    from app.services.agent.agent_service import ToolContext

    # 保存用户消息
    await save_message(db, session.id, "user", message)

    # 构建工具上下文
    effective_paper_ids = list(paper_ids or [])
    if not effective_paper_ids:
        effective_paper_ids = session.get_related_paper_ids() if hasattr(session, 'get_related_paper_ids') else []
        if not effective_paper_ids and paper_id:
            effective_paper_ids = [paper_id]

    ctx = ToolContext(
        db=db,
        paper_id=paper_id,
        paper_ids=effective_paper_ids,
        user_id=session.user_id if hasattr(session, 'user_id') else None,
        session_id=session.id,
    )

    # 创建协调器
    coordinator = ResearchCoordinator(
        react_agent=react_agent,
        llm_service=llm_service,
        ctx=ctx,
    )

    full_response = ""

    try:
        async for event in coordinator.run(query=message, chat_history=chat_history):
            event_type = event.get("type", "")
            sub_agent = event.get("sub_agent", "orchestrator")

            if event_type == "agent_thought":
                await websocket.send_text(json.dumps({
                    "type": "agent_thought",
                    "step": event.get("step", 0),
                    "content": event.get("content", ""),
                    "sub_agent": sub_agent,
                }))

            elif event_type == "agent_action":
                await websocket.send_text(json.dumps({
                    "type": "agent_action",
                    "step": event.get("step", 0),
                    "tool": event.get("tool", ""),
                    "input": event.get("input", {}),
                    "sub_agent": sub_agent,
                }))

            elif event_type == "agent_observation":
                await websocket.send_text(json.dumps({
                    "type": "agent_observation",
                    "step": event.get("step", 0),
                    "content": event.get("content", ""),
                    "sub_agent": sub_agent,
                }))

            elif event_type == "agent_reflection":
                await websocket.send_text(json.dumps({
                    "type": "agent_reflection",
                    "content": event.get("content", ""),
                    "sub_agent": sub_agent,
                }))

            elif event_type == "agent_final":
                full_response = event.get("content", "")
                # 通知前端 Agent 推理结束
                await websocket.send_text(json.dumps({
                    "type": "agent_final",
                    "content": "",
                    "sub_agent": sub_agent,
                }))
                # 流式发送最终回答（打字机效果）
                chunk_buffer = ChunkBuffer(websocket, interval_ms=50)
                try:
                    chunk_size = 20
                    for i in range(0, len(full_response), chunk_size):
                        chunk = full_response[i:i + chunk_size]
                        await chunk_buffer.add(chunk, "rag_chat_chunk")
                    await chunk_buffer.flush("rag_chat_chunk")
                finally:
                    chunk_buffer.close()
                # 发送 agent_chat channel done
                await websocket.send_text(json.dumps({
                    "type": "done",
                    "channel": "agent_chat",
                    "session_id": session.id,
                }))

    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"多 Agent 研究模式执行失败: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"多 Agent 研究失败: {str(e)}",
        }))
        return

    # 保存 AI 回复
    await save_message(db, session.id, "assistant", full_response)

    # 更新标题
    await auto_title(db, session, message)

    # 发送完成标记
    await websocket.send_text(json.dumps({
        "type": "done",
        "channel": "rag_chat",
        "session_id": session.id,
    }))


async def handle_unified_chat(websocket, state, message, paper_id, paper_ids, session_id, user_id, enable_search, forced_tool=None, thinking_mode="quick", task_key="unified", message_data=None):
    """统一聊天入口 - 根据意图自动路由到不同功能

    流程：
    1. 如果有 forced_tool，直接使用
    2. 否则先尝试 LLM 意图识别，失败则 fallback 关键词匹配
    3. 发送 intent_detected
    4. 根据意图路由到对应处理器
    5. 默认 fallback 到 RAG 问答
    """
    intent_result = None  # 用于 finally 块中的画像更新
    try:
        # === 检查是否为澄清回复 ===
        if message_data and message_data.get('type') == 'clarification_response':
            original_query = message_data.get('original_query', '')
            user_response = message_data.get('response', '')
            selected_options = message_data.get('selected_options', [])
            # 合并澄清结果
            query = clarification_service.merge_clarification(original_query, user_response, selected_options)
            message = query  # 使用合并后的查询继续正常处理流程

        # === 检查是否为确认回复 ===
        if message_data and message_data.get('type') == 'confirmation_response':
            action = message_data.get('action', '')
            confirmed = message_data.get('confirmed', False)
            if not confirmed:
                await websocket.send_json({'type': 'info', 'content': '操作已取消'})
                return
            # 已确认，继续执行原始操作
            message = message_data.get('original_query', message)

        # === 安全检查 ===
        security_result = security_service.check_input(message)
        if not security_result.is_safe:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"输入内容包含不安全的模式，请修改后重试。"
            }))
            return
        # 使用清洗后的输入
        message = security_result.sanitized_input or message

        # === 获取对话历史（用于指代消解） ===
        chat_history = ""
        try:
            async with AsyncSessionLocal() as db:
                history = await context_service.get_recent_context(session_id, db)
                chat_history = context_service.format_history_for_prompt(history)
        except Exception as e:
            logger.warning(f"获取对话历史失败: {e}")

        # 1. 意图识别
        if forced_tool:
            intent_result = {
                "matched": True,
                "intent": forced_tool,
                "tool": forced_tool,
                "confidence": "forced"
            }
        else:
            # 先尝试 LLM 识别，失败则 fallback 关键词
            try:
                intent_result = await classify_by_llm(message)
            except Exception:
                intent_result = classify_by_keywords(message)

        # 2. 发送意图识别结果给前端
        await websocket.send_text(json.dumps({
            "type": "intent_detected",
            "intent": intent_result.get("intent", "simple_qa") if intent_result.get("matched") else "simple_qa",
            "tool": intent_result.get("tool", "rag_chat") if intent_result.get("matched") else "rag_chat",
            "confidence": intent_result.get("confidence", "low"),
            "matched": intent_result.get("matched", False)
        }))

        # 2.3 主动澄清检查：意图模糊或缺少必要参数时，主动提问
        if intent_result.get("matched"):
            intent_tool = intent_result.get("tool", "")
            clarity_context = {
                "paper_id": paper_id,
                "paper_ids": paper_ids or [],
                "session_id": session_id,
            }
            clarity_result = clarification_service.check_clarity(message, intent_tool, clarity_context)
            if clarity_result.needs_clarification:
                clarification_msg = clarification_service.generate_clarification_message(clarity_result)
                clarification_msg["original_query"] = message
                await websocket.send_json(clarification_msg)
                return  # 等待用户回复后重新进入

        # 2.4 人机协作确认检查：高风险操作需用户确认
        if intent_result.get("matched"):
            from app.services.security.confirmation_service import confirmation_service
            intent_tool = intent_result.get("tool", "")
            confirm_params = {"query": message, "action": intent_tool}
            confirmation_msg = confirmation_service.check_confirmation_needed(intent_tool, confirm_params)
            if confirmation_msg:
                confirmation_msg['original_query'] = message
                await websocket.send_json(confirmation_msg)
                return  # 等待用户确认

        # 2.5 深度研究模式检测：关键词或意图识别命中跨论文工具时，路由到深度研究
        if _is_deep_research_request(message, intent_result):
            logger.info(f"深度研究模式触发: message='{message[:50]}'")
            async with AsyncSessionLocal() as db:
                await _handle_react_agent(
                    websocket, db, state, message, session_id, user_id,
                    paper_id, paper_ids, chat_history, thinking_mode,
                    mode="deep_research"
                )
            return

        # 2.6 多 Agent 研究模式检测
        intent_str = intent_result.get("intent", "") if intent_result and intent_result.get("matched") else ""
        if _is_multi_agent_research(intent_str, message):
            logger.info(f"多 Agent 研究模式触发: message='{message[:50]}'")
            async with AsyncSessionLocal() as db:
                session = await get_or_create_session(db, session_id, user_id, paper_id=paper_id)
                await _handle_multi_agent_research(
                    websocket, db, state, message,
                    paper_id, paper_ids, chat_history, session, thinking_mode
                )
            return

        # 3. 根据意图路由
        if intent_result.get("matched"):
            tool = intent_result.get("tool")

            # === 分析类 ===
            if tool == "analyze_paper":
                if paper_id:
                    async with AsyncSessionLocal() as db:
                        paper = await get_paper_by_id(db, paper_id)
                        if paper:
                            paper_text = await get_paper_text_preview(db, paper_id)
                            if paper_text:
                                await _run_thinking(websocket, message, paper_text=paper_text, thinking_mode=thinking_mode)
                                await handle_analyze(websocket, state, paper_text, paper_id, task_key=task_key)
                            else:
                                await websocket.send_text(json.dumps({
                                    "type": "error",
                                    "message": "论文内容不存在，请先上传并解析论文"
                                }))
                        else:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": "论文不存在"
                            }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "该功能需要先选择一篇论文，请在上方选择论文后再试"
                    }))

            elif tool == "deep_analyze_paper":
                if paper_id:
                    async with AsyncSessionLocal() as db:
                        paper = await get_paper_by_id(db, paper_id)
                        if paper:
                            paper_text = await get_paper_text_preview(db, paper_id)
                            if paper_text:
                                await _run_thinking(websocket, message, paper_text=paper_text, thinking_mode=thinking_mode)
                                await handle_deep_analyze(websocket, state, paper_text, paper_id, task_key=task_key)
                            else:
                                await websocket.send_text(json.dumps({
                                    "type": "error",
                                    "message": "论文内容不存在，请先上传并解析论文"
                                }))
                        else:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": "论文不存在"
                            }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "该功能需要先选择一篇论文，请在上方选择论文后再试"
                    }))

            # === 跨文档问答 ===
            elif tool == "cross_doc_chat":
                if not paper_ids or len(paper_ids) == 0:
                    if paper_id:
                        paper_ids = [paper_id]
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "跨文档问答需要提供论文列表"
                        }))
                        return

                async with AsyncSessionLocal() as db:
                    await _run_thinking(websocket, message, thinking_mode=thinking_mode)
                    await handle_cross_doc_chat(websocket, db, state, message, paper_ids, session_id, user_id, task_key=task_key)

            # === 写作类工具 ===
            elif tool == "literature_review":
                paper_text = ""
                async with AsyncSessionLocal() as db:
                    if paper_id:
                        paper_text = await get_paper_text_preview(db, paper_id)
                    ctx = ToolContext(db=db, paper_id=paper_id, paper_ids=paper_ids, user_id=user_id, session_id=session_id)
                    await _handle_writing_tool(
                        websocket, db, state, "literature_review", _literature_review_tool,
                        ctx, message, session_id, user_id, paper_id, paper_text,
                        thinking_mode=thinking_mode
                    )

            elif tool == "cite_paper":
                async with AsyncSessionLocal() as db:
                    ctx = ToolContext(db=db, paper_id=paper_id, paper_ids=paper_ids, user_id=user_id, session_id=session_id)
                    await _handle_writing_tool(
                        websocket, db, state, "cite_paper", _cite_paper_tool,
                        ctx, message, session_id, user_id, paper_id,
                        thinking_mode=thinking_mode
                    )

            elif tool == "polish_text":
                async with AsyncSessionLocal() as db:
                    ctx = ToolContext(db=db, paper_id=paper_id, paper_ids=paper_ids, user_id=user_id, session_id=session_id)
                    await _handle_writing_tool(
                        websocket, db, state, "polish_text", _polish_text_tool,
                        ctx, message, session_id, user_id, paper_id,
                        thinking_mode=thinking_mode
                    )

            # === 知识库工具 ===
            elif tool == "save_card":
                async with AsyncSessionLocal() as db:
                    ctx = ToolContext(db=db, paper_id=paper_id, paper_ids=paper_ids, user_id=user_id, session_id=session_id)
                    await _handle_knowledge_tool(
                        websocket, db, state, "save_card", _save_card_tool,
                        ctx, message, session_id, user_id, paper_id,
                        thinking_mode=thinking_mode
                    )

            elif tool == "search_cards":
                async with AsyncSessionLocal() as db:
                    ctx = ToolContext(db=db, paper_id=paper_id, paper_ids=paper_ids, user_id=user_id, session_id=session_id)
                    await _handle_knowledge_tool(
                        websocket, db, state, "search_cards", _search_cards_tool,
                        ctx, message, session_id, user_id, paper_id,
                        thinking_mode=thinking_mode
                    )

            # === 论文查询工具 ===
            elif tool == "recent_papers":
                async with AsyncSessionLocal() as db:
                    ctx = ToolContext(db=db, paper_id=paper_id, paper_ids=paper_ids, user_id=user_id, session_id=session_id)
                    await _handle_paper_query_tool(
                        websocket, db, state, "recent_papers", _recent_papers_tool,
                        ctx, message, session_id, user_id, paper_id,
                        thinking_mode=thinking_mode
                    )

            elif tool == "search_papers":
                async with AsyncSessionLocal() as db:
                    ctx = ToolContext(db=db, paper_id=paper_id, paper_ids=paper_ids, user_id=user_id, session_id=session_id)
                    await _handle_paper_query_tool(
                        websocket, db, state, "search_papers", _search_papers_tool,
                        ctx, message, session_id, user_id, paper_id,
                        thinking_mode=thinking_mode
                    )

            # === RAG 问答（含 search_text） ===
            elif tool == "rag_chat" or tool == "search_text":
                if not paper_id:
                    # RAG 问答需要论文，无论文时降级为通用对话
                    async with AsyncSessionLocal() as db:
                        await _handle_general_chat(websocket, db, state, message, session_id, user_id, thinking_mode=thinking_mode, chat_history=chat_history)
                    return

                async with AsyncSessionLocal() as db:
                    paper_text = await get_paper_text_preview(db, paper_id) if paper_id else ""
                    await _run_thinking(websocket, message, paper_text=paper_text, thinking_mode=thinking_mode)
                    await handle_rag_chat(websocket, db, state, message, paper_id, session_id, user_id, enable_search, task_key=task_key)

            # === 基础工具直通（阅读辅助等场景） ===
            elif tool in ("explain_term", "summarize", "translate"):
                async with AsyncSessionLocal() as db:
                    await _handle_simple_tool(
                        websocket, db, state, tool, message, session_id, user_id,
                        paper_id, paper_ids, thinking_mode, chat_history
                    )
                return

            # === ReAct Agent 兜底（匹配了意图但没有专用 handler） ===
            else:
                async with AsyncSessionLocal() as db:
                    await _handle_react_agent(
                        websocket, db, state, message, session_id, user_id,
                        paper_id, paper_ids, chat_history, thinking_mode
                    )
                return

        else:
            # 没有匹配到特定意图，有论文走 RAG，无论文走通用对话
            _pid = paper_id or (paper_ids[0] if paper_ids else None)
            if _pid:
                async with AsyncSessionLocal() as db:
                    paper_text = await get_paper_text_preview(db, _pid) if _pid else ""
                    await _run_thinking(websocket, message, paper_text=paper_text, thinking_mode=thinking_mode)
                    await handle_rag_chat(websocket, db, state, message, _pid, session_id, user_id, enable_search, task_key=task_key)
            else:
                # 无论文时使用通用对话
                async with AsyncSessionLocal() as db:
                    await _handle_general_chat(websocket, db, state, message, session_id, user_id, thinking_mode=thinking_mode, chat_history=chat_history)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"统一聊天处理失败: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"处理失败: {str(e)}"
        }))
    finally:
        state.running_tasks.pop(task_key, None)
        # 异步更新用户画像（不阻塞响应）
        if intent_result:  # 确保意图识别已完成
            try:
                intent_tool = intent_result.get("tool", "rag_chat") if intent_result.get("matched") else "simple_qa"
                asyncio.create_task(profile_service.update_profile_async(
                    user_id=user_id,
                    interaction_data={
                        "message": message,
                        "intent": intent_tool,
                        "paper_id": paper_id,
                        "tool_used": intent_tool,
                    }
                ))
            except Exception as e:
                logger.warning(f"画像异步更新触发失败: {e}")
