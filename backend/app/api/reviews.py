"""审核管理 API"""

import json
import logging
import re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Contract, Review, CustomRule
from app.schemas import ReviewOut, ReviewCreate, FindingsOutput
from app.core.chunker import ContractChunker
from app.core.reviewer import ReviewEngine
from app.core.pdf_renderer import PDFReportBuilder, ExportOptions, sanitize_filename

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


def _derive_risk_level(score: int) -> str:
    """根据评分推导风险等级（与系统提示词一致：0-45 高，46-70 中，71-100 低）"""
    if score <= 45:
        return "high"
    elif score <= 70:
        return "medium"
    return "low"


def _build_review_out(review: Review) -> ReviewOut:
    """构建包含解析后 findings 的 ReviewOut"""
    data = ReviewOut.model_validate(review)
    if review.findings_json:
        try:
            data.findings = FindingsOutput.model_validate(
                json.loads(review.findings_json)
            )
        except json.JSONDecodeError:
            logger.warning(f"Review {review.id} findings_json is not valid JSON, skipping")
        except Exception as e:
            logger.warning(f"Review {review.id} findings validation failed: {type(e).__name__}: {e}")
    return data


@router.post("", response_model=ReviewOut)
async def create_review(body: ReviewCreate, db: Session = Depends(get_db)):
    """创建审核任务"""
    contract = db.query(Contract).filter(Contract.id == body.contract_id).first()
    if not contract:
        raise HTTPException(404, "合同不存在。")

    # 获取活跃规则
    rules = (
        db.query(CustomRule)
        .filter(CustomRule.is_active == True)  # noqa: E712
        .all()
    )
    rule_texts = [r.prompt_template for r in rules] if rules else None

    # 分割条款
    clauses = ContractChunker.split(contract.content)
    if not clauses:
        raise HTTPException(400, "合同内容为空，无法审核。")

    # 创建审核记录
    review = Review(
        contract_id=body.contract_id,
        status="processing",
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    try:
        result = await ReviewEngine.review(
            clauses=clauses,
            custom_rules=rule_texts,
            provider=body.provider,
            model=body.model,
        )
        findings = result["findings"]

        review.overall_score = int(findings.get("overall_score", 0))
        if result.get("parse_error"):
            review.status = "error"
            review.summary = "AI 审核输出格式异常，无法解析为 JSON，请重试。"
            logger.error(f"Review {review.id}: LLM JSON parse failed, raw output stored in findings_json")
        else:
            review.status = "completed"
            review.summary = findings.get("summary", "")
            review.risk_level = _derive_risk_level(review.overall_score)
        review.findings_json = json.dumps(findings, ensure_ascii=False)
        review.token_usage = result["token_usage"]
        review.provider_used = result["provider_used"]
        review.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        review.status = "error"
        review.summary = f"审核失败: {str(e)}"
        logger.error(f"Review {review.id}: exception: {e}")
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.error(f"Review {review.id}: failed to persist error status")

    db.refresh(review)
    return _build_review_out(review)


@router.get("/{review_id}", response_model=ReviewOut)
async def get_review(review_id: int, db: Session = Depends(get_db)):
    """获取审核结果"""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(404, "审核记录不存在。")
    return _build_review_out(review)


@router.post("/stream")
async def create_review_stream(body: ReviewCreate, db: Session = Depends(get_db)):
    """创建审核任务并 SSE 流式返回进度"""
    contract = db.query(Contract).filter(Contract.id == body.contract_id).first()
    if not contract:
        raise HTTPException(404, "合同不存在。")

    rules = (
        db.query(CustomRule)
        .filter(CustomRule.is_active == True)  # noqa: E712
        .all()
    )
    rule_texts = [r.prompt_template for r in rules] if rules else None

    clauses = ContractChunker.split(contract.content)
    if not clauses:
        raise HTTPException(400, "合同内容为空，无法审核。")

    review = Review(contract_id=body.contract_id, status="processing")
    db.add(review)
    db.commit()
    db.refresh(review)

    async def generate():
        full_response = ""
        try:
            async for event in ReviewEngine.review_stream(
                clauses=clauses,
                custom_rules=rule_texts,
                provider=body.provider,
                model=body.model,
            ):
                if event["event"] == "token":
                    full_response += event["data"]
                    yield f"data: {_sse_encode(event)}\n\n"
                elif event["event"] == "done":
                    data = json.loads(event["data"])
                    data["review_id"] = review.id
                    findings = data["findings"]
                    review.overall_score = int(findings.get("overall_score", 0))
                    if data.get("parse_error"):
                        review.status = "error"
                        review.summary = "AI 输出格式异常，请重试"
                    else:
                        review.status = "completed"
                        review.summary = findings.get("summary", "")
                        review.risk_level = _derive_risk_level(review.overall_score)
                    review.findings_json = json.dumps(findings, ensure_ascii=False)
                    review.token_usage = data.get("token_usage")
                    review.provider_used = data.get("provider_used")
                    review.completed_at = datetime.now(timezone.utc)
                    try:
                        db.commit()
                    except Exception:
                        db.rollback()
                    done_event = {"event": "done", "data": json.dumps(data, ensure_ascii=False)}
                    yield f"data: {_sse_encode(done_event)}\n\n"
        except Exception as e:
            review.status = "error"
            review.summary = f"审核失败: {str(e)}"
            try:
                db.commit()
            except Exception:
                db.rollback()
            yield f"data: {_sse_encode({'event': 'error', 'data': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/{review_id}/stream")
