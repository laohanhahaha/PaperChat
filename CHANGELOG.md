# Changelog

All notable changes to PaperChat will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [5.0.0] - 2026-05-02

### Added

**多 Agent 系统**
- 自定义子 Agent：创建、配置独立 Agent 角色与工具集
- 子 Agent 管理 CRUD API 与前端管理面板
- ReAct 推理引擎：思考-行动-观察循环
- 任务规划器：复杂请求自动拆解为多步任务
- 研究 Agent：自动搜索、阅读、分析、汇总多篇论文
- 跨论文工具集：论文间对比、引用关联分析

**模型配置与路由**
- 多模型配置管理（前端/后端 CRUD）
- 智能路由引擎：`local_only / smart_route / cloud_only` 三级策略
- 预算控制与费用阈值确认
- 按会话/模型统计 Token 消耗与费用

**知识图谱**
- 知识点与论文关联的可视化图谱
- 图谱 CRUD API
- 前端图谱交互组件（KnowledgeGraph）

**批量操作**
- 批量分析：对多篇论文一键批量分析
- 文件夹导入：递归扫描目录批量导入 PDF
- arXiv 预缓存：定时预抓取 arXiv 论文，可配置时间间隔与主题

**导出与备份**
- 论文/笔记/标注导出
- 数据库备份/恢复 API

**基础设施**
- MCP 协议集成（Model Context Protocol 客户端、桥接、传输层）
- 特性开关系统（Feature Flag）
- 指标面板（Metrics Dashboard）
- 隐私控制（论文可见性设�Z）
- 离线队列：网络恢复后自动重试
- 网络状态检测（OfflineBanner 组件）
- 国际化支持（i18n 框架）
- Mermaid 图表渲染支持
- 上下文压缩器（长上下文优化）
- 记忆中间件

**前端组件**
- SubAgentManager：子 Agent 管理界面
- ModelManager：模型配置管理
- CostConfirmDialog：费用确认弹窗
- ModelIndicator：当前模型指示器
- KnowledgeGraph：知识图谱可视化
- BatchAnalysis：批量分析面板
- MetricsDashboard：指标仪表盘
- OfflineBanner：离线提示横幅
- MermaidChart：Mermaid 图表渲染

**后端服务模块**
- `services/routing/`：智能路由引擎
- `services/cost/`：成本计算服务
- `services/export/`：导出服务
- `services/privacy/`：隐私控制
- `services/security/`：安全模块
- `services/metrics/`：指标收集
- `services/health/`：健康检查
- `services/citation/`：引用管理
- `services/precache_service.py`：arXiv 预缓存
- `services/agent/config_agent.py`：配置 Agent

### Changed
- 后端架构模块化重构，服务层拆分为独立子模块
- 四层配置体系：代码默认值 → `.env` → `paperchat.yaml` → 用户数据库设置
- RAG 增强：集成 bge-reranker-v2-m3 重排序器
- WebSocket 状态管理与认证分离
- 启动脚本优化：带健康检查与依赖验证

### Removed
- 废弃的 `services/search/` 模块（用新版 `services/search/` 替代）
- 废弃的 `services/agent/tools/` 独立工具文件（整合到 Agent 系统）
- 旧版 `backend/main.py`（统一通过 `run.py` 启动）
- 旧版 `backend/services/` 顶层服务
- 开发计划文档（`优化计划.md`、`完成情况.md`、`当前情况.md`）

---

## [4.0.0] - 2026-04-03

### Changed

**系统样式重构**

- 配色方案从冷色调蓝色系全面改为暖色调学术风格
  - 主色调：`#007aff` → `#B8860B`（蓝色 → 暗金色）
  - 背景色：`#ffffff` → `#FAFAF6`（纯白 → 米白）
  - 文字色：`#86868b` → `#5C4033` / `#7A6E62`（灰色 → 棕色系）
  - 语义色全面调整（成功/警告/危险色）
- 字体系统新增 Playfair Display 衬线字体（学术期刊风格）
- 新增 `.paper-texture`（纸张纹理）和 `.academic-divider`（学术分隔线）设计元素
- 新增完整 CSS 变量体系（背景/文字/边框/强调/语义/阴影/渐变层级）

