"""提示词注入防护服务

检测并过滤用户输入中的注入攻击，保护 Agent 安全。
"""
import re
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SecurityCheckResult:
    """安全检查结果"""
    is_safe: bool = True
    risk_level: str = "none"  # none / low / medium / high
    reason: Optional[str] = None
    sanitized_input: Optional[str] = None  # 清洗后的输入


# 常见注入模式（正则表达式）
INJECTION_PATTERNS = [
    # 角色覆盖类
    (r"(?i)(ignore|disregard|forget)\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)", "high", "尝试覆盖系统指令"),
    (r"(?i)you\s+are\s+now\s+", "high", "尝试角色覆盖"),
    (r"(?i)act\s+as\s+(if\s+you\s+are|a)\s+", "medium", "尝试角色扮演"),
    (r"(?i)pretend\s+(to\s+be|you\s+are)", "medium", "尝试角色伪装"),
    (r"(?i)new\s+instructions?:", "high", "尝试注入新指令"),
    # system prompt 提取类
    (r"(?i)(show|reveal|display|print|output|repeat)\s+(your|the|system)\s+(prompt|instructions?|rules?)", "high", "尝试提取系统提示词"),
    (r"(?i)what\s+(are|is)\s+your\s+(instructions?|system\s+prompt|rules?)", "medium", "尝试查询系统设定"),
    # 分隔符注入
    (r"(?i)(---+|===+|###)\s*(system|assistant|human|user)\s*:", "high", "消息分隔符注入"),
    # 编码绕过
    (r"(?i)base64|\\x[0-9a-f]{2}|\\u[0-9a-f]{4}", "low", "可能的编码绕过"),
    # 中文注入模式
    (r"(忽略|无视|不要管|丢掉).{0,10}(之前|上面|以上|前面).{0,10}(指令|规则|要求|提示)", "high", "尝试覆盖系统指令（中文）"),
    (r"从现在开始你是", "high", "尝试角色覆盖（中文）"),
    (r"(假装|扮演|模拟).{0,5}(你是|自己是)", "medium", "尝试角色伪装（中文）"),
    (r"(显示|输出|打印|告诉我).{0,10}(系统提示词|系统指令|system prompt)", "high", "尝试提取系统提示词（中文）"),
    (r"(你的|系统的)(指令|规则|提示词)是什么", "medium", "尝试查询系统设定（中文）"),
]

# 工具风险等级
TOOL_RISK_LEVELS = {
    # 低风险 - 只读操作
    "search_text": "low",
    "extract_key_points": "low",
    "summarize": "low",
    "translate": "low",
    "explain_term": "low",
    "get_paper_info": "low",
    "compare_content": "low",
    "generate_outline": "low",
    "assess_quality": "low",
    "literature_review": "low",
    "cite_paper": "low",
    "polish_text": "low",
    "search_cards": "low",
    "recent_papers": "low",
    "search_papers": "low",
    # 中风险 - 写入操作
    "save_card": "medium",
}

# 风险等级优先级
RISK_PRIORITY = {"none": 0, "low": 1, "medium": 2, "high": 3}

# 输出敏感关键词
SENSITIVE_OUTPUT_PATTERNS = [
    r"(?i)system\s+prompt",
    r"(?i)系统提示词",
    r"(?i)你的指令",
]


