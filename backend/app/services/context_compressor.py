"""上下文压缩服务

三层上下文压缩机制，防止长对话超出 LLM 上下文窗口限制。

L1 - 消息剪枝（同步，零成本）：删除冗余消息，截断过老的轮次
L2 - 摘要压缩（异步，1次 LLM 调用）：将最早的消息压缩为摘要
L3 - 后台预压缩（异步，会话结束后触发）：异步缓存压缩结果

性能影响说明：
- L1 剪枝：同步操作，无额外开销
- L2 摘要：额外 1 次 LLM 调用（约 1-3 秒），但可防止上下文溢出造成的完全失败
- L3 预压缩：后台异步执行，不影响当前请求延迟
"""
import asyncio
import logging
from typing import Optional

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)

# 压缩摘要系统提示词
_COMPRESS_SYSTEM_PROMPT = "你是一个对话历史摘要助手。请将以下对话历史压缩为简洁的摘要，保留所有重要信息、关键结论和上下文，供后续对话参考。"

_COMPRESS_USER_PROMPT = """请将以下对话历史压缩为简洁摘要（不超过500字），保留所有关键信息：

{history_text}

要求：
1. 保留用户提问的核心意图
2. 保留助手回答的关键结论和要点
3. 保留重要的术语、数据和引用
4. 使用第三人称描述对话内容
5. 输出格式：直接输出摘要文本，不需要额外标题"""


