"""内置 Skill 包 — 开箱即用的学术工作流"""
from app.skills.builtin.literature_review import LiteratureReviewSkill
from app.skills.builtin.paper_analysis import PaperAnalysisSkill

__all__ = [
    "LiteratureReviewSkill",
    "PaperAnalysisSkill",
]
