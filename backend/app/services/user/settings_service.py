"""设置服务

提供用户个性化配置的管理功能，包括获取、更新、重置和运行时应用
"""
import json
import copy
import logging
from typing import Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import UserSettings
from app.config import settings as app_settings
from app.services.llm.llm_service import llm_service
from app.services.core.event_bus import event_bus, Event, EventTypes

logger = logging.getLogger(__name__)


# 默认配置定义（含元数据供前端渲染表单）
DEFAULT_SETTINGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "llm": {
        "model": {
            "value": "deepseek-v4-flash",
            "type": "select",
            "options": ["deepseek-v4-flash", "deepseek-v4-pro"],
            "label": "AI 模型",
            "description": "选择用于问答的AI模型"
        },
        "temperature": {
            "value": 0.3,
            "type": "slider",
            "min": 0.0,
            "max": 2.0,
            "step": 0.1,
            "label": "回答温度",
            "description": "越高越有创意，越低越精确"
        },
        "max_tokens": {
            "value": 4096,
            "type": "number",
            "min": 512,
            "max": 32000,
            "label": "最大Token数",
            "description": "控制回答长度上限"
        },
        "api_key": {
            "value": "",
            "type": "password",
            "label": "API Key",
            "description": "留空则使用环境变量中的默认Key"
        },
        "api_base_url": {
            "value": "https://api.deepseek.com",
            "type": "text",
            "label": "API Base URL",
            "description": "API服务地址"
        }
    },
    "rag": {
        "top_k": {
            "value": 5,
            "type": "slider",
            "min": 1,
            "max": 20,
            "step": 1,
            "label": "检索数量",
            "description": "每次检索返回的文本块数量"
        },
        "chunk_size": {
            "value": 800,
            "type": "number",
            "min": 200,
            "max": 2000,
            "label": "分块大小",
            "description": "PDF文本分块的字符数"
        },
        "chunk_overlap": {
            "value": 200,
            "type": "number",
            "min": 50,
            "max": 500,
            "label": "块重叠",
            "description": "相邻文本块的重叠字符数"
        }
    },
    "search": {
        "max_results": {
            "value": 5,
            "type": "slider",
            "min": 1,
            "max": 20,
            "step": 1,
            "label": "最大搜索结果",
            "description": "联网搜索返回的结果数量"
        },
        "timeout": {
            "value": 15,
            "type": "number",
            "min": 5,
            "max": 60,
            "label": "搜索超时(秒)",
            "description": "网络搜索的超时时间"
        }
    },
    "recommendation": {
        "top_k": {
            "value": 5,
            "type": "slider",
            "min": 1,
            "max": 20,
            "step": 1,
            "label": "推荐数量",
            "description": "推荐的论文数量"
        }
    },
    "appearance": {
        "theme": {
            "value": "auto",
            "type": "select",
            "options": ["light", "dark", "auto"],
            "label": "主题模式",
            "description": "浅色、深色或跟随系统自动切换"
        },
        "accent_color": {
            "value": "purple",
            "type": "select",
            "options": ["blue", "purple", "green", "orange"],
            "label": "强调色",
            "description": "界面主要色调"
        },
        "font_size": {
            "value": 1.0,
            "type": "slider",
            "min": 0.85,
            "max": 1.2,
            "step": 0.05,
            "label": "字体大小",
            "description": "全局文字缩放比例（1.0 = 100%）"
        },
        "compact_mode": {
            "value": False,
            "type": "toggle",
            "label": "紧凑模式",
            "description": "减少界面间距，显示更多内容"
        }
    },
    "general": {
        "max_file_size_mb": {
            "value": 50,
            "type": "number",
            "min": 10,
            "max": 500,
            "label": "最大文件大小(MB)",
            "description": "PDF上传的最大文件大小"
        },
        "chat_history_limit": {
            "value": 10,
            "type": "number",
            "min": 5,
            "max": 100,
            "label": "对话历史条数",
            "description": "每次问答时携带的历史消息数量"
        }
    }
}


