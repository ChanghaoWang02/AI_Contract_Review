"""翻译相关 Pydantic 模型"""

from pydantic import BaseModel
from typing import Optional


class TranslateGenerateRequest(BaseModel):
    """合同全文翻译（SSE 流式）"""
    contract_id: int
    target_lang: str = "zh"          # 目标语言
    provider: Optional[str] = None
    model: Optional[str] = None


class TranslateClauseRequest(BaseModel):
    """单条条款重新翻译（SSE 流式）"""
    contract_id: int
    clause_index: int
    original_text: str
    instruction: str = ""            # 编辑指令（可选）


class TranslateTextRequest(BaseModel):
    """任意文本翻译（SSE 流式）"""
    content: str
    source_lang: Optional[str] = None  # null = 自动检测
    target_lang: str
    provider: Optional[str] = None
    model: Optional[str] = None


class TranslateSaveRequest(BaseModel):
    """译文保存为子合同"""
    contract_id: int
    translated_content: str
    source_lang: str
    target_lang: str
    filename: str
