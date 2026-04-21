from typing import Dict, List, Optional
from app.skills.base import BaseSkill


class SkillRegistry:
    """Skill 注册中心 — 统一管理与发现所有可用 Skill"""

    def __init__(self) -> None:
        self._skills: Dict[str, BaseSkill] = {}

    # ------------------------------------------------------------------
    # 注册 / 查询
    # ------------------------------------------------------------------

    def register(self, skill: BaseSkill) -> None:
        """注册一个 Skill（重复注册会覆盖旧实例）"""
        self._skills[skill.name] = skill

    def unregister(self, name: str) -> bool:
        """取消注册，返回是否存在"""
        if name in self._skills:
            del self._skills[name]
            return True
        return False

    def get(self, name: str) -> Optional[BaseSkill]:
        """按名称获取 Skill，不存在返回 None"""
        return self._skills.get(name)

    def list_skills(self) -> List[BaseSkill]:
        """返回所有已注册 Skill 实例列表"""
        return list(self._skills.values())

    # ------------------------------------------------------------------
    # 意图匹配
    # ------------------------------------------------------------------

    def match_by_tags(self, tags: List[str]) -> List[BaseSkill]:
        """根据标签集合匹配可用 Skill（任意标签命中即入选）

        Args:
            tags: 查询标签列表，如 ["review", "literature"]

        Returns:
            匹配到的 Skill 列表（可能为空）
        """
        matched: List[BaseSkill] = []
        for skill in self._skills.values():
            if any(tag in skill.tags for tag in tags):
                matched.append(skill)
        return matched

    # ------------------------------------------------------------------
    # 元信息
    # ------------------------------------------------------------------

    def get_descriptions(self) -> List[Dict]:
        """获取所有 Skill 的描述列表（供 LLM 进行 Skill 选择）

        Returns:
            格式::

                [
                    {
                        "name": "literature_review",
                        "description": "...",
                        "steps": 3,
                        "tags": ["review", "literature"]
                    },
                    ...
                ]
        """
        return [
            {
                "name": s.name,
                "description": s.description,
                "steps": len(s.steps),
                "tags": s.tags,
            }
            for s in self._skills.values()
        ]

    def __len__(self) -> int:
        return len(self._skills)

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __repr__(self) -> str:
        names = list(self._skills.keys())
        return f"<SkillRegistry skills={names}>"
