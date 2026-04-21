from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class SkillStep:
    """Skill 中的单个步骤"""
    name: str                               # 步骤名称
    tool_name: str                          # 要调用的工具名
    description: str                        # 步骤描述
    params_template: Dict[str, Any] = field(default_factory=dict)  # 参数模板
    optional: bool = False                  # 是否可选步骤
    condition: Optional[str] = None         # 执行条件表达式（如 "ctx.paper_id is not None"）


@dataclass
class SkillContext:
    """Skill 执行上下文 — 在步骤间传递状态"""
    user_query: str
    paper_id: Optional[str] = None
    paper_ids: List[str] = field(default_factory=list)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    db: Any = None                          # 数据库会话（由调用方注入）
    variables: Dict[str, Any] = field(default_factory=dict)  # 步骤间传递的变量


@dataclass
class SkillResult:
    """Skill 执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    steps_completed: int = 0
    total_steps: int = 0

    @property
    def is_partial(self) -> bool:
        """是否部分完成"""
        return self.steps_completed > 0 and self.steps_completed < self.total_steps


class BaseSkill(ABC):
    """Skill 抽象基类 — 多步骤工作流编排器

    子类需实现：
    - name:        唯一标识符
    - description: 功能描述（供 LLM 选择）
    - steps:       步骤定义列表（声明式，不含执行逻辑）
    - execute:     实际执行入口
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Skill 唯一标识符"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Skill 功能描述（供 LLM 选择）"""
        ...

    @property
    @abstractmethod
    def steps(self) -> List[SkillStep]:
        """步骤定义列表（声明式，描述工作流结构）"""
        ...

    @property
    def tags(self) -> List[str]:
        """用于意图匹配的标签（可选覆盖）"""
        return []

    @abstractmethod
    async def execute(self, ctx: SkillContext) -> SkillResult:
        """执行完整 Skill 工作流

        Args:
            ctx: 执行上下文，包含用户查询、论文 ID、数据库会话等

        Returns:
            SkillResult，包含执行结果与步骤统计
        """
        ...

    async def on_step_complete(
        self,
        step: SkillStep,
        result: Any,
        ctx: SkillContext,
    ) -> None:
        """步骤完成回调（可选覆盖）

        Args:
            step:   刚完成的步骤定义
            result: 该步骤的执行结果
            ctx:    当前执行上下文
        """
        pass

    async def on_error(
        self,
        step: SkillStep,
        error: Exception,
        ctx: SkillContext,
    ) -> Optional[SkillResult]:
        """错误处理钩子（可选覆盖）

        Args:
            step:  出错的步骤
            error: 捕获到的异常
            ctx:   当前执行上下文

        Returns:
            返回 SkillResult 以提前结束并使用该结果；
            返回 None 则向上传播异常并中止执行。
        """
        return None
