import os
from typing import AsyncGenerator, List, Dict
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "your-api-key-here")

ANALYZE_SYSTEM_PROMPT = """你是一个专业的学术论文分析助手。请对用户提供的论文内容进行结构化解析和解释。

要求：
1. 按论文结构顺序逐部分解释：标题、摘要、各章节、各小节
2. 每个部分用以下JSON格式输出（每个部分一个JSON对象，用换行分隔）：
{"section": "章节名称", "type": "title|abstract|section|subsection", "explanation": "对该部分的简要中文解释"}
3. 参考文献（References）部分不需要解释，直接跳过
4. 解释应简洁明了，用中文，帮助读者快速理解论文的核心内容
5. 每输出一个部分的JSON后换行，不要一次输出所有内容"""

CHAT_SYSTEM_PROMPT = """你是一个专业的学术论文问答助手。以下是用户上传的论文内容，请基于论文内容回答用户的问题。
如果问题与论文无关，请礼貌地提示用户。回答请使用中文。

论文内容：
{paper_context}"""


class LLMService:
    """基于LangChain的DeepSeek大模型交互服务"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="deepseek-chat",
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
            temperature=0.3,
            max_tokens=4096,
            streaming=True,
        )
    
    async def analyze_paper(self, text: str) -> AsyncGenerator[str, None]:
        """分析论文，流式返回结构化解释"""
        messages = [
            SystemMessage(content=ANALYZE_SYSTEM_PROMPT),
            HumanMessage(content=text),
        ]
        async for chunk in self.llm.astream(messages):
            if chunk.content:
                yield chunk.content
    
    async def chat(self, message: str, paper_context: str, chat_history: ChatMessageHistory) -> AsyncGenerator[str, None]:
        """基于论文内容的问答，流式返回回答"""
        # 构建系统消息
        system_content = CHAT_SYSTEM_PROMPT.format(paper_context=paper_context[:15000])
        
        messages = [SystemMessage(content=system_content)]
        
        # 添加历史对话
        messages.extend(chat_history.messages)
        
        # 添加当前用户消息
        messages.append(HumanMessage(content=message))
        
        # 流式获取回复
        full_response = ""
        async for chunk in self.llm.astream(messages):
            if chunk.content:
                full_response += chunk.content
                yield chunk.content
        
        # 保存到历史记录
        chat_history.add_user_message(message)
        chat_history.add_ai_message(full_response)


# 全局单例
llm_service = LLMService()
