"""多 Agent 研究助手通信协议类型定义

定义 Orchestrator 与 Sub-Agent 之间的数据结构，包括：
- AgentRole: 角色枚举
- ResearchTask: 子任务描述
- ResearchPlan: 研究计划（由协调器分解）
- SubAgentResult: 子 Agent 执行结果
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class AgentRole(str, Enum):
    """Agent 角色枚举"""
    ORCHESTRATOR = "orchestrator"   # 协调器：分解任务、汇总结果
    RETRIEVER = "retriever"         # 检索器：从论文库定位信息
    ANALYZER = "analyzer"           # 分析器：评估论点、方法论
    RECOMMENDER = "recommender"     # 推荐器：发现研究空白、建议方向
    CUSTOM = "custom"               # 动态创建的自定义角色


@dataclass
class ResearchTask:
    """子 Agent 的单个任务

    Attributes:
        task_id: 任务唯一标识符（由协调器分配）
        task_type: 任务类型，取值 "retrieve" | "analyze" | "recommend" | "custom"
        query: 子任务的具体问题或指令
        required_tools: 限制该任务可使用的工具列表（空列表表示不限制）
        depends_on: 依赖的其他任务 ID 列表，依赖任务完成后才可执行
        agent_name: 子智能体显示名称（如 "文献综述专家"）
        agent_prompt: 自定义系统提示词（空 = 按 task_type 用预置）
        agent_icon: 前端图标标识（可选）
    """
    task_id: str
    task_type: str                          # "retrieve" | "analyze" | "recommend" | "custom"
    query: str                              # 子任务的具体问题
    required_tools: List[str] = field(default_factory=list)   # 限制可用的工具列表
    depends_on: List[str] = field(default_factory=list)       # 依赖的其他任务 ID
    agent_name: str = ""                    # 子智能体显示名称（如 "文献综述专家"）
    agent_prompt: str = ""                  # 自定义系统提示词（空 = 按 task_type 用预置）
    agent_icon: str = ""                    # 前端图标标识（可选）


@dataclass
class ResearchPlan:
    """协调器分解出的研究计划

    Attributes:
        research_question: 原始研究问题（来自用户）
        tasks: 分解后的子任务列表，按执行顺序排列
        metadata: 附加元数据（如优先级、预估复杂度等）
    """
    research_question: str
    tasks: List[ResearchTask]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_task_by_id(self, task_id: str) -> Optional[ResearchTask]:
        """根据 task_id 查找任务"""
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None

    def get_ready_tasks(self, completed_ids: List[str]) -> List[ResearchTask]:
        """获取当前可执行的任务（依赖已全部完成）

        Args:
            completed_ids: 已完成任务 ID 列表

        Returns:
            满足依赖条件的待执行任务列表
        """
        ready = []
        completed_set = set(completed_ids)
        for task in self.tasks:
            if task.task_id in completed_set:
                continue  # 已完成，跳过
            if all(dep in completed_set for dep in task.depends_on):
                ready.append(task)
        return ready


@dataclass
class SubAgentResult:
    """子 Agent 执行结果

    Attributes:
        task_id: 对应的任务 ID
        role: 执行该任务的 Agent 角色（AgentRole 枚举值）
        success: 是否执行成功
        findings: 主要发现（面向 Orchestrator 的摘要）
        evidence: 支撑证据列表（直接引用或数据片段）
        error: 执行失败时的错误信息
        raw_steps: 执行过程的原始步骤（可选，用于调试）
    """
    task_id: str
    role: str                                           # AgentRole value
    success: bool
    findings: str                                       # 主要发现
    evidence: List[str] = field(default_factory=list)  # 支撑证据
    error: Optional[str] = None                        # 失败时的错误信息
    raw_steps: List[Dict[str, Any]] = field(default_factory=list)  # 调试用原始步骤


@dataclass
class ResearchContext:
    """跨子 Agent 共享的研究上下文

    Orchestrator 在调度过程中维护此对象，用于在子任务间传递中间结果。

    Attributes:
        plan: 当前研究计划
        results: 已完成任务的结果，键为 task_id
        shared_facts: 跨任务共享的事实片段（检索器提取后供分析器使用）
    """
    plan: ResearchPlan
    results: Dict[str, SubAgentResult] = field(default_factory=dict)
    shared_facts: List[str] = field(default_factory=list)

    def add_result(self, result: SubAgentResult) -> None:
        """记录子任务执行结果"""
        self.results[result.task_id] = result
        if result.success and result.evidence:
            self.shared_facts.extend(result.evidence)

    def get_completed_ids(self) -> List[str]:
        """返回所有已完成的任务 ID 列表"""
        return list(self.results.keys())

    def is_plan_complete(self) -> bool:
        """判断研究计划是否全部完成"""
        all_ids = {task.task_id for task in self.plan.tasks}
        return all_ids.issubset(set(self.get_completed_ids()))
