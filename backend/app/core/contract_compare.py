"""合同对比审核引擎 — 条款匹配 + AI 差异分析 + SSE 流式输出"""

import json
import re
import logging
from difflib import SequenceMatcher
from typing import AsyncIterator

from app.core.chunker import ContractChunker, Clause
from app.core.llm.base import LLMRequest
from app.core.llm.registry import ProviderRegistry
from app.core.reviewer import ReviewEngine

logger = logging.getLogger(__name__)

# ─── System Prompt ───

COMPARE_SYSTEM_PROMPT = """# 角色与任务
你是一位合同审核律师。对以下条款变更逐条评估，判断对指定方是否有利。

分析视角：{perspective_label}

# 输入格式
每条包含「原条款」和「新条款」，编号对应。

# 输出格式（严格 JSON 数组）
[
  {{"index": 0, "risk": "favorable", "reason": "违约金从10%降至5%，减轻违约责任"}},
  {{"index": 1, "risk": "neutral", "reason": "仅调整条款顺序，未改变权利义务"}},
  {{"index": 2, "risk": "unfavorable", "reason": "新增单方解除权，赋予对方任意终止合同的权利"}}
]

# 判定标准
- favorable：分析视角方获得更多权利、更少义务、更低风险
- neutral：实质性权利义务未改变（措辞微调、结构调整、错别字修正）
- unfavorable：分析视角方承担更多义务、更少权利、更高风险

# 约束
- reason 不超过 30 字，不引用法条
- 无法判断时返回 "neutral"
- 只返回 JSON 数组，不要其他内容"""

PERSPECTIVE_LABELS = {
    "party_a": "甲方（合同中先出现的角色方：出租方/卖方/用人单位/委托方/信息披露方等）",
    "party_b": "乙方（合同中后出现的角色方：承租方/买方/劳动者/服务方/信息接收方等）",
    "neutral": "中立视角（不偏向任一方，仅分析条款变更的客观影响）",
}

# 中文数字 → 数值映射
_CN_NUM_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}

_PAT_CN_ARTICLE = re.compile(r"^第([一二三四五六七八九十百千\d]+)[条章节款]")
_PAT_NUM = re.compile(r"\d+")


def _extract_article_number(clause: Clause) -> int | None:
    """从条款标题提取编号（中文数字或阿拉伯数字），用于第1轮匹配"""
    m = _PAT_CN_ARTICLE.match(clause.title)
    if not m:
        return None
    num_str = m.group(1)
    if num_str.isdigit():
        return int(num_str)
    # 中文数字（简化版：支持一~十）
    return _CN_NUM_MAP.get(num_str)


# ─── 条款匹配 ───


