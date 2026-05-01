"""Agent 工具包 — 兼容层，工具已迁移至 app.tools

所有工具类从 app.tools 各子模块重导出，保持向后兼容。
新代码请直接从 app.tools.paper_tools 等模块导入。
"""
from app.tools.paper_tools import (
    SearchTextTool,
    ExtractKeyPointsTool,
    GetPaperInfoTool,
)
from app.tools.analysis_tools import (
    SummarizeTool,
    TranslateTool,
    ExplainTermTool,
    CompareContentTool,
    AssessQualityTool,
)
from app.tools.writing_tools import (
    LiteratureReviewTool,
    CitePaperTool,
    PolishTextTool,
)
from app.tools.knowledge_tools import (
    SaveCardTool,
    SearchCardsTool,
)
from app.tools.query_tools import (
    RecentPapersTool,
    SearchPapersTool,
    GenerateOutlineTool,
)
from app.tools.cross_doc_tools import (
    DetectContradictionTool,
    TraceEvolutionTool,
    VerifyConsistencyTool,
    FindResearchGapsTool,
    CrossPaperReasonTool,
)
from app.tools.multimodal_tools import (
    MultimodalSearchTool,
)

__all__ = [
    # paper_tools
    "SearchTextTool",
    "ExtractKeyPointsTool",
    "GetPaperInfoTool",
    # analysis_tools
    "SummarizeTool",
    "TranslateTool",
    "ExplainTermTool",
    "CompareContentTool",
    "AssessQualityTool",
    # writing_tools
    "LiteratureReviewTool",
    "CitePaperTool",
    "PolishTextTool",
    # knowledge_tools
    "SaveCardTool",
    "SearchCardsTool",
    # query_tools
    "RecentPapersTool",
    "SearchPapersTool",
    "GenerateOutlineTool",
    # cross_doc_tools
    "DetectContradictionTool",
    "TraceEvolutionTool",
    "VerifyConsistencyTool",
    "FindResearchGapsTool",
    "CrossPaperReasonTool",
    # multimodal_tools
    "MultimodalSearchTool",
]
