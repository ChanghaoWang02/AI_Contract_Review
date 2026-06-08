"""合同文本条款分割器"""

import re
from typing import NamedTuple


class Clause(NamedTuple):
    id: str
    title: str
    content: str
    index: int  # 在原文中的顺序


class ContractChunker:
    """智能条款分割"""

    # 常见条款标题模式
    CLAUSE_PATTERNS = [
        # 中文: 第X条 / 第X章 / 一、二、三 / (一)(二)
        re.compile(r"^第[一二三四五六七八九十百千\d]+[条章节款]", re.MULTILINE),
        re.compile(r"^[一二三四五六七八九十]+[、，．.]", re.MULTILINE),
        re.compile(r"^[(（][一二三四五六七八九十\d]+[)）]", re.MULTILINE),
        re.compile(r"^\d+[\.\、\)）]\s*", re.MULTILINE),
        # 常见中文标题关键词
        re.compile(r"^(甲方|乙方|卖方|买方|违约责任|争议解决|保密|知识产权|"
                   r"合同标的|付款|交付|验收|质量|期限|终止|解除|"
                   r"不可抗力|通知|送达|管辖|法律适用)", re.MULTILINE),
    ]

    @classmethod
    def split(cls, text: str, min_clause_length: int = 20) -> list[Clause]:
        """将合同文本分割为条款列表"""
        clauses = []
        lines = text.split("\n")

        current_title = "首部"
        current_lines = []
        clause_index = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # 检查是否是新条款的起始
            is_new_clause = False
            for pattern in cls.CLAUSE_PATTERNS:
                if pattern.match(stripped):
                    is_new_clause = True
                    break

            if is_new_clause and current_lines:
                # 保存上一个条款
                content = "\n".join(current_lines).strip()
                if len(content) >= min_clause_length:
                    clause = cls._build_clause(current_title, content, clause_index)
                    clauses.append(clause)
                    clause_index += 1
                # 开启新条款
                current_title = stripped[:60]
                current_lines = [stripped]
            else:
                current_lines.append(stripped)

        # 最后一个条款
        if current_lines:
            content = "\n".join(current_lines).strip()
            if len(content) >= min_clause_length:
                clause = cls._build_clause(current_title, content, clause_index)
                clauses.append(clause)

        # 如果没有识别出条款，整篇作为一个条款
        if not clauses:
            clauses.append(cls._build_clause("合同全文", text.strip(), 0))

        return clauses

    @classmethod
    def _build_clause(cls, title: str, content: str, index: int) -> Clause:
        clause_id = f"clause_{index}"
        return Clause(id=clause_id, title=title, content=content, index=index)

    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """估算文本 token 数 (近似)"""
        return len(text) // 2

    @classmethod
    def should_split_for_review(cls, total_tokens: int, max_per_chunk: int = 6000) -> bool:
        """判断是否需要分批审核"""
        return total_tokens > max_per_chunk
