# Spec: PaperChat Phase 5 — 平台能力增强与质量修复

## Objective

**现状**：Phase 4 已完成 ConfigAgent、MCP 学术服务器集群、多源搜索调度、引用管理集成、结构化报告生成等外部服务集成。Phase A（质量问题修复）已完成，B3 多模态理解已通过统一 LLM 方式实现。

## 多模态相关审计结果

| 检查项 | 状态 | 说明 |
|--------|------|------|
| B3 多模态理解 | ✅ 已完成 | `chat_with_image()`/`analyze_chart()`/`extract_formula()`/`extract_table()` 均使用 `_default_llm` |
| `use_cloud=True` 参数残留 | ❌ 4 处需清理 | `multimodal_tools.py:160`、`test_multimodal_tools.py:178`、`test_multimodal_config.py:66/80`、`multimodal_eval.py:338` — 重构后该参数已不存在 |
| `test_multimodal_config.py` | ❌ 需删除 | 测试旧版 cloud/local 双路径，该逻辑已删除 |
| QWEN_API_KEY 配置 | ✅ 已删除 | 全部 QWEN_* 配置项和代码路径已清除 |
| 兼容层 `services/llm_service.py` | ✅ 正常运行 | 作为 re-export 兼容层存在，不影响功能 |

**结论**：多模态功能（B3）核心逻辑已完成，`use_cloud` 参数残留是 Phase A 重构未同步清理的遗留问题。这些残留不阻塞功能开发，但会导致 MultimodalSearchTool 在运行时崩溃。

**目标**：完成 Phase B 剩余功能开发。

**两个阶段**：

| 阶段 | 内容 | 状态 |
|------|------|------|
| **Phase A** | 修复现有质量问题 + 清理死亡代码 | ✅ 全部完成 |
| **Phase B** | Phase 5 功能开发（B2/B1/B4/B5/B6） | ✅ 全部完成 |

**成功标准**：
- 联网搜索功能可正常返回结果 ✅
- MCP 学术服务首次启动即自动启用（免费服务） ✅
- 前端无 404 路由错误 ✅
- PDF 上传正常工作 ✅
- 图表/公式/表格解析正常工作 ✅（统一 LLM）
- RAG 增强后检索质量提升
- 智能路由按用户偏好/预算正确路由
- 离线模式可用
- 多模态搜索（图片→搜索）正常流转

---

## Tech Stack

| 堆栈 | 技术 | 版本 |
|------|------|------|
| 后端框架 | FastAPI (Python) | 3.12 |
| 前端框架 | React + Vite | JSX/TS |
| LLM SDK | LangChain (ChatOpenAI) | — |
| 向量数据库 | ChromaDB | — |
| 数据库 | SQLite (开发) / PostgreSQL (生产) | — |
| 搜索集群 | SearchDispatcher (6 适配器) | — |
| MCP 协议 | JSON-RPC over STDIO | — |
| LLM 模型 | DeepSeek (deepseek-v4-flash) | — |

---

## 更新：设计决策确认

| 决策 | 说明 |
|------|------|
| 模型名 | `deepseek-v4-flash` 是正确的，`deepseek-chat` 和 `deepseek-reasoner` 将被废弃 |
| 多模态策略 | **统一 LLM** — 用户配置什么模型就用什么模型。不支持独立的多模态 provider。模型有视觉能力就能处理图表/公式/表格，没有就不能。不设 fallback，不设额外配置。**B3 已于 A5-3 完成** |
| 修复优先 | 先修质量 bug，再开发 Phase 5 新功能 ✅ Phase A 全部完成 |
| 死亡代码 | WigoloAdapter、`backend/main.py`、`services/llm_service.py`、QWEN_API_KEY 全部路径均已删除 ✅ |

---

## Phase A — 质量问题修复 ✅ 全部完成

### A1. 修复联网搜索功能

