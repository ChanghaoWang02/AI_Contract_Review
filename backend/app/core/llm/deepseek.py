"""DeepSeek 适配器 (兼容 OpenAI API)"""

import logging
import time
from typing import AsyncIterator, Optional
from openai import AsyncOpenAI
from app.config import get_settings
from app.core.llm.base import LLMProvider, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class DeepSeekProvider(LLMProvider):
    _client: Optional[AsyncOpenAI] = None

    BASE_URL = "https://api.deepseek.com"

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.deepseek_api_key
        self.default_model = settings.deepseek_default_model

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            import httpx
            self._client = AsyncOpenAI(
                api_key=self._api_key or "not-set",
                base_url=self.BASE_URL,
                timeout=httpx.Timeout(120.0, connect=15.0),
            )
        return self._client

    @property
    def provider_name(self) -> str:
        return "deepseek"

    async def chat(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.default_model
        t0 = time.perf_counter()

        response = await self._get_client().chat.completions.create(
            model=model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        choice = response.choices[0]
        elapsed = time.perf_counter() - t0
        logger.info(
            "DeepSeek chat 完成 | model=%s | tokens=%s | %.1fs",
            model,
            response.usage.total_tokens if response.usage else "?",
            elapsed,
        )
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            provider=self.provider_name,
            token_usage=(
                response.usage.total_tokens
                if response.usage else None
            ),
            finish_reason=choice.finish_reason or "stop",
        )

    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        model = request.model or self.default_model

        stream = await self._get_client().chat.completions.create(
            model=model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

