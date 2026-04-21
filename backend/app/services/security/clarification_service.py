"""主动澄清服务

当用户意图模糊或缺少必要参数时，主动提问以获取更多信息，
避免工具因缺少参数而执行失败。

性能影响：纯规则匹配，无 LLM 调用，开销 <1ms。
"""
import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ClarificationResult:
    needs_clarification: bool = False
    questions: list = field(default_factory=list)
    missing_params: list = field(default_factory=list)
    options: list = field(default_factory=list)  # [{"label": "...", "value": "..."}]


class ClarificationService:
    """主动澄清服务：当用户意图模糊或缺少必要参数时，主动提问"""
    
    # 模糊意图模式：当消息匹配这些模式但缺少具体信息时需要澄清
    AMBIGUOUS_PATTERNS = {
        "对比": {"question": "你想对比哪些论文？", "param": "paper_ids", "options": [
            {"label": "当前打开的论文", "value": "current"},
            {"label": "最近阅读的论文", "value": "recent"},
            {"label": "自己选择", "value": "custom"}
        ]},
        "分析多篇|跨论文|多篇论文": {"question": "请指定要分析的论文范围", "param": "paper_ids", "options": [
            {"label": "当前会话的所有论文", "value": "session_all"},
            {"label": "最近阅读的 5 篇", "value": "recent_5"},
            {"label": "自己选择论文", "value": "custom"}
        ]},
        "方法演进|演进追踪": {"question": "你想追踪哪个方法的演进？请提供方法名称", "param": "method_name", "options": [
            {"label": "自己输入方法名", "value": "custom"}
        ]},
        "矛盾|一致性": {"question": "你想检测哪个主题的矛盾或一致性？", "param": "topic", "options": [
            {"label": "自己输入主题", "value": "custom"}
        ]},
        "研究空白|研究方向": {"question": "你想探索哪个研究领域的空白？", "param": "field", "options": [
            {"label": "基于当前论文的领域", "value": "current_field"},
            {"label": "自己输入领域", "value": "custom"}
        ]},
    }
    
    # 工具必需参数（从工具 schema 提取关键参数）
    TOOL_REQUIRED_PARAMS = {
        "detect_contradiction": ["paper_ids", "topic"],
        "trace_evolution": ["paper_ids", "method_name"],
        "verify_consistency": ["paper_ids", "claim"],
        "find_research_gaps": ["paper_ids", "field"],
        "cross_paper_reason": ["paper_ids", "hypothesis"],
        "compare_content": ["paper_ids"],
    }
    
    def check_clarity(self, message: str, intent: str, context: dict) -> ClarificationResult:
        """检查消息是否需要澄清
        
        Args:
            message: 用户消息
            intent: 识别到的意图（工具名）
            context: 上下文信息 {"paper_id": int|None, "paper_ids": list, "session_id": int}
        """
        result = ClarificationResult()
        
        # 1. 检查是否有论文上下文（很多操作需要论文）
        has_paper = bool(context.get("paper_id")) or bool(context.get("paper_ids"))
        
        # 2. 检查工具必需参数是否可从消息/上下文推断
        if intent in self.TOOL_REQUIRED_PARAMS:
            required = self.TOOL_REQUIRED_PARAMS[intent]
            
            # 检查 paper_ids
            if "paper_ids" in required and not has_paper:
                result.needs_clarification = True
                result.missing_params.append("paper_ids")
                result.questions.append("需要指定论文才能执行此操作")
                result.options = [
                    {"label": "最近阅读的论文", "value": "recent"},
                    {"label": "自己选择论文", "value": "custom"}
                ]
        
        # 3. 模糊意图模式匹配
        if not result.needs_clarification:
            for pattern, config in self.AMBIGUOUS_PATTERNS.items():
                if re.search(pattern, message):
                    param = config["param"]
                    # 如果需要的参数无法从上下文推断
                    if param == "paper_ids" and not has_paper:
                        result.needs_clarification = True
                        result.questions.append(config["question"])
                        result.options = config["options"]
                        result.missing_params.append(param)
                        break
                    elif param not in ("paper_ids",) and not self._can_extract_param(param, message):
                        result.needs_clarification = True
                        result.questions.append(config["question"])
                        result.options = config["options"]
                        result.missing_params.append(param)
                        break
        
        return result
    
    def _can_extract_param(self, param: str, message: str) -> bool:
        """简单检查消息中是否包含了足够的参数信息"""
        # 如果消息足够长（>30字符），通常包含了具体信息
        if len(message) > 30:
            return True
        return False
    
    def generate_clarification_message(self, result: ClarificationResult) -> dict:
        """生成 WebSocket 澄清消息"""
        question = result.questions[0] if result.questions else "请提供更多信息"
        return {
            "type": "clarification",
            "content": question,
            "options": result.options,
            "missing_params": result.missing_params
        }

    def merge_clarification(self, original_query: str, user_response: str, selected_options: list = None) -> str:
        """将用户的澄清回复合并回原始查询

        如果用户选择了预设选项，将选项内容拼接到查询中。
        如果用户自由输入，直接使用输入内容替换模糊部分。
        返回合并后的完整查询字符串。

        Args:
            original_query: 原始用户查询
            user_response: 用户澄清回复的文本
            selected_options: 用户选择的预设选项列表 [{"label": "...", "value": "..."}]

        Returns:
            合并后的完整查询字符串
        """
        if selected_options:
            # 用户选择了预设选项，将选项的 label 拼接到原始查询
            option_labels = [opt.get("label", "") for opt in selected_options if isinstance(opt, dict)]
            option_text = "、".join(label for label in option_labels if label)
            if option_text:
                return f"{original_query}（{option_text}）"

        # 用户自由输入：将输入内容追加到原始查询
        if user_response and user_response.strip():
            return f"{original_query}，{user_response.strip()}"

        # 没有有效回复，返回原始查询
        return original_query


clarification_service = ClarificationService()