def match_clauses(
    original: list[Clause], new: list[Clause]
) -> list[dict]:
    """
    3 轮条款匹配算法。
    返回变更列表，每项: {
        clause_id, change (modified|added|deleted),
        old_clause, new_clause, old_text, new_text
    }
    """
    matched_pairs: list[tuple[Clause | None, Clause | None]] = []
    orig_used = set()
    new_used = set()

    # ── 第 1 轮：编号匹配 ──
    for oc in original:
        if oc.index in orig_used:
            continue
        oc_num = _extract_article_number(oc)
        if oc_num is None:
            continue
        for nc in new:
            if nc.index in new_used:
                continue
            nc_num = _extract_article_number(nc)
            if nc_num == oc_num:
                sim = SequenceMatcher(None, oc.content, nc.content).ratio()
                if sim >= 0.4:
                    matched_pairs.append((oc, nc))
                    orig_used.add(oc.index)
                    new_used.add(nc.index)
                    break

    # ── 第 2 轮：标题包含 ──
    for oc in original:
        if oc.index in orig_used:
            continue
        for nc in new:
            if nc.index in new_used:
                continue
            if oc.title in nc.title or nc.title in oc.title:
                sim = SequenceMatcher(None, oc.content, nc.content).ratio()
                if sim >= 0.4:
                    matched_pairs.append((oc, nc))
                    orig_used.add(oc.index)
                    new_used.add(nc.index)
                    break

    # ── 第 3 轮：全文本相似度兜底 ──
    unmatched_orig = [c for c in original if c.index not in orig_used]
    unmatched_new = [c for c in new if c.index not in new_used]

    for oc in unmatched_orig[:]:
        best_sim = 0.0
        best_nc = None
        for nc in unmatched_new:
            if nc.index in new_used:
                continue
            sim = SequenceMatcher(None, oc.content, nc.content).ratio()
            if sim > best_sim:
                best_sim = sim
                best_nc = nc
        if best_sim >= 0.6 and best_nc is not None:
            matched_pairs.append((oc, best_nc))
            orig_used.add(oc.index)
            new_used.add(best_nc.index)
            unmatched_orig.remove(oc)
            unmatched_new.remove(best_nc)

    # ── 构建变更列表 ──
    changes: list[dict] = []

    # 未匹配的原条款 → deleted
    for oc in unmatched_orig:
        changes.append({
            "clause_id": oc.id,
            "change": "deleted",
            "old_text": oc.content,
            "new_text": "",
            "risk": "neutral",
            "reason": "已删除条款",
            "old_title": oc.title,
            "new_title": "",
        })

    # 未匹配的新条款 → added
    for nc in unmatched_new:
        changes.append({
            "clause_id": f"new_{nc.index}",
            "change": "added",
            "old_text": "",
            "new_text": nc.content,
            "risk": "neutral",
            "reason": "新增条款",
            "old_title": "",
            "new_title": nc.title,
        })

    # 匹配的条款 → modified（文本不同）或跳过（相同）
    for oc, nc in matched_pairs:
        if oc.content.strip() == nc.content.strip():
            continue  # 无变更，不报告
        changes.append({
            "clause_id": oc.id,
            "change": "modified",
            "old_text": oc.content,
            "new_text": nc.content,
            "risk": "unknown",  # 待 AI 判定
            "reason": "",
            "old_title": oc.title,
            "new_title": nc.title,
        })

    # 按原条款顺序排列
    changes.sort(key=lambda c: (
        int(c["clause_id"].split("_")[1]) if c["clause_id"].startswith("clause_") and
        c["clause_id"].split("_")[1].isdigit() else 9999
    ))

    return changes


# ─── AI 批量分析 ───


def _try_parse_compare_response(content: str) -> list[dict] | None:
    """从 AI 响应中提取 JSON 数组（多策略兼容，优先匹配 AI prompt 要求的数组格式）"""
    candidates: list[str] = []

    # 策略1: 直接解析
    candidates.append(content.strip())

    # 策略2: 从 markdown 代码块提取
    for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", content):
        candidates.append(m.group(1).strip())

    # 策略3: 提取第一个 [ 到最后一个 ] 之间的内容（数组格式）
    start = content.find("[")
    end = content.rfind("]")
    if start != -1 and end != -1 and end > start:
        candidates.append(content[start:end + 1])

    for candidate in candidates:
        try:
            result = json.loads(candidate)
            if isinstance(result, list):
                return result
            # 如果是 dict，提取 clauses 或直接返回 None 让调用方回退
            if isinstance(result, dict):
                arr = result.get("clauses") or result.get("results") or []
                if isinstance(arr, list) and len(arr) > 0:
                    return arr
        except (json.JSONDecodeError, ValueError, TypeError):
            # 尝试清理控制字符后重试
            try:
                fixed = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", candidate)
                result = json.loads(fixed)
                if isinstance(result, list):
                    return result
                if isinstance(result, dict):
                    arr = result.get("clauses") or result.get("results") or []
                    if isinstance(arr, list) and len(arr) > 0:
                        return arr
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
            continue

    return None


