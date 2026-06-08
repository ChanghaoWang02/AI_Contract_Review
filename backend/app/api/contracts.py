"""合同管理 API"""

import logging
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.config import get_settings
from app.db.session import get_db
from sqlalchemy import func
from app.models import Contract, Review
from app.schemas import ContractOut, ContractDetail, SaveDraftRequest
from app.core.parser import ContractParser
from app.core.chunker import ContractChunker

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=ContractOut)
async def upload_contract(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传合同文件并解析"""
    settings = get_settings()

    # 校验文件类型
    if not file.filename:
        raise HTTPException(400, "文件名不能为空。")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            400,
            f"不支持的文件格式: .{ext}。支持: {settings.allowed_extensions}",
        )

    # 校验文件大小
    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            400,
            f"文件过大 ({size_mb:.1f}MB)。最大: {settings.max_upload_size_mb}MB",
        )

    # 解析文件
    try:
        result = ContractParser.parse(file_bytes, ext)
    except Exception as e:
        raise HTTPException(400, f"文件解析失败: {str(e)}")

    # 分割条款
    clauses = ContractChunker.split(result.text)

    # 存储
    safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    logger.info(
        "合同上传 | file=%s | size=%.1fMB | type=%s | clauses=%d",
        file.filename, size_mb, ext, len(clauses),
    )
    contract = Contract(
        filename=safe_name,
        original_filename=file.filename,
        content=result.text,
        content_type=ext,
        file_size=len(file_bytes),
        clause_count=len(clauses),
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)

    return contract


@router.get("", response_model=list[ContractOut])
async def list_contracts(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """获取合同列表（含审核状态）"""
    contracts = (
        db.query(Contract)
        .order_by(Contract.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # 批量获取 review_count，避免 N+1
    if contracts:
        contract_ids = [c.id for c in contracts]
        rows = (
            db.query(Review.contract_id, func.count(Review.id))
            .filter(Review.contract_id.in_(contract_ids))
            .group_by(Review.contract_id)
            .all()
        )
        counts = {row[0]: row[1] for row in rows}
        for c in contracts:
            c.review_count = counts.get(c.id, 0)

    return contracts


@router.get("/{contract_id}", response_model=ContractDetail)
async def get_contract(contract_id: int, db: Session = Depends(get_db)):
    """获取合同详情（含原文）"""
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(404, "合同不存在。")
    return contract


@router.delete("/{contract_id}")
async def delete_contract(contract_id: int, db: Session = Depends(get_db)):
    """删除合同及其审核记录"""
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(404, "合同不存在。")
    db.delete(contract)
    db.commit()
    logger.info("合同已删除 | id=%d | file=%s", contract_id, contract.original_filename or contract.filename)
    return {"message": "合同已删除。", "id": contract_id}


@router.post("/save-draft", response_model=ContractOut)
async def save_contract_from_draft(
    body: SaveDraftRequest,
    db: Session = Depends(get_db),
):
    """从起草页保存合同（JSON body）"""
    content_bytes = body.content.encode("utf-8")
    contract = Contract(
        filename=body.filename,
        original_filename=body.filename,
        content=body.content,
        content_type=body.content_type,
        source="draft",
        file_size=len(content_bytes),
        clause_count=0,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    logger.info("合同已保存 | id=%d | filename=%s | 大小=%d chars", contract.id, body.filename, len(body.content))
    return contract
