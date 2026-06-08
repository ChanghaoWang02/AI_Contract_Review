"""AI 审核引擎"""

import json
import logging
import re as _re  # 用于 JSON 解析中的控制字符清理
from typing import AsyncIterator
from app.config import get_settings
from app.core.llm.base import LLMRequest
from app.core.llm.registry import ProviderRegistry
from app.core.chunker import Clause

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 合同审核 System Prompt
# ═══════════════════════════════════════════════════════════

SYSTEM_PROMPT = """# 角色与目标
你是一位拥有20年中国法律实务经验的合同审核专家。你的核心任务是：对用户提供的合同条款进行全面、客观的法律审核，识别潜在风险，并给出可直接操作的具体修改建议。

# 行为边界与禁令
- 你只进行法律风险分析和文字建议，不构成正式法律意见；必要时应提示用户咨询执业律师
- 不得编造不存在的法条或案例
- 不得泄露或记录用户上传的合同内容中的个人身份信息（姓名、身份证号、地址、电话、银行账户等），发现后应在摘要中用 [已脱敏] 替代
- 不得修改原条款之外的用户意图
- 不得对合同签署方的信用、履约能力等做出超出文本范围的判断
- 遇到明显违法内容（如欺诈条款），应明确指出其违法性但不对签署方做刑事指控性定性

# 输出格式与风格约束
- 严格以 JSON 格式返回审核结果，不得在 JSON 之外附加任何解释性文字
- 语言风格：专业、严谨、平实，使用中文法律文书规范用语
- issue 的 detail 字段必须完整描述问题，包含「问题定位 + 风险后果 + 判断依据」三段结构
- suggestion 必须具体到可直接替换原文的措辞，不可仅说"建议修改"
- revised_text 应为完整的修改后条款文本，可直接替代原条款
- risk 等级按如下标准判定：
  * high：存在重大法律风险或缺失关键条款，可能导致合同无效或重大损失
  * medium：存在一定风险需关注，但可通过协商解决
  * low：基本合规，仅存在微小的修饰建议
- overall_score 评分标准：0-45 高风险，46-70 中等风险，71-100 低风险；判分需综合考虑法律风险数量、严重程度、条款缺失情况

# 安全与隐私规则
- 合同中出现的自然人姓名、身份证号、手机号、住址、银行账号，在输出时全部替换为「[已脱敏]」
- 企业工商注册号、统一社会信用代码等公开信息可保留
- 涉及商业秘密的技术参数、金额条款原文保留，但在摘要中不得单独列出数额
- 如用户要求生成完全违背现行法律的条款，应拒绝并说明依据

# 引用与证据策略
- 每条 issue 必须引用对应的合同原文片段（引号标注）
- 如有明确的法律依据（如《民法典》第几条），在 detail 中引用法条编号
- 不确定的内容使用"可能存在"、"建议关注"等措辞，不得假装确定
- 不得引用已废止的法律法规

# 错误与异常处理
- 若合同内容不完整导致无法判断，应在对应的 issue 中明确标注「信息不足，无法完整判断」并说明缺失信息
- 若遇到相互矛盾的条款，应同时指出两条矛盾的条款编号和内容，并给出调和建议
- 若条款超出你的分析能力范围（如高度专业的技术规范），应标注「需专业领域律师进一步审核」
- 若 JSON 输出因字符限制未完成，优先保留高风险条款的分析结果

# 审核维度
你必须覆盖以下四个核心维度：
1. **法律风险**：责任不对等、赔偿责任上限过低、管辖权不明确、违约金过高/过低、单方任意解除权
2. **模糊用语**：使用「合理」「及时」「必要」「适当」「尽力」「重大」等无客观标准的词汇
3. **合规性**：是否符合中国《民法典》合同编通则及典型合同分编的基本要求
4. **完整性**：是否缺少违约责任、争议解决方式、保密条款、知识产权归属、不可抗力、通知送达等关键条款
"""

USER_PROMPT_TEMPLATE = """以下是要审核的合同内容。请严格按照 System Prompt 中的规则进行全面审核，只返回 JSON。

=====

{clauses_text}"""