class SettingsService:
    """设置服务类
    
    功能：
    1. 管理用户个性化配置
    2. 配置校验
    3. 运行时应用配置到各服务
    """
    
    def get_default_settings(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """获取默认配置（含元数据）"""
        return copy.deepcopy(DEFAULT_SETTINGS)
    
    def get_default_values(self) -> Dict[str, Dict[str, Any]]:
        """获取纯值配置（不含元数据）"""
        result = {}
        for category, settings in DEFAULT_SETTINGS.items():
            result[category] = {}
            for key, config in settings.items():
                result[category][key] = config["value"]
        return result
    
    def _validate_setting(self, category: str, key: str, value: Any) -> bool:
        """校验单个配置值
        
        Args:
            category: 配置分类
            key: 配置键
            value: 配置值
            
        Returns:
            是否有效
        """
        if category not in DEFAULT_SETTINGS:
            return False
        if key not in DEFAULT_SETTINGS[category]:
            return False
        
        config = DEFAULT_SETTINGS[category][key]
        config_type = config.get("type", "text")
        
        # 类型校验
        if config_type in ("slider", "number"):
            if not isinstance(value, (int, float)):
                return False
            min_val = config.get("min")
            max_val = config.get("max")
            if min_val is not None and value < min_val:
                return False
            if max_val is not None and value > max_val:
                return False
        elif config_type == "select":
            options = config.get("options", [])
            if value not in options:
                return False
        elif config_type == "text" or config_type == "password":
            if not isinstance(value, str):
                return False
        elif config_type == "toggle":
            if not isinstance(value, bool):
                return False
        
        return True
    
    def _mask_api_key(self, api_key: str) -> str:
        """脱敏 API Key，只显示最后4位
        
        Args:
            api_key: 原始 API Key
            
        Returns:
            脱敏后的 API Key
        """
        if not api_key or len(api_key) <= 4:
            return "****" if api_key else ""
        return "****" + api_key[-4:]
    
    async def get_settings(
        self, 
        user_id: int, 
        db: AsyncSession,
        mask_sensitive: bool = True
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """获取用户设置，返回完整配置（含元数据）
        
        Args:
            user_id: 用户 ID
            db: 数据库会话
            mask_sensitive: 是否脱敏敏感信息
            
        Returns:
            完整配置字典
        """
        # 获取默认配置
        result = self.get_default_settings()
        
        # 查询用户自定义配置
        query = select(UserSettings).where(UserSettings.user_id == user_id)
        result_db = await db.execute(query)
        user_settings = result_db.scalar_one_or_none()
        
        if user_settings and user_settings.settings_json:
            try:
                user_values = json.loads(user_settings.settings_json)
                # 合并用户配置到默认配置
                for category, settings in user_values.items():
                    if category in result:
                        for key, value in settings.items():
                            if key in result[category]:
                                result[category][key]["value"] = value
            except json.JSONDecodeError:
                logger.warning(f"用户 {user_id} 的配置 JSON 解析失败")
        
        # 脱敏 API Key
        if mask_sensitive and "llm" in result and "api_key" in result["llm"]:
            api_key = result["llm"]["api_key"].get("value", "")
            result["llm"]["api_key"]["value"] = self._mask_api_key(api_key)
            result["llm"]["api_key"]["masked"] = True
        
        return result
    
    async def get_setting_values(
        self, 
        user_id: int, 
        db: AsyncSession
    ) -> Dict[str, Dict[str, Any]]:
        """获取纯值配置（不含元数据，用于后端服务读取）
        
        Args:
            user_id: 用户 ID
            db: 数据库会话
            
        Returns:
            纯值配置字典
        """
        # 获取默认值
        result = self.get_default_values()
        
        # 查询用户自定义配置
        query = select(UserSettings).where(UserSettings.user_id == user_id)
        result_db = await db.execute(query)
        user_settings = result_db.scalar_one_or_none()
        
        if user_settings and user_settings.settings_json:
            try:
                user_values = json.loads(user_settings.settings_json)
                # 合并用户配置
                for category, settings in user_values.items():
                    if category in result:
                        for key, value in settings.items():
                            if key in result[category]:
                                result[category][key] = value
            except json.JSONDecodeError:
                logger.warning(f"用户 {user_id} 的配置 JSON 解析失败")
        
        # 如果用户没有设置 API Key，使用环境变量中的默认值
        if not result.get("llm", {}).get("api_key"):
            result.setdefault("llm", {})["api_key"] = app_settings.DEEPSEEK_API_KEY
        
        return result
    
    async def update_settings(
        self, 
        user_id: int, 
        settings: Dict[str, Dict[str, Any]], 
        db: AsyncSession
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """更新用户配置（校验范围），返回更新后的完整配置
        
        Args:
            user_id: 用户 ID
            settings: 要更新的配置
            db: 数据库会话
            
        Returns:
            更新后的完整配置
            
        Raises:
            ValueError: 配置校验失败
        """
        # 校验所有配置
        errors = []
        for category, category_settings in settings.items():
            for key, value in category_settings.items():
                if not self._validate_setting(category, key, value):
                    errors.append(f"无效的配置: {category}.{key} = {value}")
        
        if errors:
            raise ValueError("; ".join(errors))
        
        # 过滤脱敏值，不保存到数据库
        filtered_settings = copy.deepcopy(settings)
        if "llm" in filtered_settings and "api_key" in filtered_settings["llm"]:
            api_key = filtered_settings["llm"]["api_key"]
            if api_key and self._is_masked_api_key(api_key):
                # 脱敏值不保存到数据库
                del filtered_settings["llm"]["api_key"]
                logger.info(f"用户 {user_id} 的 API Key 为脱敏值，跳过保存")
        
        # 查询现有配置
        query = select(UserSettings).where(UserSettings.user_id == user_id)
        result_db = await db.execute(query)
        user_settings = result_db.scalar_one_or_none()
        
        # 获取当前配置
        if user_settings and user_settings.settings_json:
            try:
                current_values = json.loads(user_settings.settings_json)
            except json.JSONDecodeError:
                current_values = {}
        else:
            current_values = {}
        
        # 合并新配置（使用过滤后的配置）
        for category, category_settings in filtered_settings.items():
            if category not in current_values:
                current_values[category] = {}
            for key, value in category_settings.items():
                current_values[category][key] = value
        
        # 保存到数据库
        if user_settings:
            user_settings.settings_json = json.dumps(current_values, ensure_ascii=False)
        else:
            user_settings = UserSettings(
                user_id=user_id,
                settings_json=json.dumps(current_values, ensure_ascii=False)
            )
            db.add(user_settings)
        
        await db.commit()
        
        logger.info(f"用户 {user_id} 更新配置: {list(settings.keys())}")
        
        # 发布配置变更事件（fire-and-forget）
        import asyncio
        asyncio.create_task(event_bus.publish(Event(
            type=EventTypes.SETTINGS_CHANGED,
            data={"user_id": user_id, "changed_categories": list(settings.keys())}
        )))
        
        # 返回更新后的完整配置
        return await self.get_settings(user_id, db)
    
    async def reset_settings(
        self, 
        user_id: int, 
        db: AsyncSession
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """重置为默认值
        
        Args:
            user_id: 用户 ID
            db: 数据库会话
            
        Returns:
            默认配置
        """
        # 查询并删除用户配置
        query = select(UserSettings).where(UserSettings.user_id == user_id)
        result_db = await db.execute(query)
        user_settings = result_db.scalar_one_or_none()
        
        if user_settings:
            await db.delete(user_settings)
            await db.commit()
        
        logger.info(f"用户 {user_id} 重置配置为默认值")
        
        return self.get_default_settings()
    
    def _is_masked_api_key(self, api_key: str) -> bool:
        """检查是否为脱敏后的 API Key
        
        脱敏格式为 "****" + 最后4位，如 "****1234"
        只检测严格匹配脱敏格式的值，避免误判真实 Key
        
        Args:
            api_key: 待检查的 API Key
            
        Returns:
            是否为脱敏值
        """
        if not api_key or not isinstance(api_key, str):
            return False
        # 严格检测：必须以 "****" 开头，且总长度不超过 8 位（**** + 最多4位）
        # 或者只包含 "****" 和最多4个其他字符
        if not api_key.startswith("****"):
            return False
        # 脱敏值格式：**** + 0-4个字符
        suffix = api_key[4:]
        return len(suffix) <= 4

    async def apply_settings(self, settings_values: Dict[str, Dict[str, Any]]) -> bool:
        """将设置应用到各服务的运行时参数
        
        Args:
            settings_values: 纯值配置字典
            
        Returns:
            是否应用成功
        """
        try:
            # 应用 LLM 配置
            if "llm" in settings_values:
                llm_config = settings_values["llm"]
                
                # 获取 api_key，如果是脱敏值则不传递（保留原值）
                api_key = llm_config.get("api_key")
                if api_key and self._is_masked_api_key(api_key):
                    logger.info("API Key 为脱敏值，跳过更新，保留原值")
                    api_key = None  # 传递 None 表示不更新
                
                await llm_service.update_config(
                    model=llm_config.get("model"),
                    temperature=llm_config.get("temperature"),
                    max_tokens=llm_config.get("max_tokens"),
                    api_key=api_key,
                    api_base_url=llm_config.get("api_base_url")
                )
                logger.info(f"LLM 配置已更新: model={llm_config.get('model')}, temperature={llm_config.get('temperature')}")
            
            # 应用 RAG 配置
            if "rag" in settings_values:
                from app.services.rag_service import rag_service
                rag_config = settings_values["rag"]
                await rag_service.update_config(
                    top_k=rag_config.get("top_k"),
                    chunk_size=rag_config.get("chunk_size"),
                    chunk_overlap=rag_config.get("chunk_overlap")
                )
                logger.info(f"RAG 配置已更新: top_k={rag_config.get('top_k')}")
            
            # 应用推荐配置
            if "recommendation" in settings_values:
                from app.services.paper.recommendation_service import recommendation_service
                rec_config = settings_values["recommendation"]
                await recommendation_service.update_config(
                    top_k=rec_config.get("top_k")
                )
                logger.info(f"推荐配置已更新: top_k={rec_config.get('top_k')}")
            
            return True
            
        except Exception as e:
            logger.error(f"应用配置失败: {e}")
            return False


# 全局单例
settings_service = SettingsService()
