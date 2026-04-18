"""Agent 智能问答处理器

处理 Agent 模式的智能问答请求
"""
import json
import asyncio

from app.services.agent_service import agent_service
from app.routers.ws import ChunkBuffer


async def handle_agent_chat(websocket, db, state, message, paper_id, paper_ids, task_key="agent_chat"):
    """异步处理 Agent 智能问答

    Agent 模式：意图识别 -> 任务规划 -> 逐步执行 -> 结果聚合
    """
    try:
        # 1. 意图识别
        intent = await agent_service.classify_intent(message)
        await websocket.send_text(json.dumps({
            "type": "agent_intent",
            "intent": intent
        }))

        # 2. 任务规划
        context = {"paper_id": paper_id, "paper_ids": paper_ids}
        plan = await agent_service.plan_tasks(message, intent, context)
        await websocket.send_text(json.dumps({
            "type": "agent_plan",
            "plan": plan
        }))

        # 3. 逐步执行
        context["db"] = db
        context["original_question"] = message

        # 使用 ChunkBuffer 合并 agent_answer_chunk 消息
        chunk_buffer = ChunkBuffer(websocket, interval_ms=50)
        try:
            async for progress in agent_service.execute_plan(plan, context):
                if progress["type"] == "step_start":
                    # 状态消息立即发送
                    await websocket.send_text(json.dumps({
                        "type": "agent_step",
                        **progress
                    }))
                elif progress["type"] == "step_result":
                    # 状态消息立即发送
                    await websocket.send_text(json.dumps({
                        "type": "agent_step_result",
                        **progress
                    }))
                elif progress["type"] == "final_answer_chunk":
                    # 流式内容使用 buffer
                    await chunk_buffer.add(progress["content"], "agent_answer_chunk")
            # 确保发送所有剩余的 chunk
            await chunk_buffer.flush("agent_answer_chunk")
        finally:
            chunk_buffer.close()

        await websocket.send_text(json.dumps({
            "type": "done",
            "channel": "agent_chat"
        }))

    except asyncio.CancelledError:
        pass
    except Exception as e:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Agent 问答失败: {str(e)}"
        }))
    finally:
        state.running_tasks.pop(task_key, None)
