"""EncryptionService — 对称加密服务

使用 cryptography.fernet.Fernet 对 API Key 等敏感值进行加密存储。
主密钥从环境变量 ENCRYPTION_KEY 读取；不存在则自动生成并 warning 提示。

性能说明：
    - Fernet 加密/解密操作基于 AES-128-CBC，单次耗时 < 1ms
    - migrate_if_needed 仅在首次读取未加密旧值时有额外加密开销（< 1ms），
      已加密值直接返回，零开销
    - is_encrypted 仅做字符串前缀检测，耗时可忽略
"""

import base64
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Fernet token 在 base64 编码后始终以 "gAAAAA" 开头（版本号 0x80 的 base64 表示）
_FERNET_PREFIX = "gAAAAA"


class EncryptionService:
    """对称加密服务（单例使用）

    对外提供 encrypt / decrypt / is_encrypted / migrate_if_needed 四个方法，
    所有方法均为同步调用，无 I/O 阻塞。
    """

    def __init__(self, encryption_key: Optional[str] = None):
        """初始化加密服务

        Args:
            encryption_key: Fernet 兼容的 base64 编码密钥。
                            为 None 时从环境变量 ENCRYPTION_KEY 读取；
                            环境变量也不存在则自动生成并 warning。
        """
        key = encryption_key or os.environ.get("ENCRYPTION_KEY")

        if key:
            try:
                self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
                logger.info("EncryptionService 已使用提供的密钥初始化")
            except Exception as exc:
                logger.warning(f"提供的 ENCRYPTION_KEY 无效，将自动生成: {exc}")
                self._init_with_generated_key()
        else:
            self._init_with_generated_key()

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _init_with_generated_key(self) -> None:
        """自动生成密钥并 warning（生产环境应通过环境变量传入）"""
        generated = Fernet.generate_key()
        self._fernet = Fernet(generated)
        logger.warning(
            "ENCRYPTION_KEY 环境变量未设置，已自动生成临时密钥。"
            "请注意：应用重启后该密钥将丢失，已加密数据将无法解密！"
            "生产环境务必设置 ENCRYPTION_KEY 环境变量。"
        )

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def encrypt(self, plaintext: str) -> str:
        """加密明文，返回 base64 编码的密文

        性能：Fernet AES-128-CBC + HMAC-SHA256，单次 < 1ms

        Args:
            plaintext: 待加密的明文字符串

        Returns:
            base64 编码的密文字符串
        """
        if not plaintext:
            return plaintext
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """解密密文，返回明文字符串

        性能：Fernet 解密 + HMAC 校验，单次 < 1ms

        Args:
            ciphertext: encrypt() 返回的 base64 编码密文

        Returns:
            解密后的明文字符串

        Raises:
            InvalidToken: 密文无效或密钥不匹配
        """
        if not ciphertext:
            return ciphertext
        plaintext_bytes = self._fernet.decrypt(ciphertext.encode("utf-8"))
        return plaintext_bytes.decode("utf-8")

    def is_encrypted(self, value: str) -> bool:
        """检测值是否已加密

        Fernet token 的 base64 编码始终以 "gAAAAA" 开头（版本字节 0x80），
        利用此特征做快速前缀检测，避免对非加密值做无意义解密尝试。

        性能：仅字符串前缀比较，耗时可忽略

        Args:
            value: 待检测的字符串

        Returns:
            True 表示该值已被 Fernet 加密
        """
        if not value or not isinstance(value, str):
            return False
        return value.startswith(_FERNET_PREFIX)

    def migrate_if_needed(self, value: str) -> str:
        """如果值是明文则加密返回，已加密则原样返回

        用于向后兼容：数据库中可能存在未加密的旧 API Key，
        首次读取时自动加密并返回加密值，调用方应将返回值写回数据库。

        性能：已加密值仅做 is_encrypted 前缀检测（< 0.01ms）；
              未加密值额外执行一次 encrypt（< 1ms），仅首次读取有此开销。

        Args:
            value: 待检测/迁移的字符串

        Returns:
            加密后的值或原值（如果已加密）
        """
        if not value:
            return value
        if self.is_encrypted(value):
            return value
        # 明文 → 加密
        return self.encrypt(value)


# 全局单例（延迟初始化，由 lifespan 或模块导入时创建）
_encryption_service: Optional["EncryptionService"] = None


def get_encryption_service() -> "EncryptionService":
    """获取全局 EncryptionService 单例

    首次调用时自动初始化（读取环境变量或生成临时密钥）。
    lifespan 启动后可通过 app.state.encryption_service 获取。
    """
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def set_encryption_service(service: "EncryptionService") -> None:
    """设置全局 EncryptionService 单例（供 lifespan 初始化时使用）"""
    global _encryption_service
    _encryption_service = service