**问题**：6 个搜索源中 5 个不可用（Bing/Tavily/Brave 缺 API Key、Wigolo 虚构 API、DuckDuckGo 被屏蔽），百度 HTML 解析脆弱。

**修复完成**：
1. ✅ 删除 WigoloAdapter（虚构 API）
2. ✅ 首次启动时自动启用免费 MCP 学术搜索
3. ✅ 搜索失败时返回友好错误提示
4. ✅ 搜索网络检测改为多 URL 探测（baidu.com + google.com + arxiv.org）
5. ✅ 搜索健康检查改为探测所有已注册适配器

### A2. 免费 MCP 服务首次自动启用 ✅

**问题**：6 个 MCP 服务器全部 `enabled=False`，首次用户无配置。

**修复完成**：在 `_load_mcp_config_from_db` 中首次加载时自动启用 arxiv/crossref/dblp 并持久化。

### A3. 添加缺失的后端路由 ✅

**问题**：前端调用了 3 个不存在的后端路由。

**修复完成**：
- ✅ `GET /citations/{paper_id}` — 返回单篇论文引用
- ✅ `GET /notes/export` + `POST /notes/export/batch` — 笔记导出

### A4. 修复文件上传 Content-Type ✅

**问题**：前端硬编码 `Content-Type: multipart/form-data` 缺少 boundary。

**修复完成**：删除前端 `paperApi.ts` 中 3 处手动设置。

### A5. 删除死亡代码 + 废弃 Qwen 路径 ✅

**修复完成**：
- ✅ 删除 WigoloAdapter、`backend/main.py`、`backend/services/llm_service.py`
- ✅ 删除 `QWEN_API_KEY` 等全部 Qwen 配置和代码路径
- ✅ 重构 `chat_with_image()` 为统一 `_default_llm`（base64 image_url 发送）

### A6. 完善 `.env.example` ✅

**修复完成**：补充搜索/MCP/RAG/路由/预缓存等完整配置段（不含 QWEN_API_KEY）。

### A7. Docker healthcheck 修复 ✅

**修复完成**：Dockerfile 安装 curl。

### A8. ChatOpenAI 添加请求超时 ✅

**修复完成**：3 处 ChatOpenAI 构造函数添加 `request_timeout=120`。

---

## Phase B — Phase 5 功能开发

### B1. 智能路由与成本控制引擎 ✅ 已完成

**状态**：ModelRouter 已从 `llm_service.py` 提取到独立包，REST API 已创建。

**完成内容**：
- `backend/app/services/routing/route_engine.py` — 核心路由逻辑（隐私检查 + 复杂度路由 + 预算感知）
- `backend/app/services/routing/__init__.py` — 包导出
- `backend/app/routers/routing.py` — REST API（GET/PUT 配置 + POST 路由决策）
- `backend/app/services/llm/llm_service.py` — 移除内联 ModelRouter 类，改为 re-export

### B2. RAG 增强（Reranker + HyDE + 混合检索）

**功能**：
- Reranker：对 ChromaDB 检索结果重新排序（cross-encoder）
- HyDE：生成假设文档再检索，提升查询覆盖率
- 混合检索：BM25 关键词 + ChromaDB 向量检索加权融合
- RAG 服务重构：集成这三个增强模块

**涉及文件**：
- `backend/app/services/rag/reranker.py` — 重排序
- `backend/app/services/rag/hyde.py` — HyDE
- `backend/app/services/rag/hybrid_search.py` — 混合检索
- `backend/app/services/rag/rag_service.py` — 主服务接入

### B3. 多模态论文理解 ✅ 已完成（Phase A5-3）

**状态**：已于 A5-3 通过统一 LLM 实现。`chat_with_image()`、`analyze_chart()`、`extract_formula()`、`extract_table()` 均使用 `_default_llm` 以 base64 image_url 发送。不再需要任何额外开发。

