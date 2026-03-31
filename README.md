# PaperChat - 学术论文智能阅读与问答系统

基于云端大模型的智能论文分析系统，支持 PDF 上传、AI 论文结构化解析、智能问答、知识管理与写作辅助。

## 功能概览

### 核心功能

| 功能模块 | 说明 | 后端 | 前端 |
|---------|------|------|------|
| 论文管理 | PDF 上传、存储、元数据管理、阅读状态追踪 | ✅ | ✅ |
| PDF 阅读器 | 原生 PDF 渲染、文本选择、页码导航、阅读进度保存 | ✅ | ✅ |
| 论文解析 | AI 自动分析论文结构、章节概览、深度分析 | ✅ | ✅ |
| 智能问答 | 基于 RAG 的多轮对话、会话持久化、引用溯源 | ✅ | ✅ |
| 高亮标注 | 文本高亮、多色标注、标注管理 | ✅ | ✅ |
| 笔记系统 | 笔记创建、编辑、关联高亮、笔记面板 | ✅ | ✅ |
| 知识库 | 知识卡片管理、标签分类、搜索筛选 | ✅ | ✅ |
| 写作辅助 | 大纲生成、段落生成、学术润色、引用格式、论文对比 | ✅ | ✅ |
| 联网搜索 | 问答时联网搜索补充信息 | ✅ | ✅ |
| 推荐系统 | 相似论文推荐 | ✅ | ✅ |
| Agent 模式 | 意图识别、任务规划、多步推理 | ✅ | ❌ 待集成 |
| 阅读辅助 | 术语解释、文本摘要、翻译（选中文本触发） | ✅ | ❌ 待集成 |
| 知识图谱 | 知识点可视化图谱 | ⚠️ 待确认 | ⚠️ 待确认 |
| 用户设置 | 个性化配置、模型参数、主题切换 | ✅ | ✅ |
| 流式传输 | WebSocket 双向通信，实时流式输出 | ✅ | ✅ |

### 页面结构

| 页面 | 路由 | 说明 |
|------|------|------|
| 统一聊天 | `/chat` | 统一聊天入口，支持论文问答、分析、联网搜索 |
| 论文列表 | `/papers` | 论文库管理、批量导入 |
| 论文阅读 | `/paper/:id` | 三栏布局阅读页面 |
| 知识库 | `/knowledge` | 知识卡片管理 |
| 知识图谱 | `/knowledge-graph` | 知识点可视化图谱（待完善） |
| 写作辅助 | `/writing` | 大纲/润色/引用/对比 |
| 系统设置 | `/settings` | 个性化配置 |
| 用户认证 | `/auth` | 登录/注册 |

## 技术栈

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19.2 | UI 框架 |
| Vite | 8.0 | 构建工具 |
| Zustand | 5.0 | 状态管理 |
| react-router-dom | 7.13 | 路由管理 |
| PDF.js / react-pdf | 5.5 / 10.4 | PDF 渲染 |
| react-markdown | 10.1 | Markdown 渲染 |
| framer-motion | 12.38 | 动画效果 |
| react-dropzone | 15.0 | 文件上传 |
| axios | 1.14 | HTTP 请求 |

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.104+ | 异步 Web 框架 |
| SQLAlchemy | 2.0+ | 异步 ORM |
| aiosqlite | 0.19+ | 异步 SQLite |
| LangChain | 0.1.8+ | LLM 编排框架 |
| langchain-openai | 0.0.5+ | OpenAI 兼容接口 |
| ChromaDB | 1.5+ | 向量数据库 |
| sentence-transformers | 2.5+ | 文本向量化 |
| rank-bm25 | 0.2.2 | BM25 检索 |
| pdfplumber | 0.10+ | PDF 解析 |
| pydantic-settings | 2.0+ | 配置管理 |
| python-jose | 3.3+ | JWT 认证 |

## 项目结构

