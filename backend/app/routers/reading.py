"""阅读辅助路由

提供术语解释、文本摘要、翻译等阅读辅助功能
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.auth_service import get_current_user
from app.services.llm_service import llm_service

router = APIRouter(prefix="/api/reading", tags=["reading"])


class ExplainRequest(BaseModel):
    """术语解释请求"""
    term: str
    context: str = ""  # 术语所在的上下文段落


class SummarizeRequest(BaseModel):
    """文本摘要请求"""
    text: str


class TranslateRequest(BaseModel):
    """文本翻译请求"""
    text: str
    target_lang: str = "zh"


@router.post("/explain-term")
async def explain_term(req: ExplainRequest, user=Depends(get_current_user)):
    """
    流式返回术语解释
    
    请求体:
        - term: 要解释的术语
        - context: 术语所在的上下文（可选）
    
    返回:
        - SSE 流式响应，逐字返回解释内容
    """
    async def generate():
        try:
            async for chunk in llm_service.explain_term(req.term, req.context):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/summarize")
async def summarize_text(req: SummarizeRequest, user=Depends(get_current_user)):
    """
    流式返回文本摘要
    
    请求体:
        - text: 要摘要的文本内容
    
    返回:
        - SSE 流式响应，逐字返回摘要内容
    """
    # 限制文本长度，避免超出模型上下文
    max_length = 8000
    text = req.text[:max_length] if len(req.text) > max_length else req.text
    
    async def generate():
        try:
            async for chunk in llm_service.summarize_text(text):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/translate")
async def translate_text(req: TranslateRequest, user=Depends(get_current_user)):
    """
    流式返回翻译结果
    
    请求体:
        - text: 要翻译的文本内容
        - target_lang: 目标语言代码，默认中文(zh)
    
    返回:
        - SSE 流式响应，逐字返回翻译内容
    """
    # 限制文本长度
    max_length = 8000
    text = req.text[:max_length] if len(req.text) > max_length else req.text
    
    async def generate():
        try:
            async for chunk in llm_service.translate_text(text, req.target_lang):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
