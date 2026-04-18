"""反馈路由

提供用户对回答的反馈（点赞/点踩/文字反馈）接口
"""
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_

from app.database import get_db
from app.models.feedback import MessageFeedback
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.llm_service import llm_service
from app.services.memory_service import memory_service
from langchain_community.chat_message_histories import ChatMessageHistory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    """创建反馈请求模型"""
    message_id: int = Field(..., description="消息ID")
    rating: int = Field(..., description="评分：1=👍, -1=👎")
    comment: Optional[str] = Field(None, description="可选的文字反馈")


class FeedbackResponse(BaseModel):
    """反馈响应模型"""
    id: int
    message_id: int
    rating: int
    comment: Optional[str]
    created_at: str


class FeedbackStats(BaseModel):
    """反馈统计模型"""
    total_feedback: int
    positive_count: int
    negative_count: int
    positive_rate: float
    with_comment_count: int


@router.post("/", response_model=FeedbackResponse)
async def submit_feedback(
    req: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """提交反馈
    
    对聊天消息进行点赞/点踩，并可选择性地提供文字反馈
    """
    # 验证评分值
    if req.rating not in [1, -1]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="评分必须是 1（👍）或 -1（👎）"
        )
    
    # 验证消息是否存在且属于当前用户
    result = await db.execute(
        select(ChatMessage)
        .join(ChatSession)
        .where(
            and_(
                ChatMessage.id == req.message_id,
                ChatSession.user_id == current_user.id
            )
        )
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="消息不存在或无权限"
        )
    
    # 检查是否已提交过反馈
    existing_result = await db.execute(
        select(MessageFeedback).where(
            and_(
                MessageFeedback.message_id == req.message_id,
                MessageFeedback.user_id == current_user.id
            )
        )
    )
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        # 更新现有反馈
        existing.rating = req.rating
        existing.comment = req.comment
        await db.commit()
        await db.refresh(existing)
        feedback = existing
    else:
        # 创建新反馈
        feedback = MessageFeedback(
            message_id=req.message_id,
            user_id=current_user.id,
            rating=req.rating,
            comment=req.comment
        )
        db.add(feedback)
        await db.commit()
        await db.refresh(feedback)
    
    # 如果是差评，记录到记忆中（用于学习用户偏好）
    if req.rating == -1:
        try:
            await memory_service.store_memory(
                user_id=current_user.id,
                memory_type="feedback_pattern",
                content=f"用户对回答不满意: {message.content[:100]}...",
                db=db,
                importance=1.2
            )
        except Exception as e:
            logger.error("记录反馈模式失败", exc_info=True)
    
    return FeedbackResponse(
        id=feedback.id,
        message_id=feedback.message_id,
        rating=feedback.rating,
        comment=feedback.comment,
        created_at=feedback.created_at.isoformat() if feedback.created_at else None
    )


@router.get("/stats", response_model=FeedbackStats)
async def get_feedback_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取反馈统计
    
    返回当前用户的反馈统计数据：
    - 总反馈数
    - 好评数/差评数
    - 好评率
    - 带文字评论的反馈数
    """
    # 获取用户的所有反馈
    result = await db.execute(
        select(MessageFeedback).where(MessageFeedback.user_id == current_user.id)
    )
    feedbacks = result.scalars().all()
    
    total = len(feedbacks)
    positive = sum(1 for f in feedbacks if f.rating == 1)
    negative = sum(1 for f in feedbacks if f.rating == -1)
    with_comment = sum(1 for f in feedbacks if f.comment)
    
    positive_rate = positive / total * 100 if total > 0 else 0
    
    return FeedbackStats(
        total_feedback=total,
        positive_count=positive,
        negative_count=negative,
        positive_rate=round(positive_rate, 1),
        with_comment_count=with_comment
    )


@router.get("/message/{message_id}")
async def get_message_feedback(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定消息的反馈"""
    result = await db.execute(
        select(MessageFeedback).where(
            and_(
                MessageFeedback.message_id == message_id,
                MessageFeedback.user_id == current_user.id
            )
        )
    )
    feedback = result.scalar_one_or_none()
    
    if not feedback:
        return {"has_feedback": False}
    
    return {
        "has_feedback": True,
        "feedback": FeedbackResponse(
            id=feedback.id,
            message_id=feedback.message_id,
            rating=feedback.rating,
            comment=feedback.comment,
            created_at=feedback.created_at.isoformat() if feedback.created_at else None
        )
    }