**遗留清理**（待代码修复）：
- `app/tools/multimodal_tools.py:160` — 删除 `use_cloud=True` 参数
- `tests/unit/test_multimodal_tools.py:178` — 删除 `use_cloud=True` 参数
- `tests/unit/test_multimodal_config.py` — 整个文件可删除（测试旧版 cloud/local 双路径，逻辑已不存在）
- `tests/benchmarks/multimodal_eval.py:13,338` — 删除 `use_cloud` 引用

### B4. 多模态搜索 ✅ 已完成

**状态**：原代码已存在，`use_cloud=True` 参数残留已清除，MultimodalSearchTool 正常工作。

**完成内容**：
- `backend/app/tools/multimodal_tools.py` — 删除 `use_cloud=True` 参数
- `backend/tests/unit/test_multimodal_tools.py` — 删除 `use_cloud=True` 参数
- `backend/tests/unit/test_multimodal_config.py` — 删除已废弃的测试类
- `backend/tests/benchmarks/multimodal_eval.py` — 删除 `use_cloud` 引用

### B5. 离线优先与主动预缓存 ✅ 已完成

**状态**：PrecacheService 已存在且完整，现已在 lifespan 中启动/停止。

**完成内容**：
- `backend/app/main.py` — 在 lifespan 的启动和关闭阶段添加 `precache_service.start()` / `precache_service.stop()`

### B6. 大规模验证测试 ✅ 已完成

**状态**：38 个测试全部通过，覆盖路由/RAG/搜索/多模态四大模块。

**完成内容**：
- `backend/tests/unit/test_smart_routing.py` — 重写适配新 ModelRouter 的 7 个测试
- `backend/tests/integration/test_routing_api.py` — 路由 REST API 注册 + 配置/决策端点 7 个测试
- `backend/tests/integration/test_search_integration.py` — 搜索调度器多源融合/降级/离线检测 11 个测试
- `backend/tests/integration/test_rag_enhanced.py` — RAG 分块/Search/BM25 缓存 8 个测试
- `backend/tests/integration/test_multimodal_integration.py` — 多模态工具调用链 5 个测试
- 发现并修复：`llm_service.py` 缺少模块级单例、`notes.py` 缺少 BaseModel 导入

---

## Commands

```bash
# 后端 - 开发
cd backend
uvicorn app.main:app --reload --port 8000

# 后端 - 运行（正式）
python run.py

# 前端 - 开发
cd frontend
npm run dev

# 测试
cd backend && pytest -xvs

# 测试（带覆盖率）
cd backend && pytest --cov=app --cov-report=term-missing

# 类型检查
cd frontend && npx tsc --noEmit

# Lint
cd backend && black --check app/ && isort --check-only app/
cd frontend && npm run lint

# Docker
docker-compose up --build
```

---

## Project Structure

```
backend/
├── app/
│   ├── services/
│   │   ├── rag/
│   │   │   ├── rag_service.py        # RAG 主服务（增强）
│   │   │   ├── reranker.py           # [新增] 重排序
│   │   │   ├── hyde.py               # [新增] HyDE
│   │   │   └── hybrid_search.py      # [新增] 混合检索
│   │   ├── routing/
│   │   │   ├── route_engine.py       # [新增] 路由引擎
│   │   │   ├── cost_tracker.py       # [新增] 成本追踪
│   │   │   └── budget_service.py     # [新增] 预算管理
│   │   ├── offline/                  # [新增] 离线服务
│   │   │   ├── offline_queue.py      # 离线队列
│   │   │   └── precache_manager.py   # 预缓存管理
│   │   ├── llm/llm_service.py       # ✅ 统一 LLM（B3 已完成）
│   │   └── search/
│   │       └── dispatcher.py         # ✅ 多 URL 网络检测 + 友好错误消息
│   ├── tools/
│   │   └── multimodal_tools.py       # MultimodalSearchTool 已存在（需清除 use_cloud）
│   ├── routers/
│   │   ├── citations.py             # ✅ 新增 GET /{paper_id}
│   │   ├── notes.py                 # ✅ 新增 /export 路由
│   │   └── routing.py               # [新增] 路由控制 API
│   └── models/
│       ├── budget.py                # [新增] 预算模型
│       └── routing_config.py        # [新增] 路由配置模型
├── .env.example                     # ✅ 完善环境变量
├── Dockerfile                       # ✅ 修复 healthcheck
└── docker-compose.yml               # 修复 healthcheck
```