class ContextCompressor:
    """三层上下文压缩器

    负责在 LLM 调用前压缩消息列表，防止上下文窗口溢出。

    Attributes:
        llm_service: LLM 服务实例（用于 L2 摘要压缩）
        max_turns: 触发 L1 剪枝的轮次阈值（默认 20 轮）
        max_token_ratio: 触发 L2 压缩的 token 占比阈值（默认 0.6）
        context_window: 上下文窗口大小（默认 32000 tokens）
    """

    def __init__(self, llm_service=None):
        self.llm_service = llm_service
        self.max_turns = 20          # 超过此轮次触发 L1 剪枝
        self.max_token_ratio = 0.6   # 超过窗口 60% 触发 L2 压缩
        self.context_window = 32000  # DeepSeek 默认上下文窗口
        self._cache: dict = {}       # L3 后台预压缩缓存 {session_id: compressed_messages}

    # ------------------------------------------------------------------
    # Token 估算
    # ------------------------------------------------------------------

    def estimate_tokens(self, messages: list) -> int:
        """粗略估算消息列表的 token 数

        启发式规则（适合中英混合文本）：
        - 中文字符：约 1.5 字/token（1 汉字 ≈ 0.67 token）
        - 英文/数字：约 4 字符/token
        - 每条消息固定开销：约 4 tokens（role + 格式）

        Args:
            messages: LangChain 消息列表（BaseMessage 子类）

        Returns:
            估算的 token 总数
        """
        total = 0
        for msg in messages:
            content = msg.content if isinstance(msg, BaseMessage) else str(msg.get("content", ""))
            # 按字符分类估算
            chinese_chars = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
            other_chars = len(content) - chinese_chars
            tokens = int(chinese_chars / 1.5) + int(other_chars / 4)
            total += tokens + 4  # 每条消息固定 4 token 开销
        return total

    # ------------------------------------------------------------------
    # 压缩判断
    # ------------------------------------------------------------------

    def should_compress(self, messages: list) -> bool:
        """判断是否需要 L2 摘要压缩

        满足以下任一条件时返回 True：
        1. 非系统消息轮次 >= max_turns（默认 20 轮）
        2. 估算 token 数超过 context_window 的 max_token_ratio（默认 60%）

        Args:
            messages: 消息列表

        Returns:
            是否需要压缩
        """
        # 统计对话轮次（排除 system 消息）
        conversation_msgs = [
            m for m in messages
            if not (isinstance(m, SystemMessage) or
                    (isinstance(m, dict) and m.get("role") == "system"))
        ]
        turns = len(conversation_msgs) // 2  # 一轮 = user + assistant

        if turns >= self.max_turns:
            logger.debug(f"[Compressor] 轮次 {turns} >= {self.max_turns}，需要压缩")
            return True

        token_count = self.estimate_tokens(messages)
        threshold = int(self.context_window * self.max_token_ratio)
        if token_count >= threshold:
            logger.debug(f"[Compressor] Token {token_count} >= 阈值 {threshold}，需要压缩")
            return True

        return False

    # ------------------------------------------------------------------
    # L1: 消息剪枝（同步，零成本）
    # ------------------------------------------------------------------

    def prune(self, messages: list) -> list:
        """L1 消息剪枝（同步，零额外开销）

        执行以下操作：
        1. 提取并保留第一条 system 消息（不参与压缩）
        2. 删除连续重复的 system 消息
        3. 超过 max_turns * 2 + 1 条消息时，截断最早的对话轮次
           （始终保留 system 消息和最近 min(6, max_turns) 轮）

        Args:
            messages: 原始消息列表

        Returns:
            剪枝后的消息列表
        """
        if not messages:
            return messages

        # 1. 分离 system 消息和对话消息
        system_msgs = []
        conv_msgs = []

        for msg in messages:
            role = msg.type if isinstance(msg, BaseMessage) else msg.get("role", "")
            if role == "system":
                system_msgs.append(msg)
            else:
                conv_msgs.append(msg)

        # 去重：只保留第一条 system 消息（后续 system 消息通常是重复的论文上下文）
        unique_system = [system_msgs[0]] if system_msgs else []

        # 2. 截断过老的对话（保留最近 N 轮）
        keep_turns = min(self.max_turns, 12)  # 最多保留 12 轮完整历史
        max_conv_msgs = keep_turns * 2  # 每轮 = user + assistant

        if len(conv_msgs) > max_conv_msgs:
            # 从最早消息截断，保留最近的
            conv_msgs = conv_msgs[-max_conv_msgs:]
            logger.debug(f"[Compressor L1] 截断历史，保留最近 {keep_turns} 轮对话")

        return unique_system + conv_msgs

    # ------------------------------------------------------------------
    # L2: 摘要压缩（异步，1次 LLM 调用）
    # ------------------------------------------------------------------

    async def compress(self, messages: list) -> list:
        """L2 摘要压缩（需要 1 次 LLM 调用）

        将最早 50% 的对话消息压缩为 1 条摘要 system 消息，
        保留最近 4-6 条消息保证上下文连贯性。

        压缩后格式：
        [原始 system 消息] + [Compressed Summary 摘要] + [最近消息]

        Args:
            messages: 消息列表（通常已经过 L1 剪枝）

        Returns:
            压缩后的消息列表
        """
        if not self.llm_service:
            logger.warning("[Compressor L2] llm_service 未设置，跳过摘要压缩")
            return messages

        # 1. 分离 system 消息和对话消息
        system_msgs = []
        conv_msgs = []

        for msg in messages:
            role = msg.type if isinstance(msg, BaseMessage) else msg.get("role", "")
            if role == "system":
                system_msgs.append(msg)
            else:
                conv_msgs.append(msg)

        # 保留最近的消息数（保证上下文连贯）
        keep_recent = 6  # 最近 3 轮（6 条）完整保留

        if len(conv_msgs) <= keep_recent:
            # 消息数量不足，无需压缩
            return messages

        # 2. 分割：前半部分（待压缩）和最近部分（保留）
        to_compress = conv_msgs[:-keep_recent]
        recent_msgs = conv_msgs[-keep_recent:]

        # 3. 构建压缩请求文本
        history_lines = []
        for msg in to_compress:
            if isinstance(msg, BaseMessage):
                role_name = "用户" if msg.type == "human" else "助手"
                history_lines.append(f"{role_name}: {msg.content}")
            else:
                role = msg.get("role", "unknown")
                role_name = "用户" if role == "user" else "助手"
                history_lines.append(f"{role_name}: {msg.get('content', '')}")

        history_text = "\n\n".join(history_lines)

        # 4. 调用 LLM 生成摘要
        try:
            compress_messages = [
                SystemMessage(content=_COMPRESS_SYSTEM_PROMPT),
                HumanMessage(content=_COMPRESS_USER_PROMPT.format(history_text=history_text))
            ]
            summary = ""
            async for chunk in self.llm_service.llm.astream(compress_messages):
                if chunk.content:
                    summary += chunk.content

            logger.info(f"[Compressor L2] 压缩 {len(to_compress)} 条消息为摘要（{len(summary)} 字）")

            # 5. 构建摘要 system 消息
            summary_msg = SystemMessage(
                content=f"[Compressed Summary] 以下是之前对话的摘要，供参考：\n\n{summary}"
            )

            # 6. 返回：原始 system + 摘要 + 最近消息
            return system_msgs + [summary_msg] + recent_msgs

        except Exception as e:
            logger.error(f"[Compressor L2] 摘要压缩失败，回退到原始消息: {e}")
            return messages

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    async def process(self, messages: list) -> list:
        """主入口：自动应用 L1 剪枝 + 可选 L2 摘要压缩

        处理流程：
        1. 始终执行 L1 剪枝（同步，零成本）
        2. 如果剪枝后仍需压缩，执行 L2 摘要压缩（需要 llm_service）

        Args:
            messages: 原始消息列表

        Returns:
            压缩后的消息列表
        """
        if not messages:
            return messages

        original_count = len(messages)

        # Step 1: L1 剪枝（始终执行）
        pruned = self.prune(messages)

        pruned_count = len(pruned)
        if pruned_count < original_count:
            logger.debug(f"[Compressor L1] {original_count} -> {pruned_count} 条消息")

        # Step 2: L2 摘要压缩（仅当需要时执行）
        if self.should_compress(pruned) and self.llm_service:
            compressed = await self.compress(pruned)
            logger.info(f"[Compressor L2] {pruned_count} -> {len(compressed)} 条消息")
            return compressed

        return pruned

    # ------------------------------------------------------------------
    # L3: 后台预压缩（异步缓存）
    # ------------------------------------------------------------------

    async def background_precompress(self, session_id: str, messages: list) -> None:
        """L3 后台预压缩：在会话消息更新后异步缓存压缩结果

        下次该 session 的请求到来时，可直接使用缓存的压缩结果，
        避免实时 L2 压缩带来的延迟。

        Args:
            session_id: 会话 ID（作为缓存 key）
            messages: 当前消息列表
        """
        if not self.should_compress(messages):
            return
        try:
            compressed = await self.compress(messages)
            self._cache[str(session_id)] = compressed
            logger.debug(f"[Compressor L3] 会话 {session_id} 预压缩完成，缓存 {len(compressed)} 条消息")
        except Exception as e:
            logger.warning(f"[Compressor L3] 会话 {session_id} 预压缩失败: {e}")

    def get_cached(self, session_id: str) -> Optional[list]:
        """获取并消费预压缩缓存（pop 语义，取出即删除）

        Args:
            session_id: 会话 ID

        Returns:
            缓存的压缩消息列表，或 None（无缓存时）
        """
        return self._cache.pop(str(session_id), None)


# 全局实例（延迟绑定 llm_service，避免循环导入）
context_compressor = ContextCompressor()


def init_compressor(llm_service) -> None:
    """初始化全局压缩器的 LLM 服务

    在应用启动时调用，绑定已创建的 llm_service 实例。

    Args:
        llm_service: LLMService 实例
    """
    context_compressor.llm_service = llm_service
    logger.info("[Compressor] ContextCompressor 初始化完成，LLM 服务已绑定")