async def stream_review(review_id: int, db: Session = Depends(get_db)):
    """SSE 流式获取已有审核结果"""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(404, "审核记录不存在。")

    async def generate():
        if review.findings_json:
            try:
                findings = json.loads(review.findings_json)
                yield f"data: {_sse_encode({'event': 'done', 'data': json.dumps(findings, ensure_ascii=False)})}\n\n"
            except json.JSONDecodeError:
                yield f"data: {_sse_encode({'event': 'error', 'data': '无法解析审核结果'})}\n\n"
        else:
            yield f"data: {_sse_encode({'event': 'error', 'data': '审核结果为空'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/by-contract/{contract_id}", response_model=list[ReviewOut])
async def list_reviews(contract_id: int, db: Session = Depends(get_db)):
    """获取某合同的所有审核记录"""
    reviews = (
        db.query(Review)
        .filter(Review.contract_id == contract_id)
        .order_by(Review.created_at.desc())
        .all()
    )
    return [_build_review_out(r) for r in reviews]


@router.get("/{review_id}/export")
async def export_review_pdf(
    review_id: int,
    risk_filter: str = "high,medium,low",
    sections: str = "cover,summary,clauses,disclaimer",
    db: Session = Depends(get_db),
):
    """导出审核报告为 PDF

    参数:
        risk_filter: 逗号分隔的风险等级过滤 (high,medium,low)
        sections: 逗号分隔的章节开关 (cover,summary,clauses,disclaimer)
    """
    from fastapi.responses import Response

    # 查询审核记录 + 关联合同
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(404, "审核记录不存在。")

    # 状态校验
    if review.status == "processing":
        raise HTTPException(
            409,
            f"审核尚未完成，无法导出报告。当前状态：{review.status}",
        )
    if review.status == "error" or review.status == "pending":
        raise HTTPException(
            422,
            f"审核未成功（状态：{review.status}），无法导出。",
        )

    # 解析 findings
    if not review.findings_json:
        raise HTTPException(
            500,
            "审核数据异常，请联系管理员。",
        )

    try:
        findings = json.loads(review.findings_json)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.error("Review %d findings_json 损坏: %s", review_id, e)
        raise HTTPException(
            500,
            "审核数据异常，请联系管理员。",
        )

    # 解析导出选项
    try:
        options = ExportOptions.from_query_params(
            risk_filter=risk_filter,
            sections=sections,
        )
    except Exception as e:
        logger.warning("Review %d export options 解析失败: %s", review_id, e)
        options = ExportOptions()

    # 获取合同文件名
    contract_name = "未知合同"
    if review.contract:
        contract_name = review.contract.original_filename or review.contract.filename or "未知合同"

    # 生成 PDF
    try:
        builder = PDFReportBuilder()
        pdf_bytes = builder.build(
            findings=findings,
            contract_filename=contract_name,
            completed_at=review.completed_at or review.created_at,
            overall_score=review.overall_score or findings.get("overall_score", 0),
            risk_level=review.risk_level or "medium",
            provider_used=review.provider_used or "unknown",
            options=options,
        )
    except Exception as e:
        logger.error("Review %d PDF 生成失败: %s", review_id, e, exc_info=True)
        raise HTTPException(
            500,
            "PDF 生成失败，请重试。",
        )

    # 构建文件名：RFC 5987 编码中文名 + ASCII fallback
    safe_name = sanitize_filename(contract_name)
    date_str = (review.completed_at or review.created_at).strftime("%Y-%m-%d")
    from urllib.parse import quote
    # ASCII fallback: 去掉非 ASCII 字符，使用纯英文文件名
    ascii_name = safe_name.encode("ascii", errors="ignore").decode("ascii")
    if not ascii_name:
        ascii_name = "contract"
    filename_cn = f"审核报告_{safe_name}_{date_str}.pdf"
    filename_ascii = f"ATCR_Review_{ascii_name}_{date_str}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{filename_ascii}\"; "
                f"filename*=UTF-8''{quote(filename_cn)}"
            ),
        },
    )
