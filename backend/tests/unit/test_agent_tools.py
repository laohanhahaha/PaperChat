"""Agent 工具单元测试

测试所有 Agent 工具的：
- 基本结构（name, description 属性）
- execute 方法签名正确
- 工具 Schema 生成正确
"""
import inspect
import pytest

from app.services.core.tool_base import Tool, ToolContext, ToolResult
from app.services.agent.tools import (
    # paper_tools
    SearchTextTool,
    ExtractKeyPointsTool,
    GetPaperInfoTool,
    # analysis_tools
    SummarizeTool,
    TranslateTool,
    ExplainTermTool,
    CompareContentTool,
    AssessQualityTool,
    # writing_tools
    LiteratureReviewTool,
    CitePaperTool,
    PolishTextTool,
    # knowledge_tools
    SaveCardTool,
    SearchCardsTool,
    # query_tools
    RecentPapersTool,
    SearchPapersTool,
    GenerateOutlineTool,
    # cross_doc_tools
    DetectContradictionTool,
    TraceEvolutionTool,
    VerifyConsistencyTool,
    FindResearchGapsTool,
    CrossPaperReasonTool,
    # multimodal_tools
    MultimodalSearchTool,
)

ALL_TOOL_CLASSES = [
    SearchTextTool,
    ExtractKeyPointsTool,
    GetPaperInfoTool,
    SummarizeTool,
    TranslateTool,
    ExplainTermTool,
    CompareContentTool,
    AssessQualityTool,
    LiteratureReviewTool,
    CitePaperTool,
    PolishTextTool,
    SaveCardTool,
    SearchCardsTool,
    RecentPapersTool,
    SearchPapersTool,
    GenerateOutlineTool,
    DetectContradictionTool,
    TraceEvolutionTool,
    VerifyConsistencyTool,
    FindResearchGapsTool,
    CrossPaperReasonTool,
    MultimodalSearchTool,
]


@pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
def test_tool_inherits_from_base(tool_cls):
    assert issubclass(tool_cls, Tool)


@pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
def test_tool_has_name(tool_cls):
    assert hasattr(tool_cls, "name")
    assert isinstance(tool_cls.name, str)
    assert len(tool_cls.name) > 0


@pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
def test_tool_has_description(tool_cls):
    assert hasattr(tool_cls, "description")
    assert isinstance(tool_cls.description, str)
    assert len(tool_cls.description) > 0


@pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
def test_tool_has_execute_method(tool_cls):
    assert hasattr(tool_cls, "execute")
    assert callable(tool_cls.execute)


@pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
def test_execute_is_coroutine(tool_cls):
    assert inspect.iscoroutinefunction(tool_cls.execute), (
        f"{tool_cls.__name__}.execute 必须是 async def"
    )


@pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
def test_execute_first_param_is_ctx(tool_cls):
    sig = inspect.signature(tool_cls.execute)
    params = list(sig.parameters.keys())
    assert len(params) >= 2
    assert params[1] == "ctx", (
        f"{tool_cls.__name__}.execute 第一个参数应为 ctx，实际为 {params[1]}"
    )


def test_all_tool_names_unique():
    names = [cls.name for cls in ALL_TOOL_CLASSES]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
def test_tool_schema_structure(tool_cls):
    tool = tool_cls()
    schema = tool.get_schema()
    assert isinstance(schema, dict)
    assert "name" in schema
    assert "description" in schema
    assert "parameters" in schema
    assert schema["name"] == tool_cls.name
    assert schema["description"] == tool_cls.description


def test_tool_context_defaults():
    ctx = ToolContext()
    assert ctx.db is None
    assert ctx.paper_id is None
    assert ctx.paper_ids == []
    assert ctx.user_id is None
    assert ctx.session_id is None


def test_tool_context_with_values():
    ctx = ToolContext(paper_id=42, user_id=1, session_id=10)
    assert ctx.paper_id == 42
    assert ctx.user_id == 1
    assert ctx.session_id == 10


def test_tool_result_success_default():
    result = ToolResult()
    assert result.success is True
    assert result.data == {}
    assert result.error is None


def test_tool_result_failure():
    result = ToolResult(success=False, error="something went wrong")
    assert result.success is False
    assert result.error == "something went wrong"


def test_tool_result_with_data():
    result = ToolResult(success=True, data={"count": 5})
    assert result.data["count"] == 5


def test_all_tools_count():
    assert len(ALL_TOOL_CLASSES) == 23
    assert result.data["count"] == 5


def test_all_tools_count():
    assert len(ALL_TOOL_CLASSES) == 23
