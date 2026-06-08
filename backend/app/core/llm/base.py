"""LLM 提供商抽象基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional


@dataclass
class LLMRequest:
    messages: list[dict]
    model: str
    temperature: float = 0.3
    max_tokens: int = 4096
    stream: bool = False


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    token_usage: Optional[int] = None
    finish_reason: str = "stop"


class LLMProvider(ABC):
    """LLM 提供商抽象基类"""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @abstractmethod
    async def chat(self, request: LLMRequest) -> LLMResponse:
        """同步聊天（一次性返回完整响应）"""
        ...

    @abstractmethod
    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """流式聊天（逐 token yield）"""
        ...

    def count_tokens(self, text: str) -> int:
        """估算 token 数（默认近似：中文约 1-2 字符/token）"""
        return len(text) // 2

    def supports_model(self, model: str) -> bool:
        """检查是否支持指定模型"""
        return True
