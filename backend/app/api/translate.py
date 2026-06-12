"""合同翻译 API — SSE 流式翻译 + 文本翻译 + 保存"""

import json
import re
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Contract
from app.schemas.translate import (
    TranslateGenerateRequest,
    TranslateClauseRequest,
    TranslateTextRequest,
    TranslateSaveRequest,
)
from app.core.chunker import ContractChunker
from app.core.translator import TranslationEngine

router = APIRouter()
logger = logging.getLogger(__name__)

# SSE 数据中不允许的控制字符（U+0000-U+001F 除 \t\n\r）
_SSE_CTRL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


def _sanitize_str(s: str) -> str:
    return _SSE_CTRL_RE.sub('', s)


def _sanitize(obj):
    """递归清理 dict/list/str 中的控制字符"""
    if isinstance(obj, str):
        return _sanitize_str(obj)
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def _sse_encode(data: dict) -> str:
    """安全 SSE 编码：清理控制字符并序列化为 JSON"""
    return json.dumps(_sanitize(data), ensure_ascii=False)


@router.post("/generate")
async def translate_generate(body: TranslateGenerateRequest, db: Session = Depends(get_db)):
    """SSE 流式翻译合同全文（逐条条款）"""
    contract = db.query(Contract).filter(Contract.id == body.contract_id).first()
    if not contract:
        raise HTTPException(404, "合同不存在。")
    if not contract.content:
        raise HTTPException(400, "合同内容为空，无法翻译。")

    target_lang = body.target_lang or "zh"

    async def event_generator():
        try:
            # 1. 语言检测
            detect_result = await TranslationEngine.detect_language(
                contract.content, body.provider
            )
            source_lang = detect_result["detected"]
            tier = detect_result["tier"]
            yield f"data: {_sse_encode({'event': 'progress', 'data': {'stage': 'detect', 'detected': source_lang, 'tier': tier, 'language_name': detect_result['language_name']}})}\n\n"

            # 2. 条款分块
            clauses = ContractChunker.split(contract.content)
            if not clauses:
                yield f"data: {_sse_encode({'event': 'error', 'data': '无法解析合同条款'})}\n\n"
                return
            yield f"data: {_sse_encode({'event': 'progress', 'data': {'stage': 'chunked', 'total_clauses': len(clauses)}})}\n\n"

            # 3. 逐条流式翻译
            skipped_clauses = []
            translated_count = 0

            for clause in clauses:
                try:
                    async for event in TranslationEngine.translate_clause_stream(
                        clause=clause,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        tier=tier,
                        total_clauses=len(clauses),
                        provider=body.provider,
                        model=body.model or "",
                    ):
                        if event["event"] == "token":
                            yield f"data: {_sse_encode({'event': 'token', 'data': {'clause_index': clause.index, 'content': event['data']}})}\n\n"
                        elif event["event"] == "clause_done":
                            translated_count += 1
                            yield f"data: {_sse_encode({'event': 'clause_done', 'data': event['data']})}\n\n"
                        elif event["event"] == "clause_error":
                            skipped_clauses.append(event["data"])
                            yield f"data: {_sse_encode({'event': 'clause_error', 'data': event['data']})}\n\n"
                except Exception as e:
                    skipped_clauses.append({
                        "clause_index": clause.index,
                        "clause_id": clause.id,
                        "error": str(e),
                    })
                    yield f"data: {_sse_encode({'event': 'clause_error', 'data': {'clause_index': clause.index, 'clause_id': clause.id, 'error': str(e)}})}\n\n"

            # 4. 完成
            yield f"data: {_sse_encode({'event': 'done', 'data': {'total_clauses': len(clauses), 'translated': translated_count, 'skipped_clauses': skipped_clauses, 'source_lang': source_lang, 'target_lang': target_lang}})}\n\n"

        except Exception as e:
            logger.error("合同翻译全局异常: %s", e, exc_info=True)
            yield f"data: {_sse_encode({'event': 'error', 'data': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream; charset=utf-8")