@router.post("/regenerate/{message_id}")
async def regenerate_answer(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """负面反馈自动重跑
    
    获取原始问题和上下文，使用优化的提示词重新生成回答
    
    Returns:
        新生成的回答
    """
    # 1. 获取原始消息及其上下文
    result = await db.execute(
        select(ChatMessage, ChatSession)
        .join(ChatSession)
        .where(
            and_(
                ChatMessage.id == message_id,
                ChatSession.user_id == current_user.id,
                ChatMessage.role == "assistant"
            )
        )
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="消息不存在或无权限"
        )
    
    assistant_message, session = row
    
    # 2. 获取对应的问题消息（上一条）
    result = await db.execute(
        select(ChatMessage)
        .where(
            and_(
                ChatMessage.session_id == session.id,
                ChatMessage.role == "user",
                ChatMessage.created_at < assistant_message.created_at
            )
        )
        .order_by(desc(ChatMessage.created_at))
        .limit(1)
    )
    user_message = result.scalar_one_or_none()
    
    if not user_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无法找到对应的问题"
        )
    
    # 3. 获取历史对话上下文
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at)
    )
    all_messages = result.scalars().all()
    
    chat_history = ChatMessageHistory()
    for msg in all_messages:
        if msg.id < user_message.id:
            if msg.role == "user":
                chat_history.add_user_message(msg.content)
            else:
                chat_history.add_ai_message(msg.content)
    
    # 4. 使用优化的提示词重新生成
    try:
        # 获取相关记忆
        memory_context = ""
        try:
            memories = await memory_service.recall_memories(
                current_user.id, 
                user_message.content, 
                db, 
                top_k=3
            )
            if memories:
                memory_lines = [f"- {m['content']}" for m in memories]
                memory_context = "\n".join(memory_lines)
        except Exception as e:
            logger.warning(f"记忆召回失败: {e}")
        
        # 构建优化提示词
        optimized_prompt = f"""你是一个专业的学术论文问答助手。用户之前对回答不满意，请重新生成一个更准确、更详细的回答。

重要提示：
1. 请确保回答准确基于论文内容
2. 如果之前回答不够详细，请补充更多细节
3. 使用 [p.X] 格式标注引用来源页码
4. 回答请使用中文

{memory_context if memory_context else ""}
"""
        
        # 使用 RAG 重新生成回答
        from app.services.rag_service import rag_service
        
        relevant_chunks = await rag_service.search(
            session.paper_id, 
            user_message.content, 
            top_k=5
        )
        
        if not relevant_chunks:
            return {
                "success": False,
                "error": "无法检索到相关内容"
            }
        
        # 组装上下文
        context_parts = []
        for chunk in relevant_chunks:
            pages_str = ",".join(map(str, chunk['pages'])) if chunk['pages'] else "未知"
            context_parts.append(f"[来源: 第{pages_str}页]\n{chunk['text']}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        # 构建消息
        from langchain_core.messages import SystemMessage, HumanMessage
        
        system_content = f"{optimized_prompt}\n\n检索到的相关内容：\n{context}"
        messages = [SystemMessage(content=system_content)]
        messages.extend(chat_history.messages)
        messages.append(HumanMessage(content=user_message.content))
        
        # 生成新回答
        response = await llm_service.llm.ainvoke(messages)
        new_answer = response.content
        
        # 组装引用来源
        sources = [
            {
                "text": chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"],
                "pages": chunk["pages"],
                "score": chunk["score"]
            }
            for chunk in relevant_chunks
        ]
        
        return {
            "success": True,
            "original_question": user_message.content,
            "new_answer": new_answer,
            "sources": sources
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重新生成回答失败: {str(e)}"
        )


@router.get("/history")
async def get_feedback_history(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取反馈历史记录"""
    # 获取反馈列表
    result = await db.execute(
        select(MessageFeedback, ChatMessage)
        .join(ChatMessage)
        .where(MessageFeedback.user_id == current_user.id)
        .order_by(desc(MessageFeedback.created_at))
        .offset(offset)
        .limit(limit)
    )
    rows = result.all()
    
    feedbacks = []
    for feedback, message in rows:
        feedbacks.append({
            "id": feedback.id,
            "message_id": feedback.message_id,
            "rating": feedback.rating,
            "comment": feedback.comment,
            "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
            "message_preview": message.content[:100] + "..." if len(message.content) > 100 else message.content,
            "message_role": message.role
        })
    
    # 获取总数
    count_result = await db.execute(
        select(func.count()).where(MessageFeedback.user_id == current_user.id)
    )
    total = count_result.scalar()
    
    return {
        "feedbacks": feedbacks,
        "total": total,
        "limit": limit,
        "offset": offset
    }
