"""记忆中间件

提供记忆上下文增强和对话后记忆提取功能
"""
import asyncio
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user.memory_service import memory_service

logger = logging.getLogger(__name__)


async def enrich_context_with_memory(
    user_id: int, 
    question: str, 
    db: AsyncSession
) -> str:
    """将记忆信息附加到问答上下文
    
    在问答前调用，召回相关记忆并格式化为上下文字符串
    
    Args:
        user_id: 用户ID
        question: 当前问题
        db: 数据库会话
        
    Returns:
        记忆上下文字符串，如果没有相关记忆则返回空字符串
    """
    try:
        memories = await memory_service.recall_memories(user_id, question, db, top_k=3)
        
        if not memories:
            return ""
        
        # 格式化记忆上下文
        memory_lines = []
        for mem in memories:
            type_label = {
                "research_interest": "研究兴趣",
                "preference": "用户偏好",
                "term_usage": "术语理解",
                "background": "背景信息"
            }.get(mem["type"], "其他")
            
            memory_lines.append(f"- [{type_label}] {mem['content']}")
        
        memory_context = "\n".join(memory_lines)
        
        return f"""

[用户画像参考]
基于用户历史对话，以下信息可能有助于回答：
{memory_context}
"""
    
    except Exception as e:
        logger.error("记忆上下文增强失败", exc_info=True)
        return ""


async def post_chat_memory_extraction(
    user_id: int, 
    question: str, 
    answer: str, 
    db: AsyncSession
):
    """对话后记忆提取（后台异步执行）
    
    在问答完成后调用，提取并存储新的记忆信息
    此操作是异步的，不会阻塞响应
    
    Args:
        user_id: 用户ID
        question: 用户问题
        answer: 助手回答
        db: 数据库会话
    """
    try:
        # 异步执行记忆提取，不等待结果
        asyncio.create_task(
            _extract_memory_async(user_id, question, answer, db)
        )
    except Exception as e:
        logger.error("启动记忆提取任务失败", exc_info=True)


async def _extract_memory_async(
    user_id: int, 
    question: str, 
    answer: str, 
    db: AsyncSession
):
    """异步执行记忆提取"""
    try:
        # 注意：这里需要创建新的数据库会话，因为原始会话可能已经关闭
        from app.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as new_db:
            await memory_service.extract_memory(user_id, question, answer, new_db)
            await new_db.commit()
    except Exception as e:
        logger.error("异步记忆提取失败", exc_info=True)


async def build_memory_aware_prompt(
    user_id: int,
    question: str,
    base_prompt: str,
    db: AsyncSession
) -> str:
    """构建带有记忆感知的提示词
    
    将记忆上下文与基础提示词结合
    
    Args:
        user_id: 用户ID
        question: 当前问题
        base_prompt: 基础系统提示词
        db: 数据库会话
        
    Returns:
        增强后的提示词
    """
    memory_context = await enrich_context_with_memory(user_id, question, db)
    
    if memory_context:
        return f"{base_prompt}\n{memory_context}\n\n请记住以上用户信息，在回答时予以考虑。"
    
    return base_prompt