```
PaperChat/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 应用入口
│   │   ├── config.py            # 配置管理
│   │   ├── database.py          # 数据库连接
│   │   ├── middleware/          # 中间件
│   │   │   └── error_handler.py
│   │   ├── models/              # 数据模型
│   │   │   ├── paper.py         # 论文模型
│   │   │   ├── chat.py          # 会话模型
│   │   │   ├── highlight.py     # 高亮模型
│   │   │   ├── note.py          # 笔记模型
│   │   │   ├── knowledge.py     # 知识卡片模型
│   │   │   ├── memory.py        # 记忆模型
│   │   │   ├── feedback.py      # 反馈模型
│   │   │   ├── settings.py      # 设置模型
│   │   │   └── user.py          # 用户模型
│   │   ├── routers/             # API 路由
│   │   │   ├── papers.py        # 论文管理
│   │   │   ├── analysis.py      # 论文分析
│   │   │   ├── chat.py          # 会话管理
│   │   │   ├── ws.py            # WebSocket 通信
│   │   │   ├── highlights.py    # 高亮标注
│   │   │   ├── notes.py         # 笔记管理
│   │   │   ├── knowledge.py     # 知识库
│   │   │   ├── writing.py       # 写作辅助
│   │   │   ├── recommendations.py # 推荐系统
│   │   │   ├── reading.py       # 阅读辅助
│   │   │   ├── settings.py      # 用户设置
│   │   │   └── auth.py          # 用户认证
│   │   ├── schemas/             # Pydantic 模式
│   │   ├── services/            # 业务服务
│   │   │   ├── llm_service.py   # LLM 调用服务
│   │   │   ├── rag_service.py   # RAG 检索服务
│   │   │   ├── agent_service.py # Agent 智能体服务
│   │   │   ├── pdf_service.py   # PDF 处理服务
│   │   │   ├── knowledge_service.py
│   │   │   ├── recommendation_service.py
│   │   │   ├── search_service.py    # 联网搜索
│   │   │   ├── settings_service.py
│   │   │   ├── memory_service.py
│   │   │   └── auth_service.py
│   │   └── chroma_db/           # ChromaDB 向量数据库
│   ├── services/                # 顶层服务
│   │   ├── llm_service.py
│   │   ├── pdf_parser.py
│   │   └── paragraph_detector.py
│   ├── uploads/                 # PDF 存储目录
│   ├── main.py                  # 入口文件
│   ├── run.py                   # 启动脚本
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── main.jsx             # 应用入口
│   │   ├── App.jsx              # 主应用组件
│   │   ├── App.css              # 全局样式
│   │   ├── api/                 # API 请求
│   │   │   └── index.js
│   │   ├── components/          # UI 组件
│   │   │   ├── FileUpload/      # 文件上传
│   │   │   ├── PDFReader/       # PDF 阅读器
│   │   │   ├── PDFViewer/       # PDF 预览
│   │   │   ├── ChatPanel/       # 智能问答
│   │   │   ├── ExplanationPanel/# 论文解析
│   │   │   ├── HighlightLayer/  # 高亮图层
│   │   │   ├── HighlightToolbar/# 高亮工具栏
│   │   │   ├── NotePanel/       # 笔记面板
│   │   │   ├── NoteEditor/      # 笔记编辑器
│   │   │   ├── KnowledgeCardEditor/
│   │   │   ├── AgentProgress/   # Agent 进度（待集成）
│   │   │   ├── Recommendations/ # 推荐面板
│   │   │   ├── PaperSelector/   # 论文选择器
│   │   │   ├── BatchImport/     # 批量导入
│   │   │   ├── ReadingAssist/   # 阅读辅助（待集成）
│   │   │   ├── Navbar/          # 导航栏
│   │   │   └── ProtectedRoute.jsx
│   │   ├── pages/               # 页面组件
│   │   │   ├── ChatPage.jsx      # 统一聊天页面
│   │   │   ├── PaperList.jsx    # 论文列表
│   │   │   ├── KnowledgePage.jsx# 知识库
│   │   │   ├── KnowledgeGraphPage.jsx # 知识图谱（待完善）
│   │   │   ├── WritingPage.jsx  # 写作辅助
│   │   │   ├── SettingsPage.jsx # 系统设置
│   │   │   ├── AuthPage.jsx     # 登录注册
│   │   │   └── NotFoundPage.jsx
│   │   ├── stores/              # Zustand 状态管理
│   │   │   ├── paperStore.js
│   │   │   ├── chatStore.js
│   │   │   ├── highlightStore.js
│   │   │   ├── noteStore.js
│   │   │   ├── knowledgeStore.js
│   │   │   ├── writingStore.js
│   │   │   ├── settingsStore.js
│   │   │   ├── agentStore.js
│   │   │   └── authStore.js
│   │   ├── hooks/               # 自定义 Hooks
│   │   │   ├── useWebSocket.js
│   │   │   └── useTheme.js
│   │   └── utils/               # 工具函数
│   │       └── MarkdownRenderer.jsx
│   ├── vite.config.js
│   ├── package.json
│   └── index.html
│
└── README.md
```

## 快速开始

### 环境要求