async def analyze_changes(
    modified_items: list[dict],
    perspective: str,
    provider: str | None = None,
    model: str = "",
) -> list[dict]:
    """
    对 modified 条款逐批调用 AI 分析。
    每批 ≤ 5 条，单批失败整批标记 unknown。
    返回更新后的 modified_items（带 risk + reason）。
    """
    BATCH_SIZE = 5
    for i in range(0, len(modified_items), BATCH_SIZE):
        batch = modified_items[i : i + BATCH_SIZE]

        # 构建 prompt
        items_text = []
        for j, item in enumerate(batch):
            items_text.append(
                f"变更 {j}：\n原条款：{item['old_text'][:500]}\n新条款：{item['new_text'][:500]}"
            )
        user_prompt = "\n\n".join(items_text)

        perspective_label = PERSPECTIVE_LABELS.get(perspective, PERSPECTIVE_LABELS["neutral"])
        system_prompt = COMPARE_SYSTEM_PROMPT.format(perspective_label=perspective_label)

        # 调用 LLM（复用 fallback 链）
        providers_to_try = ReviewEngine._resolve_fallback_chain(provider)
        batch_success = False

        for p in providers_to_try:
            try:
                llm = ProviderRegistry.resolve(p)
                request = LLMRequest(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    model=model,
                    temperature=0.3,
                    max_tokens=2048,
                    stream=False,
                )
                response = await llm.chat(request)

                # 先尝试直接解析 JSON 数组（AI prompt 要求的格式）
                results = _try_parse_compare_response(response.content)
                if results is not None:
                    for j, item in enumerate(batch):
                        result = results[j] if j < len(results) else {}
                        risk = result.get("risk", "unknown")
                        reason = result.get("reason", "")
                        if risk not in ("favorable", "unfavorable", "neutral"):
                            risk = "unknown"
                        item["risk"] = risk
                        item["reason"] = reason[:100]
                    batch_success = True
                    break

                # 回退：尝试用 _parse_json_response 解析（兼容对象格式）
                parsed = ReviewEngine._parse_json_response(response.content)

                # _parse_json_response 会返回 _parse_error 标记的 dict 或真正的 result
                if isinstance(parsed, dict) and parsed.get("_parse_error"):
                    # 失败 → 整批 unknown
                    logger.warning(
                        f"AI 分析批次 {i // BATCH_SIZE + 1} JSON 解析失败: "
                        f"{parsed.get('summary', '')[:100]}"
                    )
                    for item in batch:
                        item["risk"] = "unknown"
                        item["reason"] = "AI 分析失败"
                    break

                # 正常解析：可能是 JSON 数组或包装在 clauses 里
                results = parsed if isinstance(parsed, list) else parsed.get("clauses", [])

                for j, item in enumerate(batch):
                    result = results[j] if j < len(results) else {}
                    risk = result.get("risk", "unknown")
                    reason = result.get("reason", "")
                    if risk not in ("favorable", "unfavorable", "neutral"):
                        risk = "unknown"
                    item["risk"] = risk
                    item["reason"] = reason[:100]  # 截断，安全
                batch_success = True
                break

            except Exception as e:
                if not ReviewEngine._is_transient_error(e):
                    logger.error(f"AI 分析批次永久错误: {e}")
                    break
                if p != providers_to_try[-1]:
                    logger.warning(f"AI 分析降级: {p} → next | {e}")

        if not batch_success:
            logger.warning(f"AI 分析批次 {i // BATCH_SIZE + 1} 全部失败")
            for item in batch:
                item["risk"] = "unknown"
                item["reason"] = "AI 分析失败"

    return modified_items


# ─── SSE 流水线 ───


# SSE 控制字符清理（复用 draft.py 逻辑）
_SSE_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _sanitize_sse(data: dict) -> str:
    """递归清理 dict 中的控制字符后序列化为 JSON"""
    def _clean(obj):
        if isinstance(obj, str):
            return _SSE_CTRL_RE.sub("", obj)
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean(v) for v in obj]
        return obj
    return json.dumps(_clean(data), ensure_ascii=False)


