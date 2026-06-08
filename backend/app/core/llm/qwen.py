"""通义千问 (DashScope) 适配器"""

import asyncio
import logging
import time
from typing import AsyncIterator
import os
from app.config import get_settings
from app.core.llm.base import LLMProvider, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class QwenProvider(LLMProvider):

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.dashscope_api_key
        self.default_model = settings.qwen_default_model

    @property
    def provider_name(self) -> str:
        return "qwen"

    def _ensure_api_key(self):
        key = self._api_key or os.environ.get("DASHSCOPE_API_KEY")
        if not key:
            raise RuntimeError(
                "DashScope API key 未配置。请设置 DASHSCOPE_API_KEY 环境变量。"
            )
        os.environ["DASHSCOPE_API_KEY"] = key

    async def chat(self, request: LLMRequest) -> LLMResponse:
        self._ensure_api_key()
        model = request.model or self.default_model
        t0 = time.perf_counter()

        def _call():
            from dashscope import Generation
            return Generation.call(
                model=model,
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                result_format="message",
            )

        response = await asyncio.to_thread(_call)
        elapsed = time.perf_counter() - t0

        if response.status_code == 200:
            output = response.output
            tokens = (
                response.usage.input_tokens + response.usage.output_tokens
                if response.usage else 0
            )
            logger.info(
                "Qwen chat 完成 | model=%s | tokens=%s | %.1fs",
                model, tokens, elapsed,
            )
            return LLMResponse(
                content=output.choices[0].message.content,
                model=model,
                provider=self.provider_name,
                token_usage=tokens or None,
                finish_reason=output.choices[0].finish_reason or "stop",
            )
        else:
            logger.error(
                "Qwen API 调用失败 | model=%s | code=%s | message=%s | %.1fs",
                model, response.status_code, response.message, elapsed,
            )
            raise RuntimeError(
                f"Qwen API 调用失败: code={response.status_code}, message={response.message}"
            )

    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        self._ensure_api_key()
        model = request.model or self.default_model

        def _collect():
            from dashscope import Generation
            return list(Generation.call(
                model=model,
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                result_format="message",
                stream=True,
                incremental_output=True,
            ))

        results = await asyncio.to_thread(_collect)
        for response in results:
            if response.status_code == 200 and response.output:
                content = response.output.choices[0].message.content
                if content:
                    yield content

