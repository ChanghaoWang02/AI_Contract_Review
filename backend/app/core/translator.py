"""AI 合同翻译引擎 — 逐条流式翻译 + 文本翻译"""

import re
import logging
from typing import AsyncIterator, Optional
from app.config import get_settings
from app.core.llm.base import LLMRequest
from app.core.llm.registry import ProviderRegistry
from app.core.chunker import Clause, ContractChunker

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 翻译 System Prompt（法律合同翻译专用）
# ═══════════════════════════════════════════════════════════

TRANSLATION_SYSTEM_PROMPT = """# 角色与目标
你是一位拥有 20 年双语法律实务经验的合同翻译专家，精通中英文法律文书。
核心任务：将源语言合同条款准确翻译为目标语言，保持法律效力和格式。

# 行为边界
- 法律术语必须使用目标语言司法辖区对应的标准术语
  - 例：indemnification → 赔偿/免责（视语境）
  - 例：force majeure → 不可抗力
  - 不确定的术语用「【需确认：术语】」标注
- 不得增删条款内容，不得改变权利义务关系
- 保持原文的条款编号、层级结构不变

# 输出格式
- 直接输出翻译后的条款文本，不得附加任何解释性文字
- 条款标题保持「第X条 标题」格式（中文）或「Article X — Title」格式（英文）
- 占位符保持原文格式：「【请填写：xxx】」

# 质量要求
- 准确 > 流畅：法律含义不可为追求语言通顺而牺牲
- 术语一致性：同一原文术语在全文中使用同一译文
- 句式保留：原文的列举、但书、条件从句结构应尽量保留"""

# Tier 2 追加指令
TIER2_SUFFIX = """

# 注意
源语言与中文法律体系存在差异，不确定的翻译处请标注「【需确认】」并保留原文术语。"""

# Tier 3 追加指令 — 两阶段翻译
TIER3_SUFFIX = """

# 注意
你正在翻译的语言与中文差异较大。请先理解原文含义，然后以中文法律文书风格重新表达。
不确定的翻译处请标注「【需确认：原文术语】」并保留原文术语。"""

# 语言检测 prompt
LANGUAGE_DETECT_PROMPT = """请检测以下文本的源语言，只返回一个 JSON：
{"detected": "<语言代码>", "confidence": "<high|medium|low>", "language_name": "<语言中文名>"}

常见语言代码：zh(中文), en(英文), ja(日文), ko(韩文), fr(法文), de(德文), es(西班牙文), ru(俄文), ar(阿拉伯文), th(泰文), vi(越南文)

文本：
{text_sample}"""


# ═══════════════════════════════════════════════════════════
# Tier 系统
# ═══════════════════════════════════════════════════════════

TIER1_TARGET_LANGS = {"zh", "en"}   # en↔zh 直接翻译

TIER2_SOURCE_LANGS = {"ja", "ko", "fr", "de"}  # 日韩法德→zh 需复核

LANG_NAMES = {
    "zh": "中文", "en": "英文", "ja": "日文", "ko": "韩文",
    "fr": "法文", "de": "德文", "es": "西班牙文", "ru": "俄文",
    "ar": "阿拉伯文", "th": "泰文", "vi": "越南文", "pt": "葡萄牙文",
}

# CJK Unicode 范围（Rough detection — 无需 LLM）
_CJK_RE = re.compile(r'[一-鿿㐀-䶿豈-﫿]')
_JAPANESE_KANA_RE = re.compile(r'[぀-ゟ゠-ヿ]')  # 平假名+片假名
_KOREAN_RE = re.compile(r'[가-힯]')                       # 韩文音节