class ReviewEngine:
    """合同 AI 审核引擎"""

    @classmethod
    def _build_request(
        cls,
        clauses: list[Clause],
        custom_rules: list[str] | None = None,
        provider: str | None = None,
        model: str = "",
        stream: bool = False,
    ) -> tuple["ProviderRegistry", LLMRequest]:
        """构建审核消息（review 和 review_stream 共用）"""
        settings = get_settings()
        llm = ProviderRegistry.resolve(provider)
        if provider and llm.provider_name != provider:
            logger.warning(
                f"Requested provider '{provider}' not available, "
                f"falling back to '{llm.provider_name}'"
            )

        clauses_text = "\n\n---\n\n".join(
            f"[条款{c.index+1}] {c.title}\n{c.content}" for c in clauses
        )
        user_prompt = USER_PROMPT_TEMPLATE.format(clauses_text=clauses_text)
        if custom_rules:
            user_prompt += "\n\n# 用户自定义审核规则\n" + "\n".join(f"- {r}" for r in custom_rules)

        request = LLMRequest(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            temperature=settings.review_default_temperature,
            max_tokens=settings.review_max_tokens,
            stream=stream,
        )
        return llm, request

    @classmethod
    def _build_result(
        cls,
        findings: dict,
        provider_name: str,
        model_name: str,
        token_usage: int | None,
    ) -> dict:
        """构建统一返回结构"""
        return {
            "findings": findings,
            "provider_used": provider_name,
            "model_used": model_name,
            "token_usage": token_usage,
            "parse_error": findings.get("_parse_error", False),
        }

    @classmethod
    async def review(
        cls,
        clauses: list[Clause],
        custom_rules: list[str] = None,
        provider: str = None,
        model: str = None,
    ) -> dict:
        """同步审核，返回完整审核结果（支持 LLM 故障时自动降级 + 长合同自动分片）"""
        # 长合同分片：超过 6000 tokens 时分批审核
        batches = cls._build_batches(clauses)
        if len(batches) > 1:
            return await cls._review_chunked(batches, custom_rules, provider, model)

        providers_to_try = cls._resolve_fallback_chain(provider)
        last_error = None

        for p in providers_to_try:
            try:
                llm, request = cls._build_request(clauses, custom_rules, p, model or "")
                response = await llm.chat(request)
                findings = cls._parse_json_response(response.content)
                return cls._build_result(
                    findings, llm.provider_name, response.model, response.token_usage
                )
            except Exception as e:
                last_error = e
                # 永久错误（认证、权限等）不重试，直接抛出
                if not cls._is_transient_error(e):
                    raise RuntimeError(
                        f"LLM provider '{p}' 永久性错误（非瞬态），已停止重试: {e}"
                    ) from e
                if p != providers_to_try[-1]:
                    logger.warning(
                        f"LLM provider '{p}' failed: {e}. Falling back to next provider..."
                    )

        raise RuntimeError(
            f"所有 LLM 提供商均调用失败 ({', '.join(providers_to_try)})。最后错误: {last_error}"
        )

    @classmethod
    async def review_stream(
        cls,
        clauses: list[Clause],
        custom_rules: list[str] = None,
        provider: str = None,
        model: str = None,
    ) -> AsyncIterator[dict]:
        """流式审核，逐 chunk yield 事件（支持 LLM 故障时自动降级 + 长合同自动分片）"""
        # 长合同分片
        batches = cls._build_batches(clauses)
        if len(batches) > 1:
            async for event in cls._review_chunked_stream(batches, custom_rules, provider, model):
                yield event
            return

        providers_to_try = cls._resolve_fallback_chain(provider)
        last_error = None

        for p in providers_to_try:
            try:
                llm, request = cls._build_request(clauses, custom_rules, p, model or "", stream=True)

                full_response = ""
                async for token in llm.chat_stream(request):
                    full_response += token
                    yield {"event": "token", "data": token}

                findings = cls._parse_json_response(full_response)
                yield {
                    "event": "done",
                    "data": json.dumps(
                        cls._build_result(
                            findings, llm.provider_name, model or "default",
                            # 流式路径无法获取 API 真实 token 数，用字符数近似。
                            # 中文约 1 char ≈ 1.5–2 tokens，len() 对中文合同偏差在可接受范围内。
                            # 非流式路径使用 API 返回的真实 usage.total_tokens，与此不同。
                            len(full_response),
                        ),
                        ensure_ascii=False,
                    ),
                }
                return  # 成功，退出
            except Exception as e:
                last_error = e
                # 永久错误（认证、权限等）不重试，直接报错
                if not cls._is_transient_error(e):
                    yield {
                        "event": "error",
                        "data": f"LLM provider '{p}' 永久性错误: {e}",
                    }
                    return
                if p != providers_to_try[-1]:
                    logger.warning(
                        f"LLM provider '{p}' failed during stream: {e}. Falling back..."
                    )

        # 所有 provider 都失败
        yield {
            "event": "error",
            "data": f"所有 LLM 提供商均调用失败。最后错误: {last_error}",
        }

    @classmethod
    def _resolve_fallback_chain(cls, preferred_provider: str = None) -> list[str]:
        """构建降级链：首选 → 默认 → fallback 列表（去重）"""
        settings = get_settings()
        chain = []
        seen = set()

        for p in [
            preferred_provider,
            settings.llm_default_provider,
            *settings.llm_fallback_providers,
        ]:
            if p and p not in seen:
                chain.append(p)
                seen.add(p)
        return chain

    @staticmethod
    def _is_transient_error(e: Exception) -> bool:
        """判断 LLM 错误是否为瞬态（值得重试）还是永久（应立即停止降级）"""
        name = type(e).__name__
        msg = str(e).lower()

        # 永久错误关键词：认证、权限、配置、资源不存在
        permanent_keywords = [
            'api key', 'apikey', '未配置', 'authentication', 'unauthorized',
            'permission', 'forbidden', 'not found', 'invalid_request_error',
            'invalid api key', 'incorrect api key', '账号', '余额',
        ]
        for kw in permanent_keywords:
            if kw in msg:
                return False

        # 瞬态错误类型：超时、连接、速率限制、服务不可用
        transient_type_names = [
            'Timeout', 'ConnectError', 'ConnectTimeout', 'RemoteProtocolError',
            'ReadTimeout', 'NetworkError', 'RateLimitError', 'ServiceUnavailableError',
            'APITimeoutError', 'APIConnectionError',
        ]
        for t in transient_type_names:
            if t in name:
                return True

        # 默认视为瞬态（保持原有行为，宁可多试一次也不错杀）
        return True

    # ═══════════════════════════════════════════════════════════
    # 长合同分片审核
    # ═══════════════════════════════════════════════════════════

    _CHUNK_TOKEN_LIMIT = 5000  # 每批约 5000 tokens（约 10000 中文字符）

    @classmethod
    def _build_batches(cls, clauses: list[Clause]) -> list[list[Clause]]:
        """将条款列表按 token 预算拆分为多个批次"""
        batches: list[list[Clause]] = []
        current_batch: list[Clause] = []
        current_tokens = 0

        for clause in clauses:
            clause_tokens = len(clause.content) // 2
            if current_batch and current_tokens + clause_tokens > cls._CHUNK_TOKEN_LIMIT:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0
            current_batch.append(clause)
            current_tokens += clause_tokens

        if current_batch:
            batches.append(current_batch)

        return batches if len(batches) > 1 else [clauses]

    @classmethod
    async def _review_chunked(
        cls,
        batches: list[list[Clause]],
        custom_rules: list[str] | None,
        provider: str | None,
        model: str | None,
    ) -> dict:
        """分批审核并合并结果：每个批次独立审核，单批次失败不丢失已完成结果"""
        all_findings: list[dict] = []
        providers_used: list[str] = []
        models_used: list[str] = []
        total_tokens = 0
        any_parse_error = False

        for i, batch in enumerate(batches):
            logger.info(f"审核批次 {i + 1}/{len(batches)}（{len(batch)} 条）")
            try:
                result = await cls.review(batch, custom_rules, provider, model)
                all_findings.append(result["findings"])
                providers_used.append(
                    f"{result['provider_used']}({result.get('model_used', '?')})"
                )
                models_used.append(result.get("model_used", "unknown"))
                total_tokens += result["token_usage"] or 0
                if result.get("parse_error"):
                    any_parse_error = True
            except Exception as e:
                logger.error(
                    f"批次 {i + 1}/{len(batches)} 审核失败: {e}，"
                    f"已保留前 {i} 个批次的结果"
                )
                # 继续处理剩余批次，不丢失已完成的审核
                continue

        if not all_findings:
            raise RuntimeError(
                f"所有 {len(batches)} 个批次审核均失败，无法生成审核结果"
            )

        merged = cls._merge_batch_results(all_findings, batches)
        return {
            "findings": merged,
            "provider_used": " → ".join(providers_used) if providers_used else "unknown",
            "model_used": " → ".join(models_used) if models_used else "unknown",
            "token_usage": total_tokens,
            "parse_error": any_parse_error,
        }

    @classmethod
    async def _review_chunked_stream(
        cls,
        batches: list[list[Clause]],
        custom_rules: list[str] | None,
        provider: str | None,
        model: str | None,
    ) -> AsyncIterator[dict]:
        """分批流式审核并合并结果：每批次真正流式输出 token，批次间发送 progress 事件"""
        all_findings: list[dict] = []
        providers_used: list[str] = []
        models_used: list[str] = []
        total_tokens = 0
        any_parse_error = False

        for i, batch in enumerate(batches):
            logger.info(f"审核批次 {i + 1}/{len(batches)}（{len(batch)} 条）")
            batch_findings = None
            batch_failed = False

            try:
                # 每个批次通过 review_stream 获取真正的 token 级流式输出
                async for event in cls.review_stream(
                    batch, custom_rules, provider, model
                ):
                    if event["event"] == "token":
                        yield event  # 逐 token 转发给前端
                    elif event["event"] == "done":
                        data = json.loads(event["data"])
                        batch_findings = data.get("findings")
                        providers_used.append(
                            f"{data.get('provider_used', '?')}"
                            f"({data.get('model_used', '?')})"
                        )
                        models_used.append(data.get("model_used", "unknown"))
                        total_tokens += data.get("token_usage", 0) or 0
                        if data.get("parse_error"):
                            any_parse_error = True
                    elif event["event"] == "error":
                        logger.warning(
                            f"批次 {i + 1}/{len(batches)} 失败: {event['data']}"
                        )
                        batch_failed = True
                        break
            except Exception as e:
                logger.error(f"批次 {i + 1}/{len(batches)} 异常: {e}")
                batch_failed = True

            if batch_findings:
                all_findings.append(batch_findings)

            if not batch_failed:
                yield {
                    "event": "progress",
                    "data": f"📋 批次 {i + 1}/{len(batches)} 审核完成",
                }

        if not all_findings:
            yield {
                "event": "error",
                "data": f"所有 {len(batches)} 个批次审核均失败",
            }
            return

        merged = cls._merge_batch_results(all_findings, batches)
        yield {
            "event": "done",
            "data": json.dumps(
                {
                    "findings": merged,
                    "provider_used": (
                        " → ".join(providers_used)
                        if providers_used else "unknown"
                    ),
                    "model_used": (
                        " → ".join(models_used)
                        if models_used else "unknown"
                    ),
                    "token_usage": total_tokens,
                    "parse_error": any_parse_error,
                },
                ensure_ascii=False,
            ),
        }

    @staticmethod
    def _merge_batch_results(
        batch_findings: list[dict],
        batches: list[list[Clause]] | None = None,
    ) -> dict:
        """合并多个批次的审核结果，尝试将 LLM 输出映射回原始条款 ID"""
        all_clauses = []
        overall_scores = []
        summaries = []

        for i, findings in enumerate(batch_findings):
            clauses = findings.get("clauses", [])
            original_clauses = batches[i] if batches and i < len(batches) else []

            for j, clause in enumerate(clauses):
                # 按位置映射回原始 chunker 条款 ID，使前端锚定功能正常工作
                if j < len(original_clauses):
                    clause["id"] = original_clauses[j].id
                    clause["index"] = original_clauses[j].index
                else:
                    # LLM 发现了比输入更多的条款 → 使用带批次前缀的 ID 避免冲突
                    original_id = clause.get("id", f"clause_{j}")
                    clause["id"] = f"batch{i}_{original_id}" if i > 0 else original_id
                    if "index" not in clause:
                        clause["index"] = j
            all_clauses.extend(clauses)

            score = findings.get("overall_score")
            if isinstance(score, (int, float)):
                overall_scores.append(score)

            summary = findings.get("summary", "")
            if summary and not summary.startswith("{"):
                summaries.append(f"[批次{i + 1}] {summary}")

        # 平均分
        avg_score = (
            int(sum(overall_scores) / len(overall_scores))
            if overall_scores else 50
        )

        return {
            "clauses": all_clauses,
            "overall_score": avg_score,
            "summary": "\n".join(summaries) if summaries else "（分批次审核完成）",
        }

    @staticmethod
    def _parse_json_response(content: str) -> dict:
        """从 LLM 响应中提取 JSON（多策略兼容）"""
        candidates: list[str] = []

        # 策略1: 直接解析
        candidates.append(content.strip())

        # 策略2: 从 markdown 代码块提取（多个匹配）
        for m in _re.finditer(r"```(?:json)?\s*([\s\S]*?)```", content):
            candidates.append(m.group(1).strip())

        # 策略3: 提取第一个 { 到最后一个 } 之间的内容
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidates.append(content[start:end + 1])

        for candidate in candidates:
            try:
                result = json.loads(candidate)
                result = _normalize_findings(result)
                return result
            except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
                if len(candidate) < 10:
                    continue
                try:
                    fixed = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', candidate)
                    result = json.loads(fixed)
                    result = _normalize_findings(result)
                    return result
                except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
                    pass
                continue

        logger.warning(
            f"JSON parse failed after {len(candidates)} strategies. "
            f"Content starts: {content[:200]}"
        )
        return {
            "clauses": [],
            "overall_score": 0,
            "summary": content[:200],
            "_parse_error": True,
        }

