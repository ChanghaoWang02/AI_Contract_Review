"""Pydantic 请求/响应模型"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


# ─── 合同 ───

class ContractOut(BaseModel):
    id: int
    original_filename: str
    content_type: str
    source: str = "upload"
    file_size: int
    clause_count: int
    review_count: int = 0
    review_status: Optional[str] = None  # 'completed' / 'processing' / 'error' / None (no review)
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("source", mode="before")
    @classmethod
    def default_source(cls, v):
        return v if v else "upload"


class ContractDetail(ContractOut):
    content: str
    reviews: list["ReviewBrief"] = []

    model_config = {"from_attributes": True}


# ─── 审核 ───

class ReviewBrief(BaseModel):
    id: int
    status: str
    risk_level: Optional[str]
    overall_score: Optional[int]
    token_usage: Optional[int]
    provider_used: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ClauseIssue(BaseModel):
    type: str   # "模糊用语" / "法律风险" / "合规问题" / "缺失条款"
    detail: str


class ClauseResult(BaseModel):
    id: str
    original_text: str
    summary: str
    risk: str          # high / medium / low
    issues: list[ClauseIssue] = []
    suggestions: list[str] = []
    revised_text: Optional[str] = None

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v):
        return str(v) if v is not None else ""


class FindingsOutput(BaseModel):
    clauses: list[ClauseResult] = []
    overall_score: int = 0
    summary: str = ""


class ReviewOut(BaseModel):
    id: int
    contract_id: int
    status: str
    summary: Optional[str]
    risk_level: Optional[str]
    overall_score: Optional[int]
    findings: Optional[FindingsOutput] = None
    token_usage: Optional[int]
    provider_used: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ReviewCreate(BaseModel):
    contract_id: int
    provider: Optional[str] = None      # 指定模型提供商
    model: Optional[str] = None         # 指定具体模型


# ─── 对话 ───

class ChatMessageIn(BaseModel):
    review_id: int
    content: str
    anchor_clause_id: Optional[str] = None
    anchor_clause_text: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class ChatMessageOut(BaseModel):
    id: int
    review_id: int
    role: str
    content: str
    anchor_clause_id: Optional[str] = None
    anchor_clause_text: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── 规则 ───

class RuleCreate(BaseModel):
    name: str
    prompt_template: str
    category: str = "custom"
    is_active: bool = True


class RuleOut(RuleCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── 合同起草 ───

class DraftGenerateRequest(BaseModel):
    contract_type: str                                   # e.g. "房屋租赁合同" or "自定义"
    form_data: dict = {}                                 # key-value pairs from Step 2
    provider: Optional[str] = None
    model: Optional[str] = None


class DraftChatRequest(BaseModel):
    anchored_clause: str                                 # full text of the anchored clause
    clause_titles: list[str] = []                        # all clause titles for context
    instruction: str                                     # user's editing instruction
    provider: Optional[str] = None
    model: Optional[str] = None


class SaveDraftRequest(BaseModel):
    filename: str
    content: str
    content_type: str = "txt"
