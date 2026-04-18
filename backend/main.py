import os
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

# 设置 HuggingFace 镜像（国内下载加速）- 必须在导入任何 huggingface 相关库之前设置
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

# 设置 HuggingFace 模型缓存目录（项目目录下）
_hf_cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
os.makedirs(_hf_cache_path, exist_ok=True)
os.environ['HF_HOME'] = _hf_cache_path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.chat_message_histories import ChatMessageHistory
from services.llm_service import llm_service

app = FastAPI(title="PaperChat API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "PaperChat API v3.0 (WebSocket + LangChain)"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # 每个连接维护独立状态
    paper_context = ""
    chat_history = ChatMessageHistory()
    # 跟踪正在运行的任务
    running_tasks = {}
    
    async def handle_analyze(text):
        """异步处理论文分析"""
        nonlocal paper_context
        paper_context = text
        chat_history.clear()
        
        try:
            async for chunk in llm_service.analyze_paper(text):
                await websocket.send_text(json.dumps({
                    "type": "analyze_chunk",
                    "data": chunk
                }))
            await websocket.send_text(json.dumps({
                "type": "done",
                "channel": "analyze"
            }))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"分析失败: {str(e)}"
            }))
        finally:
            running_tasks.pop("analyze", None)
    
    async def handle_chat(message):
        """异步处理问答"""
        try:
            async for chunk in llm_service.chat(message, paper_context, chat_history):
                await websocket.send_text(json.dumps({
                    "type": "chat_chunk",
                    "data": chunk
                }))
            await websocket.send_text(json.dumps({
                "type": "done",
                "channel": "chat"
            }))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"问答失败: {str(e)}"
            }))
        finally:
            running_tasks.pop("chat", None)
    
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")
            
            if msg_type == "analyze":
                text = data.get("text", "")
                if not text or len(text.strip()) < 50:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "论文内容过短，请提供完整的论文文本"
                    }))
                    continue
                
                # 取消之前正在进行的分析
                if "analyze" in running_tasks:
                    running_tasks["analyze"].cancel()
                
                # 启动新的异步分析任务
                running_tasks["analyze"] = asyncio.create_task(handle_analyze(text))
            
            elif msg_type == "chat":
                message = data.get("message", "")
                if not message:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "消息不能为空"
                    }))
                    continue
                
                # 取消之前正在进行的问答
                if "chat" in running_tasks:
                    running_tasks["chat"].cancel()
                
                # 启动新的异步问答任务
                running_tasks["chat"] = asyncio.create_task(handle_chat(message))
            
            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"未知消息类型: {msg_type}"
                }))
    
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # 清理所有运行中的任务
        for task in running_tasks.values():
            task.cancel()
        try:
            await websocket.close()
        except:
            pass