async def compare_stream(
    original_clauses: list[Clause],
    new_text: str,
    perspective: str = "neutral",
    provider: str | None = None,
    model: str = "",
) -> AsyncIterator[str]:
    """
    SSE 流式对比审核流水线。
    yield SSE 格式字符串（含 `data: ...\n\n`）。
    """
    # ── Phase 1: 解析 + 切分新版合同 ──
    yield f"data: {_sanitize_sse({'event': 'progress', 'data': {'phase': 'parsing', 'detail': '正在解析新版合同...'}})}\n\n"

    new_clauses = ContractChunker.split(new_text)
    if not new_clauses:
        yield f"data: {_sanitize_sse({'event': 'error', 'data': {'message': '新版合同内容为空，无法对比'}})}\n\n"
        return

    # ── Phase 2: 条款匹配 ──
    yield f"data: {_sanitize_sse({'event': 'progress', 'data': {'phase': 'matching', 'detail': f'正在匹配条款（原 {len(original_clauses)} 条 vs 新 {len(new_clauses)} 条）...'}})}\n\n"

    if len(original_clauses) <= 1 and len(new_clauses) <= 1:
        yield f"data: {_sanitize_sse({'event': 'error', 'data': {'message': '两份合同均无法拆分为多条条款，请检查文件内容'}})}\n\n"
        return

    changes = match_clauses(original_clauses, new_clauses)

    # 分离 modified vs added/deleted
    modified = [c for c in changes if c["change"] == "modified"]
    added_deleted = [c for c in changes if c["change"] != "modified"]

    # ── Phase 3: AI 分析 ──
    if modified:
        yield f"data: {_sanitize_sse({'event': 'progress', 'data': {'phase': 'analyzing', 'detail': f'检测到 {len(modified)} 条变更，正在分析...'}})}\n\n"
        modified = await analyze_changes(modified, perspective, provider, model)
        yield f"data: {_sanitize_sse({'event': 'progress', 'data': {'phase': 'analyzing_done', 'detail': f'AI 分析完成，共 {len(modified)} 条'}})}\n\n"
    else:
        yield f"data: {_sanitize_sse({'event': 'progress', 'data': {'phase': 'analyzing', 'detail': '未检测到实质性变更'}})}\n\n"

    # ── Phase 4: 逐条发送 clause 事件 ──
    all_changes = modified + added_deleted
    # 重新按顺序排列
    all_changes.sort(key=lambda c: (
        int(c["clause_id"].split("_")[1]) if c["clause_id"].startswith("clause_") and
        c["clause_id"].split("_")[1].isdigit() else 9999
    ))

    for c in all_changes:
        event_data = {
            "clause_id": c["clause_id"],
            "change": c["change"],
            "risk": c["risk"],
            "reason": c["reason"],
            "old_text": c["old_text"],
            "new_text": c["new_text"],
            "old_title": c.get("old_title", ""),
            "new_title": c.get("new_title", ""),
        }
        yield f"data: {_sanitize_sse({'event': 'clause', 'data': event_data})}\n\n"

    # ── 汇总统计 ──
    stats = {
        "total": len(all_changes),
        "modified": sum(1 for c in all_changes if c["change"] == "modified"),
        "added": sum(1 for c in all_changes if c["change"] == "added"),
        "deleted": sum(1 for c in all_changes if c["change"] == "deleted"),
        "favorable": sum(1 for c in all_changes if c["risk"] == "favorable"),
        "neutral": sum(1 for c in all_changes if c["risk"] == "neutral"),
        "unfavorable": sum(1 for c in all_changes if c["risk"] == "unfavorable"),
        "unknown": sum(1 for c in all_changes if c["risk"] == "unknown"),
        "token_usage": 0,
    }
    yield f"data: {_sanitize_sse({'event': 'done', 'data': stats})}\n\n"

    logger.info(
        "Contract compare 完成 | changes=%d modified=%d added=%d deleted=%d",
        stats["total"], stats["modified"], stats["added"], stats["deleted"],
    )