class SecurityService:
    """提示词注入防护服务"""

    def check_input(self, user_input: str) -> SecurityCheckResult:
        """检查用户输入是否安全
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            SecurityCheckResult: 安全检查结果
        """
        if not user_input:
            return SecurityCheckResult(is_safe=True, risk_level="none")

        highest_risk = "none"
        reasons = []

        for pattern, risk_level, reason in INJECTION_PATTERNS:
            if re.search(pattern, user_input):
                # 记录匹配到的风险
                if RISK_PRIORITY[risk_level] > RISK_PRIORITY[highest_risk]:
                    highest_risk = risk_level
                reasons.append(f"[{risk_level}] {reason}")

                # 根据风险等级记录日志
                if risk_level == "high":
                    logger.warning(f"检测到高风险注入: {reason}, 输入片段: {user_input[:100]}...")
                elif risk_level == "medium":
                    logger.warning(f"检测到中风险注入: {reason}")
                elif risk_level == "low":
                    logger.debug(f"检测到潜在风险: {reason}")

        is_safe = highest_risk != "high"
        sanitized = self.sanitize_input(user_input) if highest_risk == "high" else user_input

        return SecurityCheckResult(
            is_safe=is_safe,
            risk_level=highest_risk,
            reason="; ".join(reasons) if reasons else None,
            sanitized_input=sanitized
        )

    def check_tool_permission(self, tool_name: str, user_input: str) -> SecurityCheckResult:
        """检查工具调用权限
        
        Args:
            tool_name: 工具名称
            user_input: 用户输入（用于上下文分析）
            
        Returns:
            SecurityCheckResult: 权限检查结果
        """
        risk_level = TOOL_RISK_LEVELS.get(tool_name, "medium")
        
        if risk_level == "high":
            logger.warning(f"尝试调用高风险工具: {tool_name}")
            return SecurityCheckResult(
                is_safe=False,
                risk_level="high",
                reason=f"工具 '{tool_name}' 为高风险操作"
            )
        elif risk_level == "medium":
            logger.info(f"调用中风险工具: {tool_name}")
            return SecurityCheckResult(
                is_safe=True,
                risk_level="medium",
                reason=f"工具 '{tool_name}' 为中风险操作，已允许执行"
            )
        else:
            logger.debug(f"调用低风险工具: {tool_name}")
            return SecurityCheckResult(
                is_safe=True,
                risk_level="low",
                reason=f"工具 '{tool_name}' 为低风险操作"
            )

    def check_output(self, llm_output: str) -> SecurityCheckResult:
        """检查 LLM 输出是否安全（防止 prompt 泄露）
        
        Args:
            llm_output: LLM 生成的输出文本
            
        Returns:
            SecurityCheckResult: 安全检查结果
        """
        if not llm_output:
            return SecurityCheckResult(is_safe=True, risk_level="none")

        reasons = []
        
        # 检测敏感关键词
        for pattern in SENSITIVE_OUTPUT_PATTERNS:
            if re.search(pattern, llm_output):
                reasons.append("输出包含敏感关键词")
                logger.warning("检测到 LLM 输出可能包含系统提示词泄露")
                break

        # 检测连续工具名称（可能泄露工具列表）
        tool_names = list(TOOL_RISK_LEVELS.keys())
        tool_pattern = r"(?i)(" + "|".join(tool_names) + r")"
        tool_matches = re.findall(tool_pattern, llm_output)
        
        # 如果连续出现3个及以上工具名称，可能是工具列表泄露
        if len(tool_matches) >= 3:
            # 检查是否集中在短文本内
            if len(llm_output) < 500:
                reasons.append("输出可能包含工具列表泄露")
                logger.warning(f"检测到可能的工具列表泄露: {len(tool_matches)} 个工具名称")

        if reasons:
            return SecurityCheckResult(
                is_safe=False,
                risk_level="high",
                reason="; ".join(reasons),
                sanitized_input="[系统检测到敏感信息，输出已被拦截]"
            )

        return SecurityCheckResult(is_safe=True, risk_level="none")

    def sanitize_input(self, user_input: str) -> str:
        """清洗用户输入，移除高风险模式
        
        Args:
            user_input: 原始用户输入
            
        Returns:
            str: 清洗后的输入
        """
        if not user_input:
            return user_input

        sanitized = user_input
        removed_patterns = []

        # 只移除高风险模式
        for pattern, risk_level, reason in INJECTION_PATTERNS:
            if risk_level == "high":
                matches = re.findall(pattern, sanitized)
                if matches:
                    removed_patterns.append(reason)
                    sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)

        # 清理多余空白
        sanitized = re.sub(r"\s+", " ", sanitized).strip()

        if removed_patterns:
            logger.info(f"已清洗高风险注入模式: {', '.join(removed_patterns)}")

        return sanitized


# 全局单例
security_service = SecurityService()
