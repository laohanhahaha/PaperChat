"""Agent 服务模块"""
from app.services.agent.agent_service import AgentService, agent_service, Tool, ToolContext, ToolResult
from app.services.agent.react_agent import ReActAgent, react_agent
from app.services.agent.intent import (
    classify_by_keywords,
    classify_by_llm,
    classify_intent_full,
    INTENT_KEYWORDS,
)
from app.services.agent.tools import (
    SearchTextTool, ExtractKeyPointsTool, GetPaperInfoTool,
    SummarizeTool, TranslateTool, ExplainTermTool, CompareContentTool, AssessQualityTool,
    LiteratureReviewTool, CitePaperTool, PolishTextTool,
    SaveCardTool, SearchCardsTool,
    RecentPapersTool, SearchPapersTool, GenerateOutlineTool,
    DetectContradictionTool, TraceEvolutionTool, VerifyConsistencyTool,
    FindResearchGapsTool, CrossPaperReasonTool,
)

__all__ = [
    # 核心服务
    "AgentService", "agent_service",
    "Tool", "ToolContext", "ToolResult",
    "ReActAgent", "react_agent",
    # 意图识别
    "classify_by_keywords", "classify_by_llm", "classify_intent_full", "INTENT_KEYWORDS",
    # paper_tools
    "SearchTextTool", "ExtractKeyPointsTool", "GetPaperInfoTool",
    # analysis_tools
    "SummarizeTool", "TranslateTool", "ExplainTermTool", "CompareContentTool", "AssessQualityTool",
    # writing_tools
    "LiteratureReviewTool", "CitePaperTool", "PolishTextTool",
    # knowledge_tools
    "SaveCardTool", "SearchCardsTool",
    # query_tools
    "RecentPapersTool", "SearchPapersTool", "GenerateOutlineTool",
    # cross_doc_tools
    "DetectContradictionTool", "TraceEvolutionTool", "VerifyConsistencyTool",
    "FindResearchGapsTool", "CrossPaperReasonTool",
]