- **Python 3.10+**
- **Node.js 18+**
- **DeepSeek API Key**（[申请地址](https://platform.deepseek.com/)）

### 1. 配置后端

```powershell
cd d:\Trae_projects\ChatPDF\backend

# 复制环境变量模板
copy .env.example .env

# 编辑 .env 文件，填入 API Key
# DEEPSEEK_API_KEY=your-api-key-here

# 创建虚拟环境（可选）
python -m venv venv
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动后端

```powershell
cd d:\Trae_projects\ChatPDF\backend

# 方式一：使用启动脚本
python run.py

# 方式二：直接运行 uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 启动前端

```powershell
cd d:\Trae_projects\ChatPDF\frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 4. 访问应用

浏览器打开 **http://localhost:5173**

## 核心功能详解

### 论文分析

- **章节概览**：自动识别论文结构（摘要、引言、方法、结果、讨论等），生成各章节摘要
- **深度分析**：从研究背景、方法论、实验设计、核心贡献等多维度深入分析
- **关键词提取**：自动提取论文关键词并标签化

### 智能问答

- **RAG 检索增强**：基于 ChromaDB 向量检索 + BM25 混合检索，精准定位相关段落
- **会话持久化**：对话历史存储，支持多轮对话上下文记忆
- **引用溯源**：回答附带来源页码，点击可跳转原文
- **联网搜索**：可选开启联网搜索，补充论文外的信息

### Agent 智能体

> **状态**：后端 ✅ 已完成 | 前端 ❌ 待集成

- **意图识别**：自动判断用户请求类型（问答/分析/对比/搜索/写作）
- **任务规划**：复杂请求自动拆解为多步任务
- **工具调用**：支持搜索、摘要、翻译、解释、对比、评估等多种工具
- **结果聚合**：多步结果整合为连贯回答

**已实现的 9 个工具**：

| 工具 | 功能 |
|------|------|
| `search_text` | 搜索论文文本 |
| `summarize` | 文本摘要 |
| `translate` | 翻译 |
| `explain_term` | 术语解释 |
| `extract_key_points` | 提取知识点 |
| `compare_content` | 对比内容 |
| `generate_outline` | 生成提纲 |
| `assess_quality` | 质量评估 |
| `get_paper_info` | 获取论文信息 |

**待完成**：ChatPage 中启用 Agent 模式开关，集成 AgentProgress 进度展示组件

### 写作辅助

- **大纲生成**：基于研究主题和参考论文生成论文大纲
- **段落生成**：根据大纲节点和参考内容生成学术段落
- **学术润色**：语法修正、流畅性优化、学术表达提升
- **引用格式**：支持 APA/MLA/Chicago/GB/T 7714 等格式
- **论文对比**：多论文维度对比分析

### 知识管理

- **知识卡片**：从高亮、问答、分析中提取知识点
- **标签分类**：自定义标签和分类体系
- **搜索筛选**：全文搜索、多条件筛选
- **统计视图**：分类分布、来源分布、标签云

## WebSocket 通信协议

### 客户端 → 服务器

| 类型 | 字段 | 说明 |
|------|------|------|
| `analyze` | `text`, `paper_id` | 论文章节分析 |
| `deep_analyze` | `text`, `paper_id` | 论文深度分析 |
| `chat` | `message` | 基础问答 |
| `rag_chat` | `message`, `paper_id`, `session_id`, `user_id`, `enable_search` | RAG 增强问答 |
| `cross_doc_chat` | `message`, `paper_ids`, `session_id`, `user_id` | 跨文档问答 |
| `unified_chat` | `message`, `paper_id`, `paper_ids`, `session_id`, `enable_search` | 统一聊天入口（自动路由） |
| `agent_chat` | `message`, `paper_id`, `paper_ids` | Agent 智能问答（后端已实现，前端待集成） |
| `cancel` | - | 取消当前任务 |

### 服务器 → 客户端

| 类型 | 字段 | 说明 |
|------|------|------|
| `analyze_chunk` | `data` | 章节分析流式数据 |
| `deep_analyze_chunk` | `data` | 深度分析流式数据 |
| `chat_chunk` | `data` | 基础问答流式数据 |
| `rag_chat_chunk` | `content` | RAG 问答流式数据 |
| `rag_sources` | `sources` | 引用来源列表 |
| `cross_doc_chunk` | `content` | 跨文档问答流式数据 |
| `cross_doc_sources` | `sources` | 跨文档引用来源 |
| `search_status` | `status`, `results_count` | 联网搜索状态 |
| `intent_detected` | `intent`, `tool`, `confidence`, `matched` | 意图识别结果（统一聊天入口） |
| `agent_intent` | `intent` | Agent 意图识别结果 |
| `agent_plan` | `plan` | Agent 任务计划 |
| `agent_step` | `step`, `description` | Agent 步骤开始 |
| `agent_step_result` | `step`, `result` | Agent 步骤结果 |
| `agent_answer_chunk` | `content` | Agent 最终答案片段 |
| `cancelled` | `message` | 任务取消确认 |
| `keywords_result` | `keywords` | 关键词提取结果 |
| `done` | `channel`, `session_id` | 传输完成 |
| `error` | `message` | 错误信息 |

## API 端点

### 论文管理

- `POST /api/papers/upload` - 上传论文
- `GET /api/papers` - 获取论文列表
- `GET /api/papers/{id}` - 获取论文详情
- `GET /api/papers/{id}/text` - 获取论文文本
- `DELETE /api/papers/{id}` - 删除论文
- `POST /api/papers/batch-import` - 批量导入

### 分析相关

- `GET /api/papers/{id}/analysis` - 获取分析缓存
- `POST /api/analysis/compare` - 论文对比分析

### 高亮与笔记

- `GET /api/highlights?paper_id={id}` - 获取高亮列表
- `POST /api/highlights` - 创建高亮
- `DELETE /api/highlights/{id}` - 删除高亮
- `GET /api/notes?paper_id={id}` - 获取笔记列表
- `POST /api/notes` - 创建笔记
- `PUT /api/notes/{id}` - 更新笔记
- `DELETE /api/notes/{id}` - 删除笔记

### 知识库

- `GET /api/knowledge/cards` - 获取知识卡片
- `POST /api/knowledge/cards` - 创建知识卡片
- `PUT /api/knowledge/cards/{id}` - 更新知识卡片
- `DELETE /api/knowledge/cards/{id}` - 删除知识卡片
- `GET /api/knowledge/stats` - 获取统计信息

### 写作辅助

- `POST /api/writing/outline` - 生成大纲
- `POST /api/writing/draft` - 生成段落
- `POST /api/writing/polish` - 学术润色
- `POST /api/writing/citations` - 生成引用

### 推荐系统

- `GET /api/recommendations/similar/{paper_id}` - 获取相似论文推荐

### 用户设置

- `GET /api/settings` - 获取用户设置
- `PUT /api/settings` - 更新用户设置
- `POST /api/settings/reset` - 重置为默认设置

## 端口说明

| 端口 | 用途 |
|------|------|
| 5173 | 前端开发服务器 |
| 8000 | 后端 API / WebSocket |

## 开发日志

### v1.0 — 基础架构（2026-03-27）

- PDF 文件上传与预览
- 论文结构化解析
- 智能问答基础功能
- 三栏布局界面

### v2.0 — WebSocket + LangChain 重构（2026-03-28）

- WebSocket 双向通信
- LangChain 集成
- 断线自动重连
- 响应式布局
- 三栏拖拽调整

### v2.1 — 交互体验优化（2026-03-29）

- 卡片弹性入场动画
- 问答逐字显示
- 论文解析去重
- Markdown 渲染
- 异步并发处理

### v3.0 — 功能扩展（2026-03-30）

- 高亮标注系统
- 笔记系统
- 知识库管理
- 写作辅助模块
- 相似论文推荐
- 用户设置系统

### v3.1 — Agent 智能体后端（2026-03-31）

> **状态**：后端 ✅ 已完成 | 前端 ❌ 待集成

- Agent 意图识别
- 任务规划与执行
- 多工具调用（9 个工具已实现）
- 联网搜索集成
- 跨文档问答
- 论文对比分析
- RAG 参数可配置
- 会话持久化优化

### v3.2 — 统一聊天入口 + 设计系统重构（2026-04-01）

> **状态**：⚠️ 部分完成

#### 已完成功能

- 统一聊天入口：所有功能（问答、分析、联网搜索）聚合到 `/chat` 页面
- 论文选择支持单篇或多篇
- 基于关键词的意图识别与自动路由
- 联网搜索开关
- 会话持久化与重命名
- 导航栏调整：聊天入口置于论文库之上
- 设计系统重构：从冷色调蓝色系改为暖色调学术风格

#### 设计系统变更

- 配色方案：蓝色 `#007aff` → 暗金色 `#B8860B`
- 字体系统：新增 Playfair Display 衬线字体
- 页面样式：ChatPage、Navbar、PaperList 等全面更新

#### 待完成功能（Agent 前端集成）

- [ ] ChatPage Agent 模式开关
- [ ] AgentProgress 进度展示组件集成
- [ ] 完整 LLM 意图识别（当前使用关键词匹配）
- [ ] 任务步骤可视化
- [ ] 工具调用结果展示

#### 涉及文件

- `frontend/src/pages/ChatPage.jsx` - 统一聊天页面
- `frontend/src/hooks/useWebSocket.js` - WebSocket 方法扩展
- `frontend/src/stores/chatStore.js` - 会话管理增强
- `frontend/src/components/AgentProgress/` - Agent 进度组件（已实现，待集成）
- `frontend/src/components/Navbar/Navbar.jsx` - 导航顺序调整
- `frontend/src/index.css` - 设计系统重构

---

> PaperChat - 让学术阅读更高效