---

## Code Style

```python
# 后端风格：类型注解 + 清晰命名 + 单行 docstring
async def search_with_fallback(
    query: str,
    max_results: int = 5,
    source: str = "auto",
) -> list[SearchResult]:
    """多源搜索，失败自动降级"""
    if source == "auto":
        sources = await self._select_available_sources()
    else:
        sources = [source]

    results = await asyncio.gather(
        *[self._search(s, query, max_results) for s in sources],
        return_exceptions=True,
    )
    return self._merge([r for r in results if isinstance(r, list)])
```

```typescript
// 前端风格：TypeScript strict + hook 模式 + 干净的空行
export function useChatSearch() {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);

  const search = useCallback(async (query: string) => {
    setLoading(true);
    try {
      const { data } = await searchApi.search(query);
      setResults(data);
    } finally {
      setLoading(false);
    }
  }, []);

  return { results, loading, search };
}
```

---

## Testing Strategy

| 层级 | 框架 | 位置 | 覆盖要求 |
|------|------|------|----------|
| 单元测试 | pytest (asyncio) | `backend/tests/` | 核心服务 ≥ 80% |
| 集成测试 | pytest + httpx | `backend/tests/` | 端到端流程 ≥ 1 test/feature |
| 前端 | Jest/Vitest | `frontend/src/test/` | Store + API ≥ 60% |

Phase A 各修复项需要对应的回归测试：
- 搜索调度测试（模拟各源可用/不可用）
- MCP 配置加载测试（首次/有配置/部分配置）
- 新增路由的集成测试
- 文件上传测试

Phase B 各功能模块需要：
- 单元测试覆盖核心逻辑
- 集成测试覆盖 HTTP API 端点
- 性能测试覆盖搜索/RAG 延迟

---

## Boundaries

### Always do
- 修改前先运行 `pytest -xvs` 确保不破坏已有测试
- 新建服务/路由时添加测试
- 删除代码前确认无其他引用
- 修复搜索相关功能时验证多个网络环境

### Ask first
- 新增外部依赖（pip install / npm install）
- 数据库 schema 变更
- 修改 CI/CD 配置
- 新增 MCP Server 或搜索源适配器
- 修改核心架构（StartupManager / DI / EventBus）

### Never do
- 提交 API Key 或敏感凭据（已验证 .env 已 gitignored）
- 删除没有测试覆盖的代码而不补测试
- 跳过前端的 TypeScript 类型检查
- 一次性提交超过 20 个文件的变更（拆成多个 PR）

---

## 开发顺序

```
Phase A（先修 bug）
  ├── A5: 删除死亡代码（无风险，可立即执行）
  ├── A4: 修复前端 Content-Type（单行改动）
  ├── A3: 添加缺失路由（新增代码，不影响已有功能）
  ├── A8: ChatOpenAI 超时设置（单行改动）
  ├── A2: MCP 首次自动启用（增强现有逻辑）
  ├── A1: 搜索功能修复（核心修复，需验证）
  ├── A6: .env.example 完善
  └── A7: Docker healthcheck 修复

Phase B（Phase 5 功能）
  ├── B2: RAG 增强 ✅（已预先实现，无需额外开发）
  ├── B1: 智能路由与成本控制 ✅ 已完成
  ├── B3 遗留清理 ✅ 已完成
  ├── B4: 多模态搜索 ✅ 已完成
  ├── B5: 离线优先与预缓存 ✅ 已完成
  └── B6: 大规模验证测试 — 当前任务
```
