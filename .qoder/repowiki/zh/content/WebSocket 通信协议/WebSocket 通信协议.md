# WebSocket 通信协议

<cite>
**本文引用的文件**
- [backend/app/routers/ws.py](file://backend/app/routers/ws.py)
- [backend/app/handlers/analyze_handler.py](file://backend/app/handlers/analyze_handler.py)
- [backend/app/handlers/chat_handler.py](file://backend/app/handlers/chat_handler.py)
- [backend/app/handlers/rag_handler.py](file://backend/app/handlers/rag_handler.py)
- [backend/app/handlers/cross_doc_handler.py](file://backend/app/handlers/cross_doc_handler.py)
- [backend/app/handlers/agent_handler.py](file://backend/app/handlers/agent_handler.py)
- [backend/app/services/agent_service.py](file://backend/app/services/agent_service.py)
- [backend/app/services/llm/llm_service.py](file://backend/app/services/llm/llm_service.py)
- [frontend/src/hooks/useWebSocket.js](file://frontend/src/hooks/useWebSocket.js)
- [frontend/src/components/ChatPanel/ChatPanel.jsx](file://frontend/src/components/ChatPanel/ChatPanel.jsx)
- [frontend/src/stores/chatStore.js](file://frontend/src/stores/chatStore.js)
- [backend/app/middleware/error_handler.py](file://backend/app/middleware/error_handler.py)
</cite>

## 目录
1. [简介](#简介)
2. [项目结构](#项目结构)
3. [核心组件](#核心组件)
4. [架构总览](#架构总览)
5. [详细组件分析](#详细组件分析)
6. [依赖关系分析](#依赖关系分析)
7. [性能考量](#性能考量)
8. [故障排查指南](#故障排查指南)
9. [结论](#结论)
10. [附录](#附录)

## 简介
本文件面向 PaperChat 的 WebSocket 实时通信协议，系统性阐述双向实时通信的架构设计、连接建立、消息传递与断线重连机制；明确客户端到服务器的消息类型定义（分析请求、问答请求、跨文档问答、Agent 智能体通信），以及服务器到客户端的响应格式（流式数据、引用来源列表、错误处理）。同时提供完整的消息协议规范、字段定义、状态码说明、连接生命周期管理、心跳与异常处理策略，并给出客户端集成示例与调试技巧。

## 项目结构
PaperChat 的 WebSocket 位于后端 FastAPI 路由模块，通过独立的 WebSocket 端点接收消息并分发至各业务处理器；前端通过自定义 React Hook 管理连接、消息收发与重连逻辑。

```mermaid
graph TB
subgraph "前端"
FE_WS["React Hook<br/>useWebSocket.js"]
FE_UI["聊天界面<br/>ChatPanel.jsx"]
FE_STORE["状态管理<br/>chatStore.js"]
end
subgraph "后端"
WS_ROUTE["WebSocket 路由<br/>ws.py"]
CONN_STATE["连接状态共享<br/>ConnectionState"]
HANDLER_ANALYZE["分析处理器<br/>analyze_handler.py"]
HANDLER_CHAT["问答处理器<br/>chat_handler.py"]
HANDLER_RAG["RAG 处理器<br/>rag_handler.py"]
HANDLER_CROSS["跨文档处理器<br/>cross_doc_handler.py"]
HANDLER_AGENT["Agent 处理器<br/>agent_handler.py"]
SERVICE_LLM["LLM 服务<br/>llm_service.py"]
SERVICE_AGENT["Agent 服务<br/>agent_service.py"]
end
FE_WS --> WS_ROUTE
FE_UI --> FE_WS
FE_STORE --> FE_WS
WS_ROUTE --> CONN_STATE
WS_ROUTE --> HANDLER_ANALYZE
WS_ROUTE --> HANDLER_CHAT
WS_ROUTE --> HANDLER_RAG
WS_ROUTE --> HANDLER_CROSS
WS_ROUTE --> HANDLER_AGENT
HANDLER_ANALYZE --> SERVICE_LLM
HANDLER_CHAT --> SERVICE_LLM
HANDLER_RAG --> SERVICE_LLM
HANDLER_CROSS --> SERVICE_LLM
HANDLER_AGENT --> SERVICE_AGENT
```

图表来源
- [backend/app/routers/ws.py:76-102](file://backend/app/routers/ws.py#L76-L102)
- [backend/app/handlers/analyze_handler.py:13-49](file://backend/app/handlers/analyze_handler.py#L13-L49)
- [backend/app/handlers/chat_handler.py:11-32](file://backend/app/handlers/chat_handler.py#L11-L32)
- [backend/app/handlers/rag_handler.py:29-217](file://backend/app/handlers/rag_handler.py#L29-L217)
- [backend/app/handlers/cross_doc_handler.py:14-95](file://backend/app/handlers/cross_doc_handler.py#L14-L95)
- [backend/app/handlers/agent_handler.py:11-67](file://backend/app/handlers/agent_handler.py#L11-L67)
- [backend/app/services/llm/llm_service.py:29-200](file://backend/app/services/llm/llm_service.py#L29-L200)
- [backend/app/services/agent_service.py:473-760](file://backend/app/services/agent_service.py#L473-L760)
- [frontend/src/hooks/useWebSocket.js:1-180](file://frontend/src/hooks/useWebSocket.js#L1-L180)
- [frontend/src/components/ChatPanel/ChatPanel.jsx:132-200](file://frontend/src/components/ChatPanel/ChatPanel.jsx#L132-L200)
- [frontend/src/stores/chatStore.js:1-200](file://frontend/src/stores/chatStore.js#L1-L200)

章节来源
- [backend/app/routers/ws.py:76-102](file://backend/app/routers/ws.py#L76-L102)
- [frontend/src/hooks/useWebSocket.js:1-180](file://frontend/src/hooks/useWebSocket.js#L1-L180)

## 核心组件
- WebSocket 路由与连接管理：负责认证、连接接受、消息分发、任务并发控制与清理。
- 处理器层：按消息类型分发到具体业务处理器（分析、问答、RAG、跨文档、Agent）。
- 服务层：LLM 服务提供流式生成能力；Agent 服务提供意图识别、任务规划与工具执行。
- 前端 Hook：封装 WebSocket 连接、消息订阅、重连策略与发送接口。

章节来源
- [backend/app/routers/ws.py:32-102](file://backend/app/routers/ws.py#L32-L102)
- [backend/app/handlers/analyze_handler.py:13-49](file://backend/app/handlers/analyze_handler.py#L13-L49)
- [backend/app/handlers/chat_handler.py:11-32](file://backend/app/handlers/chat_handler.py#L11-L32)
- [backend/app/handlers/rag_handler.py:29-217](file://backend/app/handlers/rag_handler.py#L29-L217)
- [backend/app/handlers/cross_doc_handler.py:14-95](file://backend/app/handlers/cross_doc_handler.py#L14-L95)
- [backend/app/handlers/agent_handler.py:11-67](file://backend/app/handlers/agent_handler.py#L11-L67)
- [backend/app/services/llm/llm_service.py:29-200](file://backend/app/services/llm/llm_service.py#L29-L200)
- [backend/app/services/agent_service.py:473-760](file://backend/app/services/agent_service.py#L473-L760)
- [frontend/src/hooks/useWebSocket.js:1-180](file://frontend/src/hooks/useWebSocket.js#L1-L180)

## 架构总览
WebSocket 采用“路由分发 + 处理器执行”的模式，每个消息类型映射到一个异步处理函数，支持流式响应与引用来源回传。连接状态在处理器间共享，便于会话持久化与上下文维护。

```mermaid
sequenceDiagram
participant FE as "前端客户端"
participant WS as "WebSocket 路由(ws.py)"
participant ST as "连接状态(ConnectionState)"
participant HD as "业务处理器"
participant SV as "LLM/Agent 服务"
FE->>WS : "建立连接(token 可选)"
WS-->>FE : "接受连接"
loop "消息循环"
FE->>WS : "type : 消息类型 + 载荷"
WS->>ST : "更新状态(会话/上下文)"
WS->>HD : "分发到对应处理器"
HD->>SV : "调用服务(流式/非流式)"
SV-->>HD : "流式片段/最终结果"
HD-->>WS : "组装响应(片段/来源/完成)"
WS-->>FE : "type : 响应类型 + 数据"
end
WS-->>FE : "关闭连接(异常/断开)"
```

图表来源
- [backend/app/routers/ws.py:114-436](file://backend/app/routers/ws.py#L114-L436)
- [backend/app/handlers/analyze_handler.py:13-49](file://backend/app/handlers/analyze_handler.py#L13-L49)
- [backend/app/handlers/rag_handler.py:29-217](file://backend/app/handlers/rag_handler.py#L29-L217)
- [backend/app/handlers/cross_doc_handler.py:14-95](file://backend/app/handlers/cross_doc_handler.py#L14-L95)
- [backend/app/handlers/agent_handler.py:11-67](file://backend/app/handlers/agent_handler.py#L11-L67)
- [backend/app/services/llm/llm_service.py:129-200](file://backend/app/services/llm/llm_service.py#L129-L200)
- [backend/app/services/agent_service.py:494-727](file://backend/app/services/agent_service.py#L494-L727)

## 详细组件分析

### WebSocket 路由与连接生命周期
- 认证：支持 JWT token；无 token 时允许连接但后续行为受限。
- 连接接受：成功后初始化连接状态对象，存储用户、会话、论文上下文与运行中的任务集合。
- 消息循环：读取文本消息，解析 JSON，按 type 分发；同一类型消息到达时取消之前的任务。
- 断线与清理：捕获断开与异常，取消所有任务并安全关闭连接。

章节来源
- [backend/app/routers/ws.py:32-102](file://backend/app/routers/ws.py#L32-L102)
- [backend/app/routers/ws.py:114-436](file://backend/app/routers/ws.py#L114-L436)

### 客户端到服务器的消息类型定义
- 分析论文
  - 类型：analyze
  - 载荷字段：text（论文文本）、paper_id（可选）
  - 行为：校验文本长度，流式返回分析片段，完成后发送完成信号
- 问答（全文上下文）
  - 类型：chat
  - 载荷字段：message（问题）
  - 行为：基于全文上下文的流式问答，返回片段与完成信号
- RAG 问答
  - 类型：rag_chat
  - 载荷字段：message（问题）、paper_id（必需）、session_id（可选）、user_id（可选）、enable_search（布尔）
  - 行为：检索相关文本块，可选联网搜索，流式返回回答与引用来源，保存消息与会话标题
- 跨文档问答
  - 类型：cross_doc_chat
  - 载荷字段：message（问题）、paper_ids（论文 ID 列表，至少一个）、session_id（可选）、user_id（可选）
  - 行为：跨多篇论文检索，返回引用来源与流式回答，保存消息
- 深度分析
  - 类型：deep_analyze
  - 载荷字段：text（论文文本）、paper_id（可选）
  - 行为：深度分析流式返回，完成后发送完成信号
- Agent 智能问答
  - 类型：agent_chat
  - 载荷字段：message（问题）、paper_id（可选）、paper_ids（可选）
  - 行为：意图识别 → 任务规划 → 步骤执行 → 最终答案聚合，期间发送意图、计划、步骤与答案片段
- 取消任务
  - 类型：cancel
  - 行为：取消所有运行中的任务并返回取消确认
- 统一聊天入口
  - 类型：unified_chat
  - 载荷字段：message（问题）、paper_id（可选）、paper_ids（可选）、session_id（可选）、enable_search（布尔）
  - 行为：基于关键词识别意图，自动路由到对应处理器，并返回意图检测结果

章节来源
- [backend/app/routers/ws.py:84-102](file://backend/app/routers/ws.py#L84-L102)
- [backend/app/routers/ws.py:120-417](file://backend/app/routers/ws.py#L120-L417)

### 服务器到客户端的响应格式
- 分析片段
  - 类型：analyze_chunk
  - 字段：data（片段文本）
- 问答片段
  - 类型：chat_chunk
  - 字段：data（片段文本）
- RAG 问答片段
  - 类型：rag_chat_chunk
  - 字段：content（片段文本）
- 跨文档问答片段
  - 类型：cross_doc_chunk
  - 字段：content（片段文本）
- 引用来源（RAG）
  - 类型：rag_sources
  - 字段：sources（数组，元素包含 text、pages、score；网络来源含 title、href）
- 引用来源（跨文档）
  - 类型：cross_doc_sources
  - 字段：sources（数组，元素包含 text、pages、paper_id、score）
- 搜索状态
  - 类型：search_status
  - 字段：status（searching/completed）、results_count（整数）
- 完成信号
  - 类型：done
  - 字段：channel（analyze/chat/rag_chat/cross_doc_chat/agent_chat/unified）、session_id（可选）
- 错误
  - 类型：error
  - 字段：message（错误信息）
- Agent 特有
  - 类型：agent_intent、agent_plan、agent_step、agent_step_result、agent_answer_chunk

章节来源
- [backend/app/routers/ws.py:92-101](file://backend/app/routers/ws.py#L92-L101)
- [backend/app/handlers/analyze_handler.py:20-48](file://backend/app/handlers/analyze_handler.py#L20-L48)
- [backend/app/handlers/chat_handler.py:14-31](file://backend/app/handlers/chat_handler.py#L14-L31)
- [backend/app/handlers/rag_handler.py:180-206](file://backend/app/handlers/rag_handler.py#L180-L206)
- [backend/app/handlers/cross_doc_handler.py:58-84](file://backend/app/handlers/cross_doc_handler.py#L58-L84)
- [backend/app/handlers/agent_handler.py:18-66](file://backend/app/handlers/agent_handler.py#L18-L66)

### 处理器工作流与数据流

#### 分析处理器（章节概述/深度分析）
```mermaid
flowchart TD
Start(["收到 analyze/deep_analyze"]) --> Init["初始化上下文<br/>清空历史"]
Init --> Stream["流式生成分析/深度分析片段"]
Stream --> SendChunk["发送 analyze_chunk/deep_analyze_chunk"]
SendChunk --> SaveCache{"paper_id 存在？"}
SaveCache --> |是| Cache["保存分析缓存"]
SaveCache --> |否| SkipCache["跳过缓存"]
Cache --> Done["发送 done"]
SkipCache --> Done
SendChunk --> Keywords["异步提取关键词"]
Done --> End(["结束"])
```

图表来源
- [backend/app/handlers/analyze_handler.py:13-87](file://backend/app/handlers/analyze_handler.py#L13-L87)

章节来源
- [backend/app/handlers/analyze_handler.py:13-87](file://backend/app/handlers/analyze_handler.py#L13-L87)

#### RAG 处理器（检索增强问答）
```mermaid
sequenceDiagram
participant C as "客户端"
participant W as "WebSocket 路由"
participant R as "RAG 处理器"
participant S as "检索服务"
participant L as "LLM 服务"
C->>W : "rag_chat(message, paper_id, ...)"
W->>R : "分发处理"
R->>R : "获取/创建会话"
R->>R : "保存用户消息"
R->>S : "检索相关文本块(top_k)"
alt "无结果"
R->>S : "检查文本块/重建索引"
S-->>R : "重建完成/仍无结果"
end
opt "启用联网搜索"
R->>C : "search_status : searching"
R->>S : "网络搜索(max_results)"
R->>C : "search_status : completed"
end
R->>L : "构造系统提示词(论文+网络)"
L-->>R : "流式回答片段"
R->>C : "rag_chat_chunk"
R->>C : "rag_sources"
R->>R : "保存助手消息"
R->>C : "done(session_id)"
```

图表来源
- [backend/app/handlers/rag_handler.py:29-217](file://backend/app/handlers/rag_handler.py#L29-L217)
- [backend/app/services/llm/llm_service.py:173-200](file://backend/app/services/llm/llm_service.py#L173-L200)

章节来源
- [backend/app/handlers/rag_handler.py:29-217](file://backend/app/handlers/rag_handler.py#L29-L217)
- [backend/app/services/llm/llm_service.py:173-200](file://backend/app/services/llm/llm_service.py#L173-L200)

#### 跨文档处理器
```mermaid
flowchart TD
A["收到 cross_doc_chat"] --> B["获取/创建会话"]
B --> C["保存用户消息(附 paper_ids)"]
C --> D["检索多篇论文(top_k)"]
D --> E{"是否有结果？"}
E --> |否| F["发送无结果提示 + done"]
E --> |是| G["组装 cross_doc_sources"]
G --> H["流式生成回答"]
H --> I["保存助手消息"]
I --> J["发送 done(session_id)"]
```

图表来源
- [backend/app/handlers/cross_doc_handler.py:14-95](file://backend/app/handlers/cross_doc_handler.py#L14-L95)

章节来源
- [backend/app/handlers/cross_doc_handler.py:14-95](file://backend/app/handlers/cross_doc_handler.py#L14-L95)

#### Agent 智能体处理器
```mermaid
sequenceDiagram
participant C as "客户端"
participant W as "WebSocket 路由"
participant A as "Agent 处理器"
participant AS as "Agent 服务"
participant T as "工具(搜索/摘要/翻译/...)"
C->>W : "agent_chat(message, paper_id/paper_ids)"
W->>A : "分发处理"
A->>AS : "意图识别(classify_intent)"
AS-->>A : "意图结果"
A->>C : "agent_intent"
A->>AS : "任务规划(plan_tasks)"
AS-->>A : "计划(步骤+工具)"
A->>C : "agent_plan"
loop "逐步执行"
A->>AS : "execute_plan(step)"
AS->>T : "调用具体工具"
T-->>AS : "工具结果"
AS-->>A : "step_result"
A->>C : "agent_step/agent_step_result"
end
A->>AS : "聚合最终答案"
AS-->>A : "final_answer_chunk"
A->>C : "agent_answer_chunk"
A->>C : "done(agent_chat)"
```

图表来源
- [backend/app/handlers/agent_handler.py:11-67](file://backend/app/handlers/agent_handler.py#L11-L67)
- [backend/app/services/agent_service.py:494-727](file://backend/app/services/agent_service.py#L494-L727)

章节来源
- [backend/app/handlers/agent_handler.py:11-67](file://backend/app/handlers/agent_handler.py#L11-L67)
- [backend/app/services/agent_service.py:473-760](file://backend/app/services/agent_service.py#L473-L760)

### 客户端集成与使用示例
- 连接建立
  - 自动携带本地 token（若存在），否则匿名连接
  - 连接状态通过全局状态管理，支持订阅与重连
- 发送消息
  - 基础问答：sendMessage(type='chat', { message })
  - RAG 问答：sendRagMessage(message, paperId, sessionId?, userId?, enableSearch?)
  - 跨文档问答：sendCrossDocMessage(message, paperIds[], sessionId?, userId?)
  - 统一入口：sendUnifiedChatMessage(message, paperId?, paperIds?, sessionId?, enableSearch?)
  - 取消任务：sendCancel()
- 订阅响应
  - onMessage('rag_chat_chunk', handler) 订阅流式回答
  - onMessage('rag_sources', handler) 订阅引用来源
  - onMessage('done', handler) 订阅完成信号
  - onMessage('error', handler) 订阅错误
  - onMessage('*', handler) 订阅所有消息
- 前端展示
  - ChatPanel 根据 sources/crossDocSources 渲染引用来源
  - chatStore 管理会话、消息与搜索状态

章节来源
- [frontend/src/hooks/useWebSocket.js:1-180](file://frontend/src/hooks/useWebSocket.js#L1-L180)
- [frontend/src/components/ChatPanel/ChatPanel.jsx:132-200](file://frontend/src/components/ChatPanel/ChatPanel.jsx#L132-L200)
- [frontend/src/stores/chatStore.js:1-200](file://frontend/src/stores/chatStore.js#L1-L200)

## 依赖关系分析
- 路由层依赖各处理器与服务层；处理器依赖 LLM/Agent 服务；前端 Hook 依赖路由层。
- 并发控制：同一类型消息到达时取消旧任务，避免资源浪费。
- 会话持久化：RAG/跨文档处理器通过会话 ID 与历史消息实现上下文延续。

```mermaid
graph LR
WS["ws.py"] --> AH["analyze_handler.py"]
WS --> CH["chat_handler.py"]
WS --> RH["rag_handler.py"]
WS --> XH["cross_doc_handler.py"]
WS --> AGH["agent_handler.py"]
AH --> LLM["llm_service.py"]
CH --> LLM
RH --> LLM
XH --> LLM
AGH --> AGS["agent_service.py"]
FE["useWebSocket.js"] --> WS
FE_UI["ChatPanel.jsx"] --> FE
FE_STORE["chatStore.js"] --> FE
```

图表来源
- [backend/app/routers/ws.py:23-27](file://backend/app/routers/ws.py#L23-L27)
- [backend/app/handlers/analyze_handler.py:8-10](file://backend/app/handlers/analyze_handler.py#L8-L10)
- [backend/app/handlers/rag_handler.py:10-17](file://backend/app/handlers/rag_handler.py#L10-L17)
- [backend/app/handlers/cross_doc_handler.py:8-11](file://backend/app/handlers/cross_doc_handler.py#L8-L11)
- [backend/app/handlers/agent_handler.py](file://backend/app/handlers/agent_handler.py#L8)
- [backend/app/services/llm/llm_service.py:29-47](file://backend/app/services/llm/llm_service.py#L29-L47)
- [backend/app/services/agent_service.py:473-492](file://backend/app/services/agent_service.py#L473-L492)
- [frontend/src/hooks/useWebSocket.js:1-180](file://frontend/src/hooks/useWebSocket.js#L1-L180)
- [frontend/src/components/ChatPanel/ChatPanel.jsx:132-200](file://frontend/src/components/ChatPanel/ChatPanel.jsx#L132-L200)
- [frontend/src/stores/chatStore.js:1-200](file://frontend/src/stores/chatStore.js#L1-L200)

章节来源
- [backend/app/routers/ws.py:23-27](file://backend/app/routers/ws.py#L23-L27)
- [frontend/src/hooks/useWebSocket.js:1-180](file://frontend/src/hooks/useWebSocket.js#L1-L180)

## 性能考量
- 流式输出：LLM 服务开启流式生成，前端可即时渲染，降低感知延迟。
- 检索优化：RAG 通过向量检索减少上下文长度，显著降低 token 消耗与响应时间。
- 并发与取消：同一类型消息到达时取消旧任务，避免重复计算。
- 异步关键词提取：分析完成后异步提取关键词，不阻塞主流程。
- 前端渲染优化：React.memo 与键控渲染减少不必要的重绘。

章节来源
- [backend/app/services/llm/llm_service.py:129-200](file://backend/app/services/llm/llm_service.py#L129-L200)
- [backend/app/handlers/analyze_handler.py:37-48](file://backend/app/handlers/analyze_handler.py#L37-L48)
- [backend/app/routers/ws.py:130-135](file://backend/app/routers/ws.py#L130-L135)

## 故障排查指南
- 连接失败
  - 检查 token 是否有效；无 token 时可连接但需注意权限限制。
  - 查看后端日志与异常处理器返回的标准化错误。
- 消息无效
  - 确认消息类型与必填字段；后端会对缺失字段返回错误。
- RAG 无结果
  - 检查论文是否解析完成；若无索引，处理器会尝试重建索引。
  - 若启用联网搜索，确认网络可达与搜索结果数量。
- Agent 未按预期执行
  - 关注 intent_detected 与 agent_intent/plan/step 等中间事件，定位意图识别或工具执行阶段。
- 前端无响应
  - 确认 onMessage 订阅是否正确；检查连接状态与重连逻辑。

章节来源
- [backend/app/middleware/error_handler.py:11-92](file://backend/app/middleware/error_handler.py#L11-L92)
- [backend/app/routers/ws.py:120-172](file://backend/app/routers/ws.py#L120-L172)
- [backend/app/handlers/rag_handler.py:48-90](file://backend/app/handlers/rag_handler.py#L48-L90)
- [frontend/src/hooks/useWebSocket.js:19-71](file://frontend/src/hooks/useWebSocket.js#L19-L71)

## 结论
PaperChat 的 WebSocket 协议通过清晰的消息类型与响应格式、完善的流式传输与引用来源回传、严格的连接生命周期管理与错误处理，实现了论文分析、问答与跨文档检索的高效实时通信。前端 Hook 提供了简洁的接入方式与健壮的重连策略，配合后端处理器与服务层，满足从简单问答到复杂 Agent 多步推理的多样化需求。

## 附录

### 消息协议规范

- 连接建立
  - 地址：/ws
  - 查询参数：token（可选）
  - 成功：接受连接；失败：关闭连接并返回 4001（未授权）

- 客户端发送（type 字段）
  - analyze：text（字符串，≥50 字符）、paper_id（可选）
  - chat：message（字符串，非空）
  - rag_chat：message（字符串，非空）、paper_id（整数，必需）、session_id（整数，可选）、user_id（整数，可选）、enable_search（布尔）
  - cross_doc_chat：message（字符串，非空）、paper_ids（数组，至少一项）、session_id（整数，可选）、user_id（整数，可选）
  - deep_analyze：text（字符串，≥50 字符）、paper_id（可选）
  - agent_chat：message（字符串，非空）、paper_id（整数，可选）、paper_ids（数组，可选）
  - cancel：无字段
  - unified_chat：message（字符串，非空）、paper_id（整数，可选）、paper_ids（数组，可选）、session_id（整数，可选）、enable_search（布尔）

- 服务器响应（type 字段）
  - analyze_chunk：data（字符串）
  - chat_chunk：data（字符串）
  - rag_chat_chunk：content（字符串）
  - cross_doc_chunk：content（字符串）
  - rag_sources：sources（数组，元素含 text、pages、score；网络来源含 title、href）
  - cross_doc_sources：sources（数组，元素含 text、pages、paper_id、score）
  - search_status：status（字符串，searching/completed）、results_count（整数）
  - done：channel（字符串）、session_id（整数，可选）
  - error：message（字符串）
  - agent_intent/agent_plan/agent_step/agent_step_result/agent_answer_chunk：Agent 中间与最终结果

- 状态码
  - 4001：未授权（token 无效或用户不可用）

章节来源
- [backend/app/routers/ws.py:76-102](file://backend/app/routers/ws.py#L76-L102)
- [backend/app/routers/ws.py:120-436](file://backend/app/routers/ws.py#L120-L436)
- [backend/app/handlers/analyze_handler.py:20-48](file://backend/app/handlers/analyze_handler.py#L20-L48)
- [backend/app/handlers/rag_handler.py:180-206](file://backend/app/handlers/rag_handler.py#L180-L206)
- [backend/app/handlers/cross_doc_handler.py:58-84](file://backend/app/handlers/cross_doc_handler.py#L58-L84)
- [backend/app/handlers/agent_handler.py:18-66](file://backend/app/handlers/agent_handler.py#L18-L66)