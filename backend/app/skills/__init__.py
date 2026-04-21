"""app.skills — Skill 工作流编排框架

公开接口：
    BaseSkill          抽象基类
    SkillStep          步骤定义数据类
    SkillContext       执行上下文数据类
    SkillResult        执行结果数据类
    SkillRegistry      注册与发现中心
    LiteratureReviewSkill  内置：文献综述 Skill
    PaperAnalysisSkill     内置：论文深度分析 Skill
"""
from app.skills.base import BaseSkill, SkillContext, SkillResult, SkillStep
from app.skills.registry import SkillRegistry
from app.skills.builtin.literature_review import LiteratureReviewSkill
from app.skills.builtin.paper_analysis import PaperAnalysisSkill

__all__ = [
    # 核心框架
    "BaseSkill",
    "SkillStep",
    "SkillContext",
    "SkillResult",
    "SkillRegistry",
    # 内置 Skill
    "LiteratureReviewSkill",
    "PaperAnalysisSkill",
]