**页面样式更新**

- ChatPage：学术书架风格侧边栏
- Navbar：渐变背景 + 悬停展开
- PaperList：学术书房风格卡片
- KnowledgePage / WritingPage / SettingsPage：学术精致风统一

### Added

**统一聊天入口 (`/chat`)**

- 整合 RAG 问答、章节概述、深度分析、跨文档问答到单一入口
- 基于关键词的意图自动识别与路由
- 支持单论文 / 多论文选择
- 联网搜索开关

**会话管理增强**

- 会话持久化（聊天记录保存到数据库）
- 会话重命名（双击标题编辑）
- 自动命名（基于首条消息生成标题）
- 跨文档会话创建

**意图识别系统**

- 10 种意图分类：chapter_overview / deep_analysis / key_points / comparison / summary / translate / explain / cross_doc / quality_assessment / outline
- 关键词匹配 + LLM 意图识别双引擎

**WebSocket 消息类型扩展**

- `unified_chat`：统一聊天入口消息
- `intent_detected`：意图识别结果反馈
- `cancelled`：任务取消确认

**阅读辅助 API**

- `POST /api/reading/explain-term`：术语解释（SSE 流式）
- `POST /api/reading/summarize`：文本摘要（SSE 流式）
- `POST /api/reading/translate`：文本翻译（SSE 流式）

**前端组件**

- AgentProgress：Agent 执行进度展示
- ReadingAssist：阅读辅助面板（术语解释/摘要/翻译）
- PaperSelector：论文选择器

**chatStore 新增方法**

- `renameSession` / `autoNameSession` / `toggleSearch` / `setSearchStatus` / `setCrossDocPapers` / `removePaperFromCrossDoc` / `createCrossDocSession`

### Deprecated

- 论文详情页聊天入口（迁移到 `/chat` 统一入口）

### Unimplemented

- Agent 模式前端集成（后端已完成，AgentProgress 组件已实现，ChatPage 未启用）
- 阅读辅助面板集成（ReadingAssist 组件存在，PDFReader 未集成）
- 知识图谱功能（KnowledgeGraphPage 存在，功能待确认）

---

## [3.2.0] - 2026-04-01

### Added

- 统一聊天入口：所有功能聚合到 `/chat` 页面
- 论文选择支持单篇或多篇
- 基于关键词的意图识别与自动路由
- 联网搜索开关
- 会话持久化与重命名
- 导航栏调整：聊天入口置于论文库之上
- 设计系统重构：从冷色调蓝色系改为暖色调学术风格

---

## [3.1.0] - 2026-03-31

### Added

- Agent 意图识别（9 种意图分类）
- 任务规划与执行
- 多工具调用（9 个工具：search_text / summarize / translate / explain_term / extract_key_points / compare_content / generate_outline / assess_quality / get_paper_info）
- 联网搜索集成
- 跨文档问答
- 论文对比分析
- RAG 参数可配置
- 会话持久化优化

### Note

> 后端 ✅ 已完成 | 前端 ❌ 待集成

---

## [3.0.0] - 2026-03-30

### Added

- 高亮标注系统（多色标注、标注管理）
- 笔记系统（创建、编辑、关联高亮）
- 知识库管理（知识卡片、标签分类、搜索筛选）
- 写作辅助模块（大纲生成、段落生成、学术润色）
- 相似论文推荐
- 用户设置系统

---

## [2.1.0] - 2026-03-29

### Added

- 卡片弹性入场动画
- 问答逐字显示
- 论文解析去重
- Markdown 渲染
- 异步并发处理

---

## [2.0.0] - 2026-03-28

### Changed

- 重构为 WebSocket 双向通信架构
- LangChain 集成
- 断线自动重连
- 响应式布局
- 三栏拖拽调整

---

## [1.0.0] - 2026-03-27

### Added

- PDF 文件上传与预览
- 论文结构化解析
- 智能问答基础功能
- 三栏布局界面
