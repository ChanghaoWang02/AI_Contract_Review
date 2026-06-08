"""LLM 提供商注册中心"""

import logging
from typing import Optional
from app.config import get_settings
from app.core.llm.base import LLMProvider
from app.core.llm.claude import ClaudeProvider
from app.core.llm.openai_adapter import OpenAIProvider
from app.core.llm.qwen import QwenProvider
from app.core.llm.deepseek import DeepSeekProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """LLM 提供商注册与解析"""

    _providers: dict[str, LLMProvider] = {}
    _initialized = False

    @classmethod
    def _ensure_initialized(cls):
        if cls._initialized:
            return
        cls._providers = {
            "claude": ClaudeProvider(),
            "openai": OpenAIProvider(),
            "qwen": QwenProvider(),
            "deepseek": DeepSeekProvider(),
        }
        cls._initialized = True

    @classmethod
    def get(cls, provider_name: str) -> LLMProvider:
        """获取指定提供商实例"""
        cls._ensure_initialized()
        provider = cls._providers.get(provider_name)
        if not provider:
            available = list(cls._providers.keys())
            raise ValueError(
                f"不支持的 LLM 提供商: '{provider_name}'。可选: {available}"
            )
        return provider

    @classmethod
    def resolve(cls, provider_name: Optional[str] = None) -> LLMProvider:
        """
        解析提供商：传入名称则使用指定，否则使用默认。
        如果默认不可用，按 fallback 顺序降级。
        """
        cls._ensure_initialized()
        settings = get_settings()

        if provider_name and provider_name in cls._providers:
            logger.debug("LLM 提供商: %s (指定)", provider_name)
            return cls._providers[provider_name]

        # 使用默认
        default = settings.llm_default_provider
        if default in cls._providers:
            logger.debug("LLM 提供商: %s (默认)", default)
            return cls._providers[default]

        # 降级
        for fallback in settings.llm_fallback_providers:
            if fallback in cls._providers:
                logger.warning(
                    "LLM 默认提供商 '%s' 不可用，降级至 '%s'", default, fallback
                )
                return cls._providers[fallback]

        raise RuntimeError("没有可用的 LLM 提供商。请检查配置。")

    @classmethod
    def list_providers(cls) -> list[str]:
        cls._ensure_initialized()
        return list(cls._providers.keys())
