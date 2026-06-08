"""AI 对话 API"""

import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Review, Message
from app.schemas import ChatMessageIn, ChatMessageOut
from app.core.llm.base import LLMRequest
from app.core.llm.registry import ProviderRegistry

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/stream")
async def chat_stream(body: ChatMessageIn, db: Session = Depends(get_db)):
    """SSE 流式对话"""

    # 查找审核记录
    review = db.query(Review).filter(Review.id == body.review_id).first()
    if not review:
        raise HTTPException(404, "审核记录不存在。")

    # 保存用户消息
    user_msg = Message(
        review_id=review.id,
        role="user",
        content=body.content,
        anchor_clause_id=body.anchor_clause_id,
        anchor_clause_text=body.anchor_clause_text,
    )
    db.add(user_msg)
    db.commit()

    # 构建消息上下文
    messages = _build_chat_context(review, db, body)

    llm = ProviderRegistry.resolve(body.provider)
    llm_request = LLMRequest(
        messages=messages,
        model=body.model or "",
        temperature=0.5,
        max_tokens=2048,
        stream=True,
    )

    async def event_generator():
        full_content = ""
        try:
            logger.info("Chat stream 开始 | review=%d | anchor=%s", review.id, body.anchor_clause_id or "none")
            async for token in llm.chat_stream(llm_request):
                full_content += token
                yield f"data: {json.dumps({'event': 'token', 'data': token}, ensure_ascii=False)}\n\n"

            # 保存 AI 回复
            assistant_msg = Message(
                review_id=review.id,
                role="assistant",
                content=full_content,
                anchor_clause_id=body.anchor_clause_id,
                anchor_clause_text=body.anchor_clause_text,
            )
            db.add(assistant_msg)
            db.commit()

            logger.info("Chat stream 完成 | review=%d | 回复长度=%d chars", review.id, len(full_content))
            yield f"data: {json.dumps({'event': 'done', 'data': json.dumps({'token_usage': len(full_content) // 2}, ensure_ascii=False)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error("Chat stream 异常 | review=%d | %s: %s", review.id, type(e).__name__, e)
            yield f"data: {json.dumps({'event': 'error', 'data': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{review_id}/history", response_model=list[ChatMessageOut])
async def get_chat_history(review_id: int, db: Session = Depends(get_db)):
    """获取对话历史"""
    messages = (
        db.query(Message)
        .filter(Message.review_id == review_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return messages


def _build_chat_context(
    review: Review,
    db: Session,
    body: ChatMessageIn,
) -> list[dict]:
    """构建对话上下文消息列表（精简版，控制 token 消耗）"""
    messages = []

    # 仅注入审核摘要 + 条款概要，不注入完整合同原文
    has_findings = False
    if review.findings_json:
        try:
            findings = json.loads(review.findings_json)
            summary = findings.get("summary", "")
            # 收集高风险条款标题
            high_risk_clauses = []
            for c in findings.get("clauses", []):
                if c.get("risk") == "high":
                    high_risk_clauses.append(f"  - {c.get('summary', c.get('id', ''))}")
            clause_info = ""
            if high_risk_clauses:
                clause_info = "\n高风险条款：\n" + "\n".join(high_risk_clauses[:8])

            if summary or clause_info:
                messages.append({
                    "role": "system",
                    "content": (
                        "你是一位合同审核专家。以下是合同审核结果摘要：\n"
                        f"{summary}{clause_info}\n\n"
                        "请基于审核结果回答用户问题。回答要具体、可操作。"
                    ),
                })
                has_findings = True
        except (json.JSONDecodeError, Exception):
            pass

    # 如果没有审核结果，注入合同摘要（截取前 2000 字）
    if not has_findings and review.contract:
        snippet = review.contract.content[:2000]
        if snippet:
            messages.append({
                "role": "system",
                "content": (
                    "你是一位合同审核专家。以下是用户合同的片段：\n\n"
                    f"{snippet}\n\n"
                    "请基于此回答用户问题。"
                ),
            })

    # 条款锚定上下文（优先级最高）
    if body.anchor_clause_text:
        messages.append({
            "role": "system",
            "content": f"用户关注的条款：{body.anchor_clause_text[:1000]}",
        })

    # 历史对话（最近 10 条，减少上下文膨胀）
    history = (
        db.query(Message)
        .filter(Message.review_id == review.id)
        .order_by(Message.created_at.desc())
        .limit(10)
        .all()
    )
    history.reverse()  # 恢复时间顺序
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    return messages