def _normalize_clause(c: dict) -> dict:
    """规范化单个条款的字段名，兼容不同 LLM 的输出格式"""
    # ID
    if "id" not in c:
        c["id"] = c.get("clause") or c.get("clause_ref") or c.get("clause_id") or f"clause_{hash(str(c))}"
    # 原文
    if "original_text" not in c:
        c["original_text"] = c.get("clause_text") or c.get("original_text") or c.get("content") or ""
    # 摘要
    if "summary" not in c:
        c["summary"] = c.get("title") or c.get("name") or c["original_text"][:30]
    # 风险等级
    if "risk" not in c:
        rl = c.get("risk_level") or c.get("level") or "medium"
        c["risk"] = rl if rl in ("high", "medium", "low") else "medium"
    # issues → 统一类型字段
    if "issues" not in c and "detail" in c:
        c["issues"] = [{"type": c.get("type", "法律风险"), "detail": c["detail"]}]
    if "suggestion" in c and "suggestions" not in c:
        c["suggestions"] = [c["suggestion"]] if isinstance(c["suggestion"], str) else c["suggestion"]
    if "revised_text" not in c:
        c["revised_text"] = c.get("revised") or c.get("revision") or None
    return c


def _normalize_findings(result: dict) -> dict:
    """规范化审核结果的字段结构"""
    # 顶层: issues → clauses
    if "issues" in result and "clauses" not in result:
        result["clauses"] = result.pop("issues")
    # 顶层: missing_clauses 合并到 clauses
    if "missing_clauses" in result and isinstance(result["missing_clauses"], list):
        for mc in result["missing_clauses"]:
            result.setdefault("clauses", []).append({
                "id": "missing",
                "original_text": "",
                "summary": mc if isinstance(mc, str) else mc.get("name", "缺失条款"),
                "risk": "high",
                "issues": [{"type": "缺失条款", "detail": mc if isinstance(mc, str) else mc.get("detail", "")}],
                "suggestions": [],
                "revised_text": None,
            })
    # 规范化每个条款的内部字段
    if "clauses" in result and isinstance(result["clauses"], list):
        result["clauses"] = [_normalize_clause(c) for c in result["clauses"]]
    # overall_score 为数字
    if "overall_score" not in result or not isinstance(result.get("overall_score"), (int, float)):
        result["overall_score"] = 50
    return result
