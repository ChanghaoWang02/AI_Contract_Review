"""pdf_renderer 单元测试"""
import pytest
from datetime import datetime, timezone
from app.core.pdf_renderer import PDFReportBuilder, ExportOptions, FONT_NAME


# ── 测试数据 ──

def make_findings(clauses=None, overall_score=72, summary="测试摘要"):
    return {
        "clauses": clauses or [
            {
                "id": "clause_0",
                "index": 0,
                "original_text": "甲方应在合理期限内完成交付。",
                "summary": "交付期限条款",
                "risk": "high",
                "issues": [
                    {"type": "模糊用语", "detail": "\"合理期限\"缺乏客观标准，可能导致交付延迟争议。"}
                ],
                "suggestions": ["建议明确具体交付日期，例如\"自合同生效之日起30个工作日内完成交付\"。"],
                "revised_text": "甲方应自合同生效之日起30个工作日内完成交付。",
            },
            {
                "id": "clause_1",
                "index": 1,
                "original_text": "双方争议由甲方所在地法院管辖。",
                "summary": "争议解决条款",
                "risk": "medium",
                "issues": [
                    {"type": "法律风险", "detail": "单方管辖约定对乙方不利，增加乙方维权成本。"}
                ],
                "suggestions": ["建议修改为\"由被告所在地或合同履行地法院管辖\"。"],
                "revised_text": None,
            },
            {
                "id": "clause_2",
                "index": 2,
                "original_text": "合同自双方签字盖章之日起生效。",
                "summary": "生效条款",
                "risk": "low",
                "issues": [],
                "suggestions": [],
                "revised_text": None,
            },
        ],
        "overall_score": overall_score,
        "summary": summary,
    }


def make_review():
    class Review:
        completed_at = datetime(2026, 6, 8, 14, 30, 0, tzinfo=timezone.utc)
        overall_score = 72
        risk_level = "medium"
        provider_used = "deepseek"
    return Review()


def default_options():
    return ExportOptions(
        risk_filter=["high", "medium", "low"],
        sections=["cover", "summary", "clauses", "disclaimer"],
    )


# ── 测试 ──

class TestExportOptions:
    def test_from_query_params_defaults(self):
        opts = ExportOptions.from_query_params()
        assert opts.risk_filter == ["high", "medium", "low"]
        assert opts.sections == ["cover", "summary", "clauses", "disclaimer"]

    def test_from_query_params_custom(self):
        opts = ExportOptions.from_query_params(
            risk_filter="high",
            sections="cover,clauses",
        )
        assert opts.risk_filter == ["high"]
        assert opts.sections == ["cover", "clauses"]

    def test_from_query_params_invalid_risk_ignored(self):
        opts = ExportOptions.from_query_params(risk_filter="high,invalid,low")
        assert opts.risk_filter == ["high", "low"]


class TestPDFReportBuilder:
    def test_build_returns_bytes(self):
        builder = PDFReportBuilder()
        pdf_bytes = builder.build(
            findings=make_findings(),
            contract_filename="销售合同_v2.pdf",
            completed_at=make_review().completed_at,
            overall_score=72,
            risk_level="medium",
            provider_used="deepseek",
            options=default_options(),
        )
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 100
        assert pdf_bytes[:4] == b"%PDF"

    def test_risk_filter_high_only(self):
        opts = ExportOptions(
            risk_filter=["high"],
            sections=["cover", "summary", "clauses", "disclaimer"],
        )
        pdf_bytes = PDFReportBuilder().build(
            findings=make_findings(),
            contract_filename="test.pdf",
            completed_at=make_review().completed_at,
            overall_score=72,
            risk_level="medium",
            provider_used="deepseek",
            options=opts,
        )
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 100

    def test_sections_cover_only(self):
        opts = ExportOptions(
            risk_filter=["high", "medium", "low"],
            sections=["cover"],
        )
        pdf_bytes = PDFReportBuilder().build(
            findings=make_findings(),
            contract_filename="test.pdf",
            completed_at=make_review().completed_at,
            overall_score=72,
            risk_level="medium",
            provider_used="deepseek",
            options=opts,
        )
        assert len(pdf_bytes) > 100

    def test_empty_clauses(self):
        pdf_bytes = PDFReportBuilder().build(
            findings=make_findings(clauses=[]),
            contract_filename="empty.pdf",
            completed_at=make_review().completed_at,
            overall_score=50,
            risk_level="medium",
            provider_used="openai",
            options=default_options(),
        )
        assert isinstance(pdf_bytes, bytes)

    def test_batched_provider_chain(self):
        pdf_bytes = PDFReportBuilder().build(
            findings=make_findings(),
            contract_filename="batch.pdf",
            completed_at=make_review().completed_at,
            overall_score=65,
            risk_level="medium",
            provider_used="deepseek(v4-pro) → openai(gpt-4o) → deepseek(v4-pro)",
            options=default_options(),
        )
        assert len(pdf_bytes) > 100

    def test_font_registered(self):
        from reportlab.pdfbase import pdfmetrics
        assert FONT_NAME in pdfmetrics._fonts


class TestSortClauses:
    def test_sort_high_first(self):
        builder = PDFReportBuilder()
        clauses = [
            {"id": "c0", "index": 0, "risk": "low"},
            {"id": "c1", "index": 1, "risk": "high"},
            {"id": "c2", "index": 2, "risk": "medium"},
        ]
        sorted_clauses = builder._sort_clauses(clauses)
        risks = [c["risk"] for c in sorted_clauses]
        assert risks == ["high", "medium", "low"]

    def test_same_risk_preserves_index_order(self):
        builder = PDFReportBuilder()
        clauses = [
            {"id": "c0", "index": 2, "risk": "high"},
            {"id": "c1", "index": 0, "risk": "high"},
            {"id": "c2", "index": 1, "risk": "high"},
        ]
        sorted_clauses = builder._sort_clauses(clauses)
        indices = [c["index"] for c in sorted_clauses]
        assert indices == [0, 1, 2]


class TestSanitizeFilename:
    def test_removes_extension(self):
        from app.core.pdf_renderer import sanitize_filename
        assert sanitize_filename("销售合同_v2.pdf") == "销售合同_v2"

    def test_replaces_illegal_chars(self):
        from app.core.pdf_renderer import sanitize_filename
        result = sanitize_filename("合同:测试<1>.docx")
        for ch in r'\/:*?"<>|':
            assert ch not in result

    def test_double_extension(self):
        from app.core.pdf_renderer import sanitize_filename
        assert sanitize_filename("合同.2024.最终版.pdf") == "合同.2024.最终版"
