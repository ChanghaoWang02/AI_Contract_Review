"""自定义审核规则 API"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import CustomRule
from app.schemas import RuleCreate, RuleOut

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=list[RuleOut])
async def list_rules(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """获取审核规则列表"""
    rules = (
        db.query(CustomRule)
        .order_by(CustomRule.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return rules


@router.post("", response_model=RuleOut)
async def create_rule(body: RuleCreate, db: Session = Depends(get_db)):
    """创建自定义审核规则"""
    rule = CustomRule(
        name=body.name,
        prompt_template=body.prompt_template,
        category=body.category,
        is_active=body.is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    logger.info("规则已创建 | id=%d | name=%s | category=%s", rule.id, rule.name, rule.category)
    return rule


@router.put("/{rule_id}", response_model=RuleOut)
async def update_rule(rule_id: int, body: RuleCreate, db: Session = Depends(get_db)):
    """更新审核规则"""
    rule = db.query(CustomRule).filter(CustomRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "规则不存在。")
    if rule.category == "system":
        raise HTTPException(400, "系统默认规则不可修改。")

    rule.name = body.name
    rule.prompt_template = body.prompt_template
    rule.category = body.category
    rule.is_active = body.is_active
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
async def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    """删除审核规则"""
    rule = db.query(CustomRule).filter(CustomRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "规则不存在。")
    if rule.category == "system":
        raise HTTPException(400, "系统默认规则不可删除，可设为停用。")

    db.delete(rule)
    db.commit()
    logger.info("规则已删除 | id=%d | name=%s", rule_id, rule.name)
    return {"message": "规则已删除。", "id": rule_id}


@router.patch("/{rule_id}/toggle", response_model=RuleOut)
async def toggle_rule(rule_id: int, db: Session = Depends(get_db)):
    """切换规则启用状态"""
    rule = db.query(CustomRule).filter(CustomRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "规则不存在。")
    if rule.category == "system":
        raise HTTPException(400, "系统默认规则不可修改启用状态。")

    rule.is_active = not rule.is_active
    db.commit()
    db.refresh(rule)
    return rule
