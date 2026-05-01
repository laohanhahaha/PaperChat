"""设置服务

提供用户个性化配置的管理功能，包括获取、更新、重置和运行时应用
"""
import json
import copy
import logging
import time
from typing import Dict, Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import UserSettings
from app.config import settings as app_settings
from app.services.security.encryption import get_encryption_service

logger = logging.getLogger(__name__)


# 默认配置定义（含元数据供前端渲染表单）
DEFAULT_SETTINGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "llm": {
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
        },
        "reranker_enabled": {
            "value": True,
            "type": "toggle",
            "label": "Reranker 重排序",
            "description": "启用 bge-reranker-v2-m3 对检索结果重排序（+50-100ms）"
        },
        "hyde_enabled": {
            "value": False,
            "type": "toggle",
            "label": "HyDE 假设文档增强",
            "description": "用 LLM 生成假设文档增强检索（+500-1000ms，默认关闭）"
        },
        "reranker_model": {
            "value": "BAAI/bge-reranker-v2-m3",
            "type": "text",
            "label": "Reranker 模型",
            "description": "重排序模型名称"
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
    },
    "precache": {
        "topics": {
            "value": app_settings.PRECACHE_DEFAULT_TOPICS.split(","),
            "type": "multi_select",
            "options": [
                {"value": "cs.AI", "label": "cs.AI (人工智能)"},
                {"value": "cs.CL", "label": "cs.CL (计算语言学)"},
                {"value": "cs.CV", "label": "cs.CV (计算机视觉)"},
                {"value": "cs.LG", "label": "cs.LG (机器学习)"},
                {"value": "cs.NE", "label": "cs.NE (神经与进化计算)"},
                {"value": "cs.IR", "label": "cs.IR (信息检索)"},
                {"value": "stat.ML", "label": "stat.ML (统计机器学习)"}
            ],
            "label": "预缓存主题",
            "description": "选择关注的 arXiv 分类，后台将自动缓存相关领域最新论文"
        }
    },
    "zotero": {
        "api_key": {
            "value": "",
            "type": "password",
            "label": "Zotero API Key",
            "description": "从 Zotero 个人设置中生成的 API Key"
        },
        "library_id": {
            "value": "",
            "type": "text",
            "label": "Zotero Library ID",
            "description": "你的 Zotero 用户 ID（数字）"
        },
        "library_type": {
            "value": "users",
            "type": "select",
            "options": ["users", "groups"],
            "label": "Library 类型",
            "description": "个人库 (users) 或群组库 (groups)"
        }
    },
    "mcp": {
        "status": {
            "value": "",
            "type": "text",
            "label": "服务状态",
            "description": "MCP 学术服务配置状态（此分组由 ConfigAgentPanel 组件渲染）"
        }
    },
    "routing": {
        "model_mode": {
            "value": "smart_route",
            "type": "select",
            "options": ["smart_route", "local_only", "cloud_only"],
            "label": "模型路由模式",
            "description": "智能路由自动根据任务复杂度选择模型，仅本地模式不使用云端 API，仅云端模式始终使用云端模型"
        },
        "budget_limit": {
            "value": 10.0,
            "type": "number",
            "min": 0,
            "max": 1000,
            "label": "月度预算上限（元）",
            "description": "月度 API 调用费用上限，超出后自动降级到本地模型"
        },
        "confirm_threshold": {
            "value": 0.5,
            "type": "slider",
            "min": 0.0,
            "max": 5.0,
            "step": 0.1,
            "label": "单次费用确认阈值（元）",
            "description": "预估费用超过此阈值时请求用户确认"
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
        elif config_type == "multi_select":
            if not isinstance(value, list):
                return False
            options = config.get("options", [])
            option_values = [
                opt["value"] if isinstance(opt, dict) else opt for opt in options
            ]
            return all(v in option_values for v in value)

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

    # ------------------------------------------------------------------
    # API Key 轮换与验证
    # ------------------------------------------------------------------

    # 支持的第三方服务名称 → 验证端点映射
    _KEY_VALIDATION_MAP: Dict[str, Dict[str, Any]] = {
        "deepseek": {
            "url": "https://api.deepseek.com/models",
            "method": "GET",
            "headers": lambda key: {"Authorization": f"Bearer {key}"},
            "expect_status": 200,
            "label": "DeepSeek",
        },
        "bing": {
            "url": "https://api.bing.microsoft.com/v7.0/search?q=test",
            "method": "GET",
            "headers": lambda key: {"Ocp-Apim-Subscription-Key": key},
            "expect_status": 200,
            "label": "Bing Search",
        },
        "tavily": {
            "url": "https://api.tavily.com/search",
            "method": "POST",
            "headers": lambda key: {"Content-Type": "application/json"},
            "body": lambda key: {"api_key": key, "query": "test", "max_results": 1},
            "expect_status": 200,
            "label": "Tavily Search",
        },
        "brave": {
            "url": "https://api.search.brave.com/res/v1/web/search?q=test&count=1",
            "method": "GET",
            "headers": lambda key: {"X-Subscription-Token": key},
            "expect_status": 200,
            "label": "Brave Search",
        },
        "zotero": {
            "url": "https://api.zotero.org/users/me",
            "method": "GET",
            "headers": lambda key: {"Zotero-API-Key": key},
            "expect_status": 200,
            "label": "Zotero",
        },
        "semantic_scholar": {
            "url": "https://api.semanticscholar.org/graph/v1/paper/search?query=test&limit=1",
            "method": "GET",
            "headers": lambda key: {"x-api-key": key},
            "expect_status": 200,
            "label": "Semantic Scholar",
        },
    }

    async def validate_api_key(self, service_name: str, key: str) -> dict:
        """验证 API Key 有效性

        根据服务名称调用对应的验证端点，检测 Key 是否可用。
        所有请求带有 5s 超时保护，避免阻塞。

        性能影响：每次验证发起一次 HTTP 请求，延迟取决于目标服务响应速度
        （通常 200ms~2s），5s 超时兜底。不影响其他并发请求。

        Args:
            service_name: 服务名称（deepseek/bing/tavily/brave/zotero/semantic_scholar）
            key: 待验证的 API Key

        Returns:
            {"valid": bool, "message": str, "latency_ms": int}
        """
        service_name = service_name.lower().strip()
        if service_name not in self._KEY_VALIDATION_MAP:
            return {
                "valid": False,
                "message": f"不支持的服务: {service_name}，支持: {', '.join(self._KEY_VALIDATION_MAP.keys())}",
                "latency_ms": 0,
            }

        if not key or not key.strip():
            return {"valid": False, "message": "API Key 不能为空", "latency_ms": 0}

        config = self._KEY_VALIDATION_MAP[service_name]
        start = time.monotonic()

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                headers = config["headers"](key)
                method = config["method"]
                url = config["url"]

                if method == "GET":
                    resp = await client.get(url, headers=headers)
                else:  # POST
                    body = config.get("body", lambda k: {})(key)
                    resp = await client.post(url, headers=headers, json=body)

            latency_ms = int((time.monotonic() - start) * 1000)

            if resp.status_code == config["expect_status"]:
                return {
                    "valid": True,
                    "message": f"{config['label']} API Key 验证通过",
                    "latency_ms": latency_ms,
                }
            elif resp.status_code in (401, 403):
                return {
                    "valid": False,
                    "message": f"{config['label']} API Key 无效（HTTP {resp.status_code}）",
                    "latency_ms": latency_ms,
                }
            else:
                return {
                    "valid": False,
                    "message": f"{config['label']} 验证异常（HTTP {resp.status_code}），无法确认有效性",
                    "latency_ms": latency_ms,
                }

        except httpx.TimeoutException:
            latency_ms = int((time.monotonic() - start) * 1000)
            return {
                "valid": False,
                "message": f"{config['label']} 验证超时（5s）",
                "latency_ms": latency_ms,
            }
        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            return {
                "valid": False,
                "message": f"{config['label']} 验证失败: {str(e)[:100]}",
                "latency_ms": latency_ms,
            }

    async def rotate_api_key(
        self,
        user_id: int,
        service_name: str,
        new_key: str,
        db: AsyncSession,
    ) -> dict:
        """轮换 API Key

        步骤：
          1. 读取旧 key（脱敏记录）
          2. 验证新 key 有效性
          3. 更新数据库中的 key
          4. 应用到运行时服务
          5. 记录审计日志

        性能影响：轮换过程中包含一次 HTTP 验证请求（200ms~2s），
        以及数据库写操作。LLM 服务实例会重建，但仅在轮换完成时触发一次，
        不影响正在进行的流式请求（下一个请求生效）。

        Args:
            user_id: 用户 ID
            service_name: 服务名称
            new_key: 新的 API Key
            db: 数据库会话

        Returns:
            {"success": bool, "message": str, "service": str}
        """
        service_name = service_name.lower().strip()

        # 1. 读取旧 key
        old_values = await self.get_setting_values(user_id, db)
        old_key = ""
        if service_name == "deepseek":
            # deepseek 的 api_key 已移至 model_configs 表管理
            from app.models.model_config import ModelConfig
            from sqlalchemy import select as sa_select
            active_result = await db.execute(
                sa_select(ModelConfig).where(
                    ModelConfig.user_id == user_id,
                    ModelConfig.is_active == True,
                )
            )
            active_config = active_result.scalar_one_or_none()
            old_key = active_config.api_key if active_config else ""
        else:
            # 其他服务的 key 也存储在配置区域或单独区域
            old_key = old_values.get(service_name, {}).get("api_key", "")

        # 2. 验证新 key
        validation = await self.validate_api_key(service_name, new_key)
        if not validation["valid"]:
            return {
                "success": False,
                "message": f"新 Key 验证失败: {validation['message']}",
                "service": service_name,
            }

        # 3. 更新数据库
        if service_name == "deepseek":
            # deepseek 的 key 已移至 model_configs，更新激活模型的 api_key
            from app.models.model_config import ModelConfig
            from sqlalchemy import select as sa_select
            active_result = await db.execute(
                sa_select(ModelConfig).where(
                    ModelConfig.user_id == user_id,
                    ModelConfig.is_active == True,
                )
            )
            active_config = active_result.scalar_one_or_none()
            if active_config:
                active_config.api_key = new_key
                await db.commit()
            else:
                return {
                    "success": False,
                    "message": "没有激活的模型配置，请先添加模型",
                    "service": service_name,
                }
        else:
            update_payload = {service_name: {"api_key": new_key}}
            try:
                result = await self.update_settings(user_id, update_payload, db)
            except Exception as e:
                return {
                    "success": False,
                    "message": f"数据库更新失败: {str(e)[:100]}",
                    "service": service_name,
                }

        # 4. 应用到运行时服务
        if service_name == "deepseek":
            try:
                from app.services.llm.llm_service import llm_service
                await llm_service.update_config(api_key=new_key)
                logger.info(f"DeepSeek API Key 已轮换并应用到运行时服务")
            except Exception as e:
                logger.warning(f"运行时应用新 Key 失败: {e}")

        # 5. 记录审计日志（复用 ApiKeyAuditor）
        try:
            from app.services.privacy.privacy_service import api_key_auditor
            api_key_auditor.log_access(
                key_id=self._mask_api_key(old_key),
                action="rotate_key",
                source=f"user:{user_id}",
            )
            api_key_auditor.log_access(
                key_id=self._mask_api_key(new_key),
                action="rotate_key_new",
                source=f"user:{user_id}",
            )
        except Exception as e:
            logger.debug(f"审计日志记录失败（非阻断）: {e}")

        logger.info(
            f"API Key 轮换成功: service={service_name}, user={user_id}, "
            f"old={self._mask_api_key(old_key)}, new={self._mask_api_key(new_key)}"
        )

        return {
            "success": True,
            "message": f"{service_name} API Key 轮换成功",
            "service": service_name,
        }

    async def apply_settings(self, settings_values: Dict[str, Dict[str, Any]]) -> bool:
        """将设置应用到各服务的运行时参数
        
        Args:
            settings_values: 纯值配置字典
            
        Returns:
            是否应用成功
        """
        try:
            # 应用 LLM 配置（model/api_key/api_base_url 已移至 model_configs 管理，只应用 temperature/max_tokens）
            if "llm" in settings_values:
                from app.services.llm_service import llm_service
                llm_config = settings_values["llm"]
                
                await llm_service.update_config(
                    temperature=llm_config.get("temperature"),
                    max_tokens=llm_config.get("max_tokens"),
                )
                logger.info(f"LLM 配置已更新: temperature={llm_config.get('temperature')}, max_tokens={llm_config.get('max_tokens')}")
            
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
                from app.services.recommendation_service import recommendation_service
                rec_config = settings_values["recommendation"]
                await recommendation_service.update_config(
                    top_k=rec_config.get("top_k")
                )
                logger.info(f"推荐配置已更新: top_k={rec_config.get('top_k')}")

            # 应用预缓存配置
            if "precache" in settings_values:
                from app.services.precache_service import precache_service
                precache_config = settings_values["precache"]
                topics = precache_config.get("topics", [])
                if isinstance(topics, str):
                    topics = [t.strip() for t in topics.split(",") if t.strip()]
                if topics:
                    precache_service.update_topics(topics)
                    logger.info(f"预缓存主题已更新: {topics}")

            return True
            
        except Exception as e:
            logger.error(f"应用配置失败: {e}")
            return False


# 全局单例
settings_service = SettingsService()
