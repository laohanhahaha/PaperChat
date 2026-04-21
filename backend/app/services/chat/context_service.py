"""对话上下文服务 - 短期记忆与指代消解支持

提供最近 N 轮对话历史，注入到 LLM Prompt 中，
使 LLM 能理解 "它"、"这篇"、"上面的" 等指代。
"""
import logging
from typing import Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.chat import ChatMessage

logger = logging.getLogger(__name__)


class ContextService:
    """对话上下文管理"""
    
    DEFAULT_HISTORY_ROUNDS = 5  # 默认保留最近5轮对话
    MAX_CONTEXT_CHARS = 4000    # 上下文最大字符数，防止 token 溢出
    
    async def get_recent_context(
        self, 
        session_id: int, 
        db: AsyncSession = None, 
        max_rounds: int = None
    ) -> list[dict]:
        """获取最近 N 轮对话历史
        
        Args:
            session_id: 会话ID
            db: 数据库会话（AsyncSession）
            max_rounds: 最大轮数，默认使用 DEFAULT_HISTORY_ROUNDS
            
        Returns:
            [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
            按时间正序排列（最早的在前，最新的在后）
        """
        if db is None:
            logger.warning("get_recent_context called without db session")
            return []
        
        rounds = max_rounds or self.DEFAULT_HISTORY_ROUNDS
        # 每轮包含 user + assistant 两条消息，所以 limit = rounds * 2
        limit = rounds * 2
        
        try:
            # 查询最近的消息，按时间倒序（最新的在前）
            query = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(desc(ChatMessage.created_at))
                .limit(limit)
            )
            result = await db.execute(query)
            messages = result.scalars().all()
            
            # 转换为 dict 列表并反转顺序（最早的在前）
            history = [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at
                }
                for msg in reversed(messages)
            ]
            
            logger.debug(f"Retrieved {len(history)} messages for session {session_id}")
            return history
            
        except Exception as e:
            logger.error(f"Error fetching context for session {session_id}: {e}")
            return []
    
    def format_history_for_prompt(self, history: list[dict]) -> str:
        """将对话历史格式化为 Prompt 可用的文本
        
        Args:
            history: 对话历史列表，每个元素包含 role 和 content
            
        Returns:
            格式化后的文本，适合注入到 Prompt 中
        """
        if not history:
            return ""
        
        lines = ["[对话历史]"]
        total_chars = 0
        
        for msg in history:
            role_label = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")
            
            # 截断过长的单条消息
            if len(content) > 500:
                content = content[:500] + "..."
            
            line = f"{role_label}: {content}"
            total_chars += len(line)
            
            # 超过最大字符数限制时停止添加
            if total_chars > self.MAX_CONTEXT_CHARS:
                lines.append("...（历史记录已截断）")
                break
            
            lines.append(line)
        
        return "\n".join(lines)
    
    def build_context_instruction(self) -> str:
        """返回指代消解指令，注入到 system prompt
        
        Returns:
            指代消解指令文本
        """
        return (
            "请注意：以下对话可能包含指代词（如'它'、'这篇'、'上面的'、'刚才的'）或省略主语。"
            "请结合对话历史理解用户的真实意图，自动补全省略的对象。"
            "例如：如果用户先问了某篇论文的内容，然后说'翻译一下'，应理解为翻译该论文的相关内容。"
        )


# 全局实例
context_service = ContextService()