class TranslationEngine:
    """合同 AI 翻译引擎"""

    # ═══════════════════════════════════════════════════════════
    # 语言检测
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def classify_tier(source_lang: str, target_lang: str) -> int:
        """根据语言对返回质量 Tier"""
        pair = {source_lang, target_lang}
        if pair <= TIER1_TARGET_LANGS and len(pair) == 2:
            return 1
        if source_lang in TIER2_SOURCE_LANGS or target_lang in TIER2_SOURCE_LANGS:
            return 2
        return 3

    @staticmethod
    def quick_detect(text: str) -> Optional[str]:
        """快速启发式语言检测（无需 LLM），返回 None 表示无法判断"""
        sample = text[:2000]
        cjk_count = len(_CJK_RE.findall(sample))
        kana_count = len(_JAPANESE_KANA_RE.findall(sample))
        korean_count = len(_KOREAN_RE.findall(sample))
        total = len(sample)

        if total == 0:
            return None

        cjk_ratio = cjk_count / max(total, 1)

        if kana_count > 5:
            return "ja"
        if korean_count > 5:
            return "ko"
        if cjk_ratio > 0.08:
            return "zh"
        # ASCII 占比超高 → 英文
        ascii_count = sum(1 for c in sample if ord(c) < 128)
        if ascii_count / max(total, 1) > 0.85:
            return "en"

        return None  # 需要 LLM 判断

    @staticmethod
    async def detect_language(
        text: str,
        provider: Optional[str] = None,
    ) -> dict:
        """检测源语言，返回 {detected, confidence, tier, language_name}"""
        # 先尝试快速检测
        quick = TranslationEngine.quick_detect(text)
        if quick and quick in ("zh", "en", "ja", "ko"):
            tier = TranslationEngine.classify_tier(quick, "zh" if quick != "zh" else "en")
            return {
                "detected": quick,
                "confidence": "high",
                "tier": tier,
                "language_name": LANG_NAMES.get(quick, quick),
            }

        # LLM 检测
        try:
            llm = ProviderRegistry.resolve(provider)
            sample = text[:1500]
            response = await llm.chat(LLMRequest(
                messages=[{"role": "user", "content": LANGUAGE_DETECT_PROMPT.format(text_sample=sample)}],
                temperature=0.0,
                max_tokens=150,
                stream=False,
            ))
            import json
            result = json.loads(response.content.strip().removeprefix('```json').removesuffix('```').strip())
            detected = result.get("detected", "en").lower()
            confidence = result.get("confidence", "medium")
            tier = TranslationEngine.classify_tier(detected, "zh" if detected != "zh" else "en")
            return {
                "detected": detected,
                "confidence": confidence,
                "tier": tier,
                "language_name": result.get("language_name", detected),
            }
        except Exception as e:
            logger.warning("语言检测 LLM 调用失败，默认英文: %s", e)
            return {"detected": "en", "confidence": "low", "tier": 1, "language_name": "英文"}

    # ═══════════════════════════════════════════════════════════
    # 条款翻译
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _build_clause_prompt(
        clause: Clause,
        source_lang: str,
        target_lang: str,
        tier: int,
        total_clauses: int,
    ) -> str:
        """构建单条条款的翻译提示词"""
        source_name = LANG_NAMES.get(source_lang, source_lang)
        target_name = LANG_NAMES.get(target_lang, target_lang)

        prompt = f"""将以下合同条款从{source_name}翻译为{target_name}。
条款序号：第 {clause.index + 1} 条 / 共 {total_clauses} 条
条款标题：{clause.title}

原文：
{clause.content}

请直接输出翻译后的条款文本。"""

        if tier == 2:
            prompt += "\n注意：不确定的术语请标注【需确认】。"
        elif tier == 3:
            prompt += "\n注意：请以目标语言的法律文书风格重新表达，不确定处标注【需确认：原文术语】。"
        return prompt

    @staticmethod
    async def translate_clause_stream(
        clause: Clause,
        source_lang: str,
        target_lang: str,
        tier: int,
        total_clauses: int,
        provider: Optional[str] = None,
        model: str = "",
        instruction: str = "",
    ) -> AsyncIterator[dict]:
        """流式翻译单条条款，yield token/clause_done/error 事件"""
        system = TRANSLATION_SYSTEM_PROMPT
        if tier == 2:
            system += TIER2_SUFFIX
        elif tier == 3:
            system += TIER3_SUFFIX

        user_prompt = TranslationEngine._build_clause_prompt(
            clause, source_lang, target_lang, tier, total_clauses
        )
        if instruction:
            user_prompt += f"\n\n特别要求：{instruction}"

        try:
            llm = ProviderRegistry.resolve(provider)
            request = LLMRequest(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                model=model,
                temperature=0.2,
                max_tokens=2048,
                stream=True,
            )

            full_translation = ""
            async for token in llm.chat_stream(request):
                full_translation += token
                yield {"event": "token", "data": token}

            yield {
                "event": "clause_done",
                "data": {
                    "clause_index": clause.index,
                    "clause_id": clause.id,
                    "original": clause.content,
                    "translated": full_translation.strip(),
                },
            }
        except Exception as e:
            logger.error(
                "条款 %d 翻译失败: %s", clause.index, e
            )
            yield {
                "event": "clause_error",
                "data": {
                    "clause_index": clause.index,
                    "clause_id": clause.id,
                    "error": str(e),
                },
            }

    # ═══════════════════════════════════════════════════════════
    # 文本翻译（审核报告等）
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    async def translate_text_stream(
        content: str,
        target_lang: str,
        source_lang: Optional[str] = None,
        provider: Optional[str] = None,
        model: str = "",
    ) -> AsyncIterator[dict]:
        """流式翻译任意文本，yield progress/token/done 事件"""
        # 检测源语言
        if not source_lang:
            detect_result = await TranslationEngine.detect_language(content, provider)
            source_lang = detect_result["detected"]
            tier = detect_result["tier"]
            yield {"event": "progress", "data": {"stage": "detect", "detected": source_lang, "tier": tier, "language_name": detect_result["language_name"]}}
        else:
            tier = TranslationEngine.classify_tier(source_lang, target_lang)

        source_name = LANG_NAMES.get(source_lang, source_lang)
        target_name = LANG_NAMES.get(target_lang, target_lang)

        system = TRANSLATION_SYSTEM_PROMPT.replace("合同条款", "文本")
        if tier == 2:
            system += TIER2_SUFFIX
        elif tier == 3:
            system += TIER3_SUFFIX

        user_prompt = f"请将以下{source_name}文本翻译为{target_name}，直接输出翻译结果：\n\n{content}"

        try:
            llm = ProviderRegistry.resolve(provider)
            request = LLMRequest(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                model=model,
                temperature=0.2,
                max_tokens=4096,
                stream=True,
            )

            full_text = ""
            async for token in llm.chat_stream(request):
                full_text += token
                yield {"event": "token", "data": token}

            yield {
                "event": "done",
                "data": {
                    "content": full_text.strip(),
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                },
            }
        except Exception as e:
            logger.error("文本翻译失败: %s", e)
            yield {"event": "error", "data": str(e)}
