"""人机协作确认服务

当用户意图涉及高风险操作时，主动发送确认请求，等待用户确认后再执行。
状态通过 WebSocket 消息传递，不修改 Session 模型。

性能影响：纯规则匹配，无 LLM 调用，开销 <1ms。
"""
import logging

logger = logging.getLogger(__name__)


class ConfirmationService:
    """人机协作确认服务：高风险操作需用户确认后才执行"""

    HIGH_RISK_ACTIONS = {
        'delete_paper': {
            'description': '删除论文将清除所有相关数据（笔记、高亮、索引）',
            'level': 'high',
        },
        'batch_delete': {
            'description': '批量删除将影响多篇论文',
            'level': 'high',
        },
        'clear_history': {
            'description': '清除对话历史将不可恢复',
            'level': 'high',
        },
        'batch_analyze': {
            'description': '批量分析将消耗较多资源',
            'level': 'medium',
        },
    }

    # 意图到高风险动作的映射关键词
    INTENT_ACTION_MAP = {
        'delete_paper': 'delete_paper',
        'batch_delete': 'batch_delete',
        'clear_history': 'clear_history',
        'batch_analyze': 'batch_analyze',
    }

    # 消息中触发确认的关键词模式
    MESSAGE_PATTERNS = {
        'delete_paper': ['删除论文', '删除这篇', '删掉论文'],
        'batch_delete': ['批量删除', '全部删除', '删除所有'],
        'clear_history': ['清除历史', '清空对话', '删除对话', '清除对话'],
        'batch_analyze': ['批量分析', '全部分析', '分析所有'],
    }

    def check_confirmation_needed(self, intent: str, params: dict) -> dict | None:
        """检查操作是否需要用户确认

        Args:
            intent: 识别到的意图/工具名
            params: 操作参数

        Returns:
            None 表示无需确认，否则返回确认消息字典
        """
        action = self._resolve_action(intent, params)
        if not action:
            return None

        action_config = self.HIGH_RISK_ACTIONS.get(action)
        if not action_config:
            return None

        return self.generate_confirmation_message(action, params)

    def generate_confirmation_message(self, action: str, details: dict) -> dict:
        """生成确认消息

        格式与前端 Task 50 约定一致。
        """
        action_config = self.HIGH_RISK_ACTIONS.get(action, {})
        description = action_config.get('description', f'即将执行 {action} 操作')
        level = action_config.get('level', 'medium')

        return {
            'type': 'confirmation_required',
            'action': action,
            'description': description,
            'level': level,
            'details': details,
            'options': [
                {'label': '确认执行', 'value': 'confirm'},
                {'label': '取消', 'value': 'cancel'},
            ],
        }

    def _resolve_action(self, intent: str, params: dict) -> str | None:
        """根据意图和参数解析出需要确认的动作

        优先级：意图直接匹配 > 参数推断 > 消息关键词匹配
        """
        # 1. 意图直接映射
        action = self.INTENT_ACTION_MAP.get(intent)
        if action:
            return action

        # 2. 参数推断（如 params 中的 action 字段）
        if isinstance(params, dict):
            explicit_action = params.get('action', '')
            if explicit_action in self.HIGH_RISK_ACTIONS:
                return explicit_action

        # 3. 消息关键词匹配
        query = params.get('query', '') or params.get('message', '') if isinstance(params, dict) else ''
        if query:
            for action_key, patterns in self.MESSAGE_PATTERNS.items():
                for pattern in patterns:
                    if pattern in query:
                        return action_key

        return None


confirmation_service = ConfirmationService()
