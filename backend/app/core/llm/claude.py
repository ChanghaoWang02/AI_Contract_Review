"""Claude (Anthropic) 适配器"""

import logging
import time
from typing import AsyncIterator, Optional
from anthropic import AsyncAnthropic
from app.config import get_settings
from app.core.llm.base import LLMProvider, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class ClaudeProvider(LLMProvider):
    _client: Optional[AsyncAnthropic] = None

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.anthropic_api_key
        self.default_model = settings.anthropic_default_model

    def _get_client(self) -> AsyncAnthropic:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "Anthropic API key 未配置。请设置 ANTHROPIC_API_KEY 环境变量。"
                )
            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    @property
    def provider_name(self) -> str:
        return "claude"

    async def chat(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.default_model
        t0 = time.perf_counter()
        system_prompt, user_messages = self._extract_system(request.messages)

        kwargs = dict(
            model=model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            messages=user_messages,
        )
        if system_prompt:
            kwargs["system"] = system_prompt

        response = await self._get_client().messages.create(**kwargs)

        elapsed = time.perf_counter() - t0
        tokens = (
            response.usage.input_tokens + response.usage.output_tokens
            if response.usage else 0
        )
        logger.info(
            "Claude chat 完成 | model=%s | tokens=%s | %.1fs",
            model, tokens, elapsed,
        )
        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            provider=self.provider_name,
            token_usage=tokens or None,
            finish_reason=response.stop_reason or "stop",
        )

    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        model = request.model or self.default_model
        system_prompt, user_messages = self._extract_system(request.messages)

        kwargs = dict(
            model=model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            messages=user_messages,
        )
        if system_prompt:
            kwargs["system"] = system_prompt

        async with self._get_client().messages.stream(**kwargs) as stream:
            async for text_delta in stream.text_stream:
                yield text_delta

    def _extract_system(self, messages: list[dict]) -> tuple[Optional[str], list[dict]]:
        system_content = None
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                user_messages.append(msg)
        return system_content, user_messages