@router.post("/clause")
async def translate_clause(body: TranslateClauseRequest, db: Session = Depends(get_db)):
    """SSE 流式重新翻译单条条款"""
    contract = db.query(Contract).filter(Contract.id == body.contract_id).first()
    if not contract:
        raise HTTPException(404, "合同不存在。")

    # 检测语言
    detect_result = await TranslationEngine.detect_language(body.original_text)
    source_lang = detect_result["detected"]
    tier = detect_result["tier"]

    # 目标语言：来自请求参数（前端选择）
    target_lang = body.target_lang

    # 构造 Clause 对象
    clause = ContractChunker._build_clause(
        title=f"条款 {body.clause_index + 1}",
        content=body.original_text,
        index=body.clause_index,
    )

    async def event_generator():
        try:
            async for event in TranslationEngine.translate_clause_stream(
                clause=clause,
                source_lang=source_lang,
                target_lang=target_lang,
                tier=tier,
                total_clauses=1,
                provider=None,
                model="",
                instruction=body.instruction,
            ):
                if event["event"] == "token":
                    yield f"data: {_sse_encode({'event': 'token', 'data': event['data']})}\n\n"
                elif event["event"] == "clause_done":
                    yield f"data: {_sse_encode({'event': 'done', 'data': event['data']})}\n\n"
                elif event["event"] == "clause_error":
                    yield f"data: {_sse_encode({'event': 'error', 'data': event['data']})}\n\n"
        except Exception as e:
            yield f"data: {_sse_encode({'event': 'error', 'data': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream; charset=utf-8")


@router.post("/text")
async def translate_text(body: TranslateTextRequest):
    """SSE 流式翻译任意文本（审核报告等）"""
    async def event_generator():
        try:
            async for event in TranslationEngine.translate_text_stream(
                content=body.content,
                target_lang=body.target_lang,
                source_lang=body.source_lang,
                provider=body.provider,
                model=body.model or "",
            ):
                if event["event"] == "progress":
                    yield f"data: {_sse_encode({'event': 'progress', 'data': event['data']})}\n\n"
                elif event["event"] == "token":
                    yield f"data: {_sse_encode({'event': 'token', 'data': event['data']})}\n\n"
                elif event["event"] == "done":
                    yield f"data: {_sse_encode({'event': 'done', 'data': event['data']})}\n\n"
                elif event["event"] == "error":
                    yield f"data: {_sse_encode({'event': 'error', 'data': event['data']})}\n\n"
        except Exception as e:
            logger.error("文本翻译全局异常: %s", e, exc_info=True)
            yield f"data: {_sse_encode({'event': 'error', 'data': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream; charset=utf-8")


@router.post("/save")
async def translate_save(body: TranslateSaveRequest, db: Session = Depends(get_db)):
    """保存译文为新合同（子合同），可直接审核"""
    parent = db.query(Contract).filter(Contract.id == body.contract_id).first()
    if not parent:
        raise HTTPException(404, "原文合同不存在。")

    # 构建文件名
    clean_name = body.filename
    for ext in (".txt", ".pdf", ".docx"):
        if clean_name.lower().endswith(ext):
            clean_name = clean_name.rsplit(".", 1)[0]
            break
    if not clean_name.endswith(f"_{body.target_lang.upper()}"):
        clean_name = f"{clean_name}_{body.target_lang.upper()}"

    # 分块统计
    clause_count = len(ContractChunker.split(body.translated_content))

    child = Contract(
        filename=f"{clean_name}.txt",
        original_filename=f"{clean_name}.txt",
        content=body.translated_content,
        content_type="txt",
        source="translated",
        parent_contract_id=body.contract_id,
        source_lang=body.source_lang,
        target_lang=body.target_lang,
        file_size=len(body.translated_content.encode("utf-8")),
        clause_count=clause_count,
    )
    db.add(child)
    db.commit()
    db.refresh(child)

    logger.info(
        "译文已保存: id=%d parent=%d lang=%s→%s clauses=%d",
        child.id, body.contract_id, body.source_lang, body.target_lang, clause_count,
    )

    return {
        "id": child.id,
        "parent_contract_id": body.contract_id,
        "source": "translated",
        "source_lang": body.source_lang,
        "target_lang": body.target_lang,
        "clause_count": clause_count,
        "filename": child.original_filename,
    }
