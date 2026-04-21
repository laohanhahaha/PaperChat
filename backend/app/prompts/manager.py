"""PromptManager — 提示词统一管理器

提供 Jinja2 模板变量注入、版本管理和提示词检索功能。

性能说明：
- get_prompt(): 纯字典查找，< 1ms，无额外开销
- render_prompt(): Jinja2 模板渲染，< 1ms，无 LLM 调用
- PromptManager 为单例，模板在首次 register 时编译并缓存
"""
from typing import Any, Dict, Optional

try:
    from jinja2 import Environment, BaseLoader, TemplateError
    _JINJA2_AVAILABLE = True
except ImportError:
    _JINJA2_AVAILABLE = False


class PromptManager:
    """提示词统一管理器

    支持：
    - Jinja2 模板变量注入（render / render_prompt）
    - 版本字段（每个 prompt 以 {"template": "...", "version": "1.0"} 存储）
    - 按名称检索和渲染
    """

    def __init__(self):
        self._prompts: Dict[str, Dict[str, Any]] = {}
        if _JINJA2_AVAILABLE:
            self._jinja_env = Environment(loader=BaseLoader())
        else:
            self._jinja_env = None

    def register(
        self,
        name: str,
        template: str,
        version: str = "1.0",
        description: str = "",
    ) -> None:
        """注册一个提示词模板

        Args:
            name: 提示词唯一名称（如 "rag_chat"、"analyze_paper"）
            template: 提示词模板字符串（支持 Jinja2 语法或 str.format 占位符）
            version: 版本号（默认 "1.0"）
            description: 可选的描述信息
        """
        self._prompts[name] = {
            "template": template,
            "version": version,
            "description": description,
        }

    def get_prompt(self, name: str) -> Optional[Dict[str, Any]]:
        """获取提示词字典（包含 template、version、description）

        Args:
            name: 提示词名称

        Returns:
            提示词字典，若不存在则返回 None
        """
        return self._prompts.get(name)

    def get_template(self, name: str) -> Optional[str]:
        """获取提示词模板字符串

        Args:
            name: 提示词名称

        Returns:
            模板字符串，若不存在则返回 None
        """
        entry = self._prompts.get(name)
        if entry is None:
            return None
        return entry["template"]

    def render_prompt(self, prompt_name: str, **kwargs: Any) -> str:
        """渲染提示词模板，注入变量

        优先使用 Jinja2 模板渲染；若 Jinja2 不可用则回退到 str.format_map。

        Args:
            prompt_name: 提示词名称
            **kwargs: 模板变量

        Returns:
            渲染后的提示词字符串

        Raises:
            KeyError: 提示词名称不存在
            ValueError: 模板渲染失败
        """
        entry = self._prompts.get(prompt_name)
        if entry is None:
            raise KeyError(f"Prompt '{prompt_name}' not found. Available: {list(self._prompts.keys())}")

        template_str = entry["template"]

        if _JINJA2_AVAILABLE and self._jinja_env is not None:
            try:
                tmpl = self._jinja_env.from_string(template_str)
                return tmpl.render(**kwargs)
            except TemplateError as e:
                raise ValueError(f"Jinja2 template error for prompt '{prompt_name}': {e}") from e
        else:
            # 回退：使用 str.format_map（忽略多余的键）
            try:
                return template_str.format_map(kwargs)
            except KeyError as e:
                raise ValueError(f"Missing template variable {e} for prompt '{prompt_name}'") from e

    # 向后兼容别名
    render = render_prompt

    def list_prompts(self) -> Dict[str, str]:
        """列出所有已注册的提示词（名称 → 版本）"""
        return {name: entry["version"] for name, entry in self._prompts.items()}

    def __contains__(self, name: str) -> bool:
        return name in self._prompts

    def __len__(self) -> int:
        return len(self._prompts)


# 全局单例
prompt_manager = PromptManager()
