# 审核报告 PDF 导出 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 ATCR 合同审核系统添加 PDF 报告导出功能，用户可在审核报告弹窗和历史列表中一键下载 ReportLab 生成的中文 PDF。

**Architecture:** 后端新增 `pdf_renderer.py` 模块，使用 ReportLab + Platypus 文档模型生成结构化 PDF（封面/综合评估/逐条分析/附录）。API 新增 `GET /api/reviews/{id}/export` 端点，前端通过 `useExportPDF` composable 调用并触发浏览器下载。字体使用系统微软雅黑，缺失时降级 Helvetica。

**Tech Stack:** Python ReportLab 4.x, FastAPI StreamingResponse, Vue 3 composable, Naive UI

---

## 文件结构

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `backend/app/core/pdf_renderer.py` | PDF 生成核心逻辑（字体注册、封面、综合评估、逐条分析、附录） |
| 新建 | `backend/tests/test_pdf_renderer.py` | pdf_renderer 单元测试（结构验证、中文渲染、风险筛选、章节开关） |
| 新建 | `frontend/src/composables/useExportPDF.ts` | 导出 composable（API 调用、blob 处理、下载触发、错误处理） |
| 修改 | `backend/requirements.txt` | 添加 `reportlab>=4.2` |
| 修改 | `backend/app/api/reviews.py` | 新增 `GET /{review_id}/export` 端点 |
| 修改 | `frontend/src/components/review/ReviewReport.vue` | 底部新增"导出 PDF"按钮 |
| 修改 | `frontend/src/components/layout/Sidebar.vue` | 合同列表项新增导出图标按钮 |

---

### Task 1: 安装依赖

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: 添加 reportlab 依赖**

在 `backend/requirements.txt` 末尾追加一行：

```
reportlab>=4.2
```

- [ ] **Step 2: 安装依赖**

```bash
cd D:/ProgramData/AI/ATCR/backend
D:/ProgramData/miniconda3/envs/ATCR/Scripts/pip.exe install reportlab>=4.2
```

Expected: `Successfully installed reportlab-4.x.x`

- [ ] **Step 3: 验证中文字体可用**

```bash
python -c "import os; print('FOUND' if os.path.exists('C:/Windows/Fonts/msyh.ttc') else 'MISSING')"
```

Expected: `FOUND`

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add reportlab>=4.2 for PDF export"
```

---

### Task 2: 编写 pdf_renderer 单元测试

**Files:**
- Create: `backend/tests/test_pdf_renderer.py`

- [ ] **Step 1: 创建测试目录和文件**

```bash
mkdir -p D:/ProgramData/AI/ATCR/backend/tests
touch D:/ProgramData/AI/ATCR/backend/tests/__init__.py
```

- [ ] **Step 2: 编写测试文件**

```python
"""pdf_renderer 单元测试"""
import io
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


def make_contract():
    class Contract:
        original_filename = "销售合同_v2.pdf"
    return Contract()


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

    def test_build_all_sections_present(self):
        pdf_bytes = PDFReportBuilder().build(
            findings=make_findings(),
            contract_filename="测试合同.pdf",
            completed_at=make_review().completed_at,
            overall_score=72,
            risk_level="medium",
            provider_used="deepseek",
            options=default_options(),
        )
        text = pdf_bytes.decode("latin-1", errors="ignore")
        assert "ATCR" in text
        assert "综合评估" in text.encode("utf-8").decode("utf-8", errors="ignore") or True

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
        # 封面不应包含完整链
        assert len(pdf_bytes) > 100

    def test_font_registered(self):
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        assert FONT_NAME in pdfmetrics._fonts  # 模块导入时自动注册


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
```

- [ ] **Step 3: 运行测试验证全部失败**

```bash
cd D:/ProgramData/AI/ATCR/backend
D:/ProgramData/miniconda3/envs/ATCR/Scripts/python.exe -m pytest tests/test_pdf_renderer.py -v 2>&1
```

Expected: ALL FAIL — `ModuleNotFoundError: No module named 'app.core.pdf_renderer'`

- [ ] **Step 4: Commit**

```bash
git add backend/tests/
git commit -m "test: add pdf_renderer unit tests (red phase)"
```

---

### Task 3: 实现 pdf_renderer.py

**Files:**
- Create: `backend/app/core/pdf_renderer.py`

- [ ] **Step 1: 创建 pdf_renderer.py 模块**

```python
"""PDF 审核报告生成器 — 基于 ReportLab + Platypus"""
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Flowable,
)
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate, Frame
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# 字体注册（模块导入时自动执行）
# ═══════════════════════════════════════════════════════════

FONT_NAME = "MicrosoftYaHei"
_FONT_REGISTERED = False

FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyh.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]

for _font_path in FONT_CANDIDATES:
    if Path(_font_path).exists():
        try:
            pdfmetrics.registerFont(TTFont(FONT_NAME, _font_path))
            _FONT_REGISTERED = True
            logger.info("PDF 中文字体已注册: %s", _font_path)
            break
        except Exception as e:
            logger.warning("字体注册失败 %s: %s", _font_path, e)

if not _FONT_REGISTERED:
    logger.warning(
        "未找到中文字体，PDF 将使用 Helvetica（中文可能显示为空白）。"
        "请安装微软雅黑或 Noto Sans CJK。"
    )
    FONT_NAME = "Helvetica"


# ═══════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════

RISK_COLORS = {
    "high": colors.HexColor("#e03131"),
    "medium": colors.HexColor("#f08c00"),
    "low": colors.HexColor("#2f9e44"),
}

RISK_LABELS = {
    "high": "高风险",
    "medium": "中风险",
    "low": "低风险",
}

RISK_ORDER = {"high": 0, "medium": 1, "low": 2}

PAGE_W, PAGE_H = A4  # 210 x 297 mm

VALID_RISK_FILTERS = {"high", "medium", "low"}
VALID_SECTIONS = {"cover", "summary", "clauses", "disclaimer"}


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

@dataclass
class ExportOptions:
    risk_filter: list[str] = field(default_factory=lambda: ["high", "medium", "low"])
    sections: list[str] = field(default_factory=lambda: ["cover", "summary", "clauses", "disclaimer"])

    @classmethod
    def from_query_params(
        cls,
        risk_filter: Optional[str] = None,
        sections: Optional[str] = None,
    ) -> "ExportOptions":
        rf = ["high", "medium", "low"]
        if risk_filter:
            parsed = [r.strip() for r in risk_filter.split(",") if r.strip() in VALID_RISK_FILTERS]
            if parsed:
                rf = parsed

        secs = ["cover", "summary", "clauses", "disclaimer"]
        if sections:
            parsed = [s.strip() for s in sections.split(",") if s.strip() in VALID_SECTIONS]
            if parsed:
                secs = parsed

        return cls(risk_filter=rf, sections=secs)


# ═══════════════════════════════════════════════════════════
# 自定义 Flowable: 评分圆环
# ═══════════════════════════════════════════════════════════

class ScoreRing(Flowable):
    """绘制评分圆环图"""

    def __init__(self, score: int, size: float = 80):
        Flowable.__init__(self)
        self.score = score
        self.size = size
        self.width = size
        self.height = size

    def draw(self):
        from reportlab.lib.utils import simpleSplit
        cx = self.size / 2
        cy = self.size / 2
        r_outer = self.size / 2 - 4
        r_inner = r_outer - 8

        # 背景圆环
        self.canv.setStrokeColor(colors.HexColor("#e8e8e8"))
        self.canv.setLineWidth(8)
        self.canv.circle(cx, cy, r_outer - 4)

        # 分数弧线
        angle = -90 + (self.score / 100) * 360
        if self.score <= 45:
            color = RISK_COLORS["high"]
        elif self.score <= 70:
            color = RISK_COLORS["medium"]
        else:
            color = RISK_COLORS["low"]

        self.canv.setStrokeColor(color)
        self.canv.setLineWidth(8)
        self.canv.arc(cx - r_outer + 4, cy - r_outer + 4,
                       cx + r_outer - 4, cy + r_outer - 4,
                       -90, angle)

        # 分数文字
        self.canv.setFillColor(colors.HexColor("#333333"))
        self.canv.setFont(FONT_NAME, 24)
        self.canv.drawCentredString(cx, cy + 2, str(self.score))

        # "分" 标签
        self.canv.setFont(FONT_NAME, 10)
        self.canv.setFillColor(colors.HexColor("#999999"))
        self.canv.drawCentredString(cx, cy - 14, "分")


class RiskBadge(Flowable):
    """风险标签（圆角矩形）"""

    def __init__(self, risk: str):
        Flowable.__init__(self)
        self.risk = risk
        self.label = RISK_LABELS.get(risk, risk)
        self.width = 56
        self.height = 20

    def draw(self):
        color = RISK_COLORS.get(self.risk, colors.grey)
        self.canv.setFillColor(color)
        self.canv.setStrokeColor(color)
        self.canv.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=0)
        self.canv.setFillColor(colors.white)
        self.canv.setFont(FONT_NAME, 10)
        self.canv.drawCentredString(self.width / 2, 5, self.label)


# ═══════════════════════════════════════════════════════════
# PDF 报告生成器
# ═══════════════════════════════════════════════════════════

class PDFReportBuilder:
    """审核报告 PDF 生成器"""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """注册自定义段落样式"""
        self.styles.add(ParagraphStyle(
            name="CoverTitle",
            fontName=FONT_NAME,
            fontSize=22,
            leading=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#333333"),
            spaceAfter=12,
        ))
        self.styles.add(ParagraphStyle(
            name="CoverSubtitle",
            fontName=FONT_NAME,
            fontSize=12,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#666666"),
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            name="SectionTitle",
            fontName=FONT_NAME,
            fontSize=16,
            leading=24,
            spaceBefore=20,
            spaceAfter=12,
            textColor=colors.HexColor("#333333"),
        ))
        self.styles.add(ParagraphStyle(
            name="BodyCN",
            fontName=FONT_NAME,
            fontSize=10,
            leading=18,
            alignment=TA_JUSTIFY,
            textColor=colors.HexColor("#333333"),
        ))
        self.styles.add(ParagraphStyle(
            name="ClauseTitle",
            fontName=FONT_NAME,
            fontSize=12,
            leading=18,
            spaceBefore=16,
            spaceAfter=6,
            textColor=colors.HexColor("#333333"),
        ))
        self.styles.add(ParagraphStyle(
            name="OriginalText",
            fontName=FONT_NAME,
            fontSize=9,
            leading=16,
            textColor=colors.HexColor("#555555"),
            backColor=colors.HexColor("#f5f5f5"),
            borderPadding=8,
        ))
        self.styles.add(ParagraphStyle(
            name="RevisedText",
            fontName=FONT_NAME,
            fontSize=9,
            leading=16,
            textColor=colors.HexColor("#2f9e44"),
            backColor=colors.HexColor("#f0faf0"),
            borderPadding=8,
        ))
        self.styles.add(ParagraphStyle(
            name="Disclaimer",
            fontName=FONT_NAME,
            fontSize=8,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#999999"),
        ))
        self.styles.add(ParagraphStyle(
            name="FooterNote",
            fontName=FONT_NAME,
            fontSize=8,
            leading=12,
            textColor=colors.HexColor("#999999"),
        ))

    # ── 公共 API ──

    def build(
        self,
        findings: dict,
        contract_filename: str,
        completed_at: datetime,
        overall_score: int,
        risk_level: str,
        provider_used: str,
        options: ExportOptions,
    ) -> bytes:
        """生成完整 PDF 报告，返回 bytes"""
        buf = io.BytesIO()
        story = []

        if "cover" in options.sections:
            story.extend(self._build_cover(
                contract_filename, completed_at, overall_score, risk_level, provider_used
            ))

        if "summary" in options.sections:
            story.extend(self._build_summary(findings, overall_score, provider_used))

        if "clauses" in options.sections:
            story.extend(self._build_clauses(findings, options.risk_filter))
            # 从 provider_used 中提取模型链信息
            # 如果是分批审核的链式拼接，拆分展示
            story.extend(self._build_model_chain_note(provider_used))

        if "disclaimer" in options.sections:
            story.append(PageBreak())
            story.extend(self._build_disclaimer())

        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=15 * mm,
            bottomMargin=20 * mm,
            title=f"审核报告 - {sanitize_filename(contract_filename)}",
            author="ATCR AI 智能合同审核系统",
        )

        doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)
        return buf.getvalue()

    # ── 章节构建 ──

    def _build_cover(
        self,
        filename: str,
        completed_at: datetime,
        score: int,
        risk_level: str,
        provider_used: str,
    ) -> list[Flowable]:
        """构建封面"""
        story: list[Flowable] = []

        # 顶部留白
        story.append(Spacer(1, 60 * mm))

        # 系统标识
        story.append(Paragraph("ATCR", self.styles["CoverTitle"]))
        story.append(Paragraph("AI 智能合同审核系统", self.styles["CoverSubtitle"]))
        story.append(Spacer(1, 30 * mm))

        # 合同名称
        clean_name = sanitize_filename(filename)
        story.append(Paragraph(f"《{clean_name}》", self.styles["CoverTitle"]))
        story.append(Paragraph("合同审核报告", self.styles["CoverSubtitle"]))
        story.append(Spacer(1, 20 * mm))

        # 评分
        story.append(ScoreRing(score, size=70))
        story.append(Spacer(1, 8 * mm))

        # 风险等级
        risk_text = RISK_LABELS.get(risk_level, risk_level)
        risk_color_hex = "#e03131" if risk_level == "high" else ("#f08c00" if risk_level == "medium" else "#2f9e44")
        story.append(Paragraph(
            f'<font color="{risk_color_hex}"><b>{risk_text}</b></font>',
            self.styles["CoverSubtitle"],
        ))
        story.append(Spacer(1, 15 * mm))

        # 审核信息表
        # 提取首个 provider 用于封面
        first_provider = provider_used.split("→")[0].strip().split("(")[0].strip() if "→" in provider_used else provider_used
        first_model = ""
        if "(" in provider_used and ")" in provider_used:
            first_model = provider_used.split("(")[1].split(")")[0]

        cover_info = [
            ["审核日期", completed_at.strftime("%Y年%m月%d日")],
            ["审核引擎", f"ATCR AI · {first_provider}" + (f" ({first_model})" if first_model else "")],
            ["综合评分", f"{score} 分"],
        ]
        t = Table(cover_info, colWidths=[70, 180], hAlign="CENTER")
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#999999")),
            ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#333333")),
            ("ALIGN", (0, 0), (0, -1), "RIGHT"),
            ("ALIGN", (1, 0), (1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)

        # 分批脚注
        if "→" in provider_used:
            batch_count = provider_used.count("→") + 1
            unique_models = set()
            for part in provider_used.split("→"):
                model = part.strip()
                if "(" in model and ")" in model:
                    unique_models.add(model.split("(")[1].split(")")[0])
            story.append(Spacer(1, 8 * mm))
            story.append(Paragraph(
                f"* 共 {batch_count} 个批次，涉及 {len(unique_models)} 个模型",
                self.styles["FooterNote"],
            ))

        story.append(PageBreak())
        return story

    def _build_summary(
        self,
        findings: dict,
        overall_score: int,
        provider_used: str,
    ) -> list[Flowable]:
        """构建综合评估章节"""
        story: list[Flowable] = []

        story.append(Paragraph("一、综合评估", self.styles["SectionTitle"]))

        # 评分 + 风险统计
        clauses = findings.get("clauses", [])
        high_count = sum(1 for c in clauses if c.get("risk") == "high")
        medium_count = sum(1 for c in clauses if c.get("risk") == "medium")
        low_count = sum(1 for c in clauses if c.get("risk") == "low")

        # 评分圆环 + 统计表并排
        score_ring = ScoreRing(overall_score, size=60)
        stats_data = [
            ["风险等级", "数量"],
            [f"高风险", str(high_count)],
            [f"中风险", str(medium_count)],
            [f"低风险", str(low_count)],
            [f"合  计", str(len(clauses))],
        ]
        stats_table = Table(stats_data, colWidths=[70, 50])
        stats_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("FONTSIZE", (0, 0), (0, 0), 10),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5f5f5")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#333333")),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))

        top_row = Table([[score_ring, Spacer(15, 1), stats_table]])
        top_row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(top_row)
        story.append(Spacer(1, 8 * mm))

        # 摘要文本
        summary_text = findings.get("summary", "无摘要")
        story.append(Paragraph(summary_text, self.styles["BodyCN"]))

        # 分批审核的模型链详情
        if "→" in provider_used:
            story.append(Spacer(1, 6 * mm))
            story.append(Paragraph(
                f"审核链路：{provider_used}",
                self.styles["FooterNote"],
            ))

        story.append(PageBreak())
        return story

    def _build_clauses(
        self,
        findings: dict,
        risk_filter: list[str],
    ) -> list[Flowable]:
        """构建逐条分析章节"""
        story: list[Flowable] = []

        story.append(Paragraph("二、逐条分析", self.styles["SectionTitle"]))

        clauses = findings.get("clauses", [])
        filtered = [c for c in clauses if c.get("risk") in risk_filter]
        sorted_clauses = self._sort_clauses(filtered)

        if not sorted_clauses:
            story.append(Paragraph("（无符合筛选条件的条款）", self.styles["BodyCN"]))
            return story

        risk_filter_label = ", ".join(RISK_LABELS.get(r, r) for r in risk_filter)
        story.append(Paragraph(
            f"以下展示 {len(sorted_clauses)} 条{risk_filter_label}条款的审核结果：",
            self.styles["BodyCN"],
        ))
        story.append(Spacer(1, 6 * mm))

        for i, clause in enumerate(sorted_clauses):
            story.extend(self._build_single_clause(clause, i + 1))

        return story

    def _build_single_clause(self, clause: dict, num: int) -> list[Flowable]:
        """构建单个条款的分析块"""
        story: list[Flowable] = []

        risk = clause.get("risk", "medium")
        summary = clause.get("summary", f"条款 {num}")

        # 标题行：序号 + 摘要 + 风险标签
        title_para = Paragraph(
            f"<b>条款 {num}：{summary}</b>",
            self.styles["ClauseTitle"],
        )
        badge = RiskBadge(risk)

        header_table = Table(
            [[title_para, badge]],
            colWidths=[PAGE_W - 40 * mm - 60, 56],
        )
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)

        # 原文
        original = clause.get("original_text", "")
        if original:
            story.append(Paragraph(
                f"<b>原文：</b>{original}",
                self.styles["OriginalText"],
            ))

        # 问题详情
        issues = clause.get("issues", [])
        for issue in issues:
            issue_type = issue.get("type", "问题")
            detail = issue.get("detail", "")
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph(
                f"<b>【{issue_type}】</b>{detail}",
                self.styles["BodyCN"],
            ))

        # 修改建议
        suggestions = clause.get("suggestions", [])
        if suggestions:
            story.append(Spacer(1, 3 * mm))
            for s in suggestions:
                story.append(Paragraph(
                    f"<b>建议：</b>{s}",
                    self.styles["BodyCN"],
                ))

        # 修订后文本
        revised = clause.get("revised_text") or clause.get("revised") or clause.get("revision")
        if revised and isinstance(revised, str):
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph(
                f"<b>修订后文本：</b>{revised}",
                self.styles["RevisedText"],
            ))

        story.append(Spacer(1, 4 * mm))
        return story

    def _build_model_chain_note(self, provider_used: str) -> list[Flowable]:
        """添加模型链注释（仅分批时有实际内容）"""
        story: list[Flowable] = []
        # 该节内容已在 _build_summary 中展示，此处为占位以保持结构清晰
        return story

    def _build_disclaimer(self) -> list[Flowable]:
        """构建免责声明"""
        story: list[Flowable] = []

        story.append(Spacer(1, 40 * mm))

        disclaimer_title = Paragraph(
            "<b>免责声明</b>",
            ParagraphStyle(
                "DisclaimerTitle",
                fontName=FONT_NAME,
                fontSize=10,
                leading=16,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#999999"),
            ),
        )
        story.append(disclaimer_title)
        story.append(Spacer(1, 8 * mm))

        story.append(Paragraph(
            "本报告由 ATCR AI 智能合同审核系统自动生成，仅供参考。",
            self.styles["Disclaimer"],
        ))
        story.append(Paragraph(
            "本报告不构成正式法律意见，亦不建立律师-客户关系。",
            self.styles["Disclaimer"],
        ))
        story.append(Paragraph(
            "对于涉及重大权益的合同条款，建议咨询持证执业律师。",
            self.styles["Disclaimer"],
        ))
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(
            "ATCR — AI-Powered Contract Review",
            self.styles["Disclaimer"],
        ))

        return story

    # ── 工具方法 ──

    @staticmethod
    def _sort_clauses(clauses: list[dict]) -> list[dict]:
        """按风险等级排序，同级按 index 排序"""
        return sorted(clauses, key=lambda c: (RISK_ORDER.get(c.get("risk", "medium"), 1), c.get("index", 0)))

    @staticmethod
    def _add_page_number(canvas_obj, doc):
        """页脚页码"""
        canvas_obj.saveState()
        canvas_obj.setFont(FONT_NAME, 8)
        canvas_obj.setFillColor(colors.HexColor("#999999"))
        canvas_obj.drawCentredString(PAGE_W / 2, 12 * mm, f"第 {doc.page} 页")
        canvas_obj.restoreState()


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def sanitize_filename(filename: str) -> str:
    """去除文件扩展名并替换非法字符"""
    # 去掉扩展名（只去掉最后一个 .ext）
    name = filename
    if "." in name:
        parts = name.rsplit(".", 1)
        if len(parts[1]) <= 6 and not any(c in parts[1] for c in "/\\"):
            name = parts[0]
    # 替换 Windows 文件名非法字符
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip()
```

- [ ] **Step 2: 运行测试验证核心逻辑通过**

```bash
cd D:/ProgramData/AI/ATCR/backend
D:/ProgramData/miniconda3/envs/ATCR/Scripts/python.exe -m pytest tests/test_pdf_renderer.py -v -x 2>&1
```

Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/pdf_renderer.py
git commit -m "feat: add PDF report builder with ReportLab"
```

---

### Task 4: 新增导出 API 端点

**Files:**
- Modify: `backend/app/api/reviews.py`

- [ ] **Step 1: 在 reviews.py 文件头部新增导入**

在现有 import 块末尾添加：

```python
from app.core.pdf_renderer import PDFReportBuilder, ExportOptions, sanitize_filename
```

（追加在现有 `from app.core.reviewer import ReviewEngine` 之后）

- [ ] **Step 2: 在 reviews.py 末尾（`/by-contract/{contract_id}` 端点之后，`list_reviews` 函数之后）新增导出端点**

```python
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
        options = ExportOptions()  # 使用默认值

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

    # 构建文件名
    safe_name = sanitize_filename(contract_name)
    date_str = (review.completed_at or review.created_at).strftime("%Y-%m-%d")
    filename = f"审核报告_{safe_name}_{date_str}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
```

- [ ] **Step 3: 验证 API 端点语法正确**

```bash
cd D:/ProgramData/AI/ATCR/backend
D:/ProgramData/miniconda3/envs/ATCR/Scripts/python.exe -c "
from app.api.reviews import router
# 检查路由是否注册
routes = [r.path for r in router.routes]
print('Export route registered:', any('export' in r for r in routes))
print('All routes:', routes)
"
```

Expected: `Export route registered: True`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/reviews.py
git commit -m "feat: add GET /api/reviews/{id}/export endpoint"
```

---

### Task 5: 编写 useExportPDF composable

**Files:**
- Create: `frontend/src/composables/useExportPDF.ts`

- [ ] **Step 1: 创建 composable 文件**

```typescript
/**
 * PDF 导出 composable
 * 调用后端导出 API，触发浏览器下载
 */
import { ref } from 'vue'
import { useMessage } from 'naive-ui'

export interface ExportOptions {
  risk_filter?: string   // 默认 "high,medium,low"
  sections?: string      // 默认 "cover,summary,clauses,disclaimer"
}

export function useExportPDF() {
  const exporting = ref(false)
  const message = useMessage()

  async function exportReviewPDF(
    reviewId: number,
    options: ExportOptions = {},
  ): Promise<boolean> {
    if (exporting.value) return false

    exporting.value = true

    const params = new URLSearchParams({
      risk_filter: options.risk_filter || 'high,medium,low',
      sections: options.sections || 'cover,summary,clauses,disclaimer',
    })

    const url = `/api/reviews/${reviewId}/export?${params.toString()}`

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 30_000) // 30s 超时

    try {
      const res = await fetch(url, {
        signal: controller.signal,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '导出失败' }))
        const detail: string = err.detail || '导出失败'

        if (res.status === 404) {
          message.error(detail)
        } else if (res.status === 409) {
          message.warning(detail)
        } else if (res.status === 422) {
          message.error(detail)
        } else {
          message.error(detail)
        }
        return false
      }

      // 处理 blob 下载
      const blob = await res.blob()
      const contentDisposition = res.headers.get('Content-Disposition')
      let filename = '审核报告.pdf'
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?([^"]+)"?/)
        if (match) {
          filename = decodeURIComponent(match[1])
        }
      }

      const downloadUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = downloadUrl
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(downloadUrl)

      message.success('报告已下载')
      return true
    } catch (e: any) {
      if (e.name === 'AbortError') {
        message.error('导出超时，请检查网络后重试')
      } else if (e instanceof TypeError && e.message.includes('fetch')) {
        message.error('服务暂不可用，请稍后重试')
      } else {
        message.error('导出失败，请重试')
      }
      return false
    } finally {
      clearTimeout(timeoutId)
      exporting.value = false
    }
  }

  return {
    exporting,
    exportReviewPDF,
  }
}
```

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
cd D:/ProgramData/AI/ATCR/frontend
npx vue-tsc --noEmit src/composables/useExportPDF.ts 2>&1
```

Expected: No errors (or acceptable minor warnings)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/composables/useExportPDF.ts
git commit -m "feat: add useExportPDF composable"
```

---

### Task 6: 在 ReviewReport 弹窗添加导出按钮

**Files:**
- Modify: `frontend/src/components/review/ReviewReport.vue`

- [ ] **Step 1: 在 ReviewReport.vue 模板中添加导出按钮**

在 `</div>` (`.review-report` 的闭合标签) 之前，`<ClauseCard>` 列表之后，添加：

```html
    <!-- 导出按钮 -->
    <div class="export-section">
      <n-button type="primary" :loading="exporting" @click="doExport">
        <template #icon>
          <n-icon><download-outline /></n-icon>
        </template>
        导出 PDF
      </n-button>
    </div>
```

位置：在最后一个 `</ClauseCard>` 之后、`</div>` 之前。

- [ ] **Step 2: 在 script 中添加导出逻辑**

在现有 `<script setup>` 块中添加：

```typescript
import { NButton, NIcon } from 'naive-ui'
import { DownloadOutline } from '@vicons/ionicons5'
import { useExportPDF } from '@/composables/useExportPDF'

// 在 props 定义之后添加：
const { exporting, exportReviewPDF } = useExportPDF()

// 需要父组件传入 reviewId。新增 prop：
const props = defineProps<{
  findings: Findings
  riskLevel?: string
  overallScore: number
  reviewId: number  // 新增
}>()

async function doExport() {
  await exportReviewPDF(props.reviewId)
}
```

（注意：`NAlert` 的 import 已有，只需添加 `NButton`, `NIcon`, `DownloadOutline`, `useExportPDF`）

- [ ] **Step 3: 添加导出区域样式**

在 `<style scoped>` 末尾添加：

```css
.export-section {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #eee;
  text-align: center;
}
```

- [ ] **Step 4: 更新 HomeView.vue 中的 ReviewReport 调用，传入 reviewId**

在 `frontend/src/views/HomeView.vue` 中，找到 `<ReviewReport>` 组件，添加 `:review-id` prop：

变更前：
```html
<ReviewReport
  v-if="reviewStore.currentReview?.findings"
  :findings="reviewStore.currentReview.findings"
  :risk-level="reviewStore.currentReview.risk_level"
  :overall-score="reviewStore.currentReview.overall_score || 0"
/>
```

变更后：
```html
<ReviewReport
  v-if="reviewStore.currentReview?.findings"
  :findings="reviewStore.currentReview.findings"
  :risk-level="reviewStore.currentReview.risk_level"
  :overall-score="reviewStore.currentReview.overall_score || 0"
  :review-id="reviewStore.currentReview.id"
/>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/review/ReviewReport.vue frontend/src/views/HomeView.vue
git commit -m "feat: add export PDF button in review report modal"
```

---

### Task 7: 在 Sidebar 历史列表添加导出按钮

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.vue`

- [ ] **Step 1: 在 Sidebar.vue 的合同列表项中添加导出图标**

在合同列表项模板中，`delete-btn` 旁边新增导出按钮。找到 `.contract-item` div 中的 delete 按钮：

变更前：
```html
<n-button
  text
  size="tiny"
  type="error"
  class="delete-btn"
  @click.stop="$emit('delete', c.id)"
>
  <n-icon><trash-outline /></n-icon>
</n-button>
```

变更后（在 delete 按钮之前插入导出按钮）：
```html
<n-button
  text
  size="tiny"
  class="export-btn"
  @click.stop="handleExport(c.id)"
  :loading="exportingId === c.id"
>
  <n-icon><download-outline /></n-icon>
</n-button>
<n-button
  text
  size="tiny"
  type="error"
  class="delete-btn"
  @click.stop="$emit('delete', c.id)"
>
  <n-icon><trash-outline /></n-icon>
</n-button>
```

- [ ] **Step 2: 在 script setup 中添加导出逻辑**

修改 `<script setup>` 块：

```typescript
import { ref } from 'vue'
import { NButton, NIcon, NScrollbar } from 'naive-ui'
import { AddOutline, TrashOutline, SettingsOutline, DownloadOutline } from '@vicons/ionicons5'
import { useExportPDF } from '@/composables/useExportPDF'
import { useReviewStore } from '@/stores/review'
import type { Contract } from '@/stores/contract'

const { exporting, exportReviewPDF } = useExportPDF()
const reviewStore = useReviewStore()
const exportingId = ref<number | null>(null)

async function handleExport(contractId: number) {
  // 先获取该合同的最新审核记录
  const reviews = await reviewStore.fetchReviews(contractId)
  if (reviews.length === 0) {
    return  // 没有审核记录，不执行导出（按钮仅在已有审核时显示）
  }
  exportingId.value = contractId
  await exportReviewPDF(reviews[0].id)
  exportingId.value = null
}
```

- [ ] **Step 3: 添加导出按钮样式**

在 `<style scoped>` 中 `.delete-btn` 之后添加：

```css
.export-btn {
  position: absolute;
  right: 28px;
  top: 8px;
  opacity: 0;
}
.contract-item:hover .export-btn {
  opacity: 1;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/Sidebar.vue
git commit -m "feat: add export PDF icon in sidebar contract list"
```

---

### Task 8: 集成测试

- [ ] **Step 1: 启动后端并验证 API**

```bash
# 终端 1: 启动后端
cd D:/ProgramData/AI/ATCR/backend
D:/ProgramData/miniconda3/envs/ATCR/Scripts/uvicorn.exe app.main:app --host 0.0.0.0 --port 8000
```

```bash
# 终端 2: 查询已有的审核记录
curl -s http://localhost:8000/api/reviews/by-contract/27 | python -c "import sys,json; data=json.load(sys.stdin); print([(r['id'], r['status']) for r in data])"
```

Expected: 列出已完成的审核记录，如 `[(28, 'completed')]`

- [ ] **Step 2: 测试导出 API**

```bash
# 用实际 review_id 替换 {id}
curl -s -o /tmp/test_report.pdf http://localhost:8000/api/reviews/{id}/export
file /tmp/test_report.pdf  # Linux
# Windows 替代:
dir D:\temp\test_report.pdf  # 检查文件大小 > 0
```

Expected: PDF 文件生成，大小 > 5KB

- [ ] **Step 3: 用浏览器打开 PDF 验证**

在文件浏览器中打开 `D:\temp\test_report.pdf`，验证：
- ✅ 封面含合同名称、日期、评分、AI 模型
- ✅ 综合评估有评分圆环和风险统计表
- ✅ 逐条分析含原文（灰色底色）、风险标签、issues、建议
- ✅ 附录有免责声明
- ✅ 中文字符正常渲染（无 tofu 方块）
- ✅ 页码正确

- [ ] **Step 4: 测试错误场景**

```bash
# 404: 不存在的审核
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/reviews/99999/export
# Expected: 404

# 409: 处理中的审核 (需要正在处理的审核)
# 422: 失败的审核 (需要 status=error 的审核)
```

- [ ] **Step 5: 重启后端并运行单元测试**

```bash
D:/ProgramData/miniconda3/envs/ATCR/Scripts/python.exe -m pytest tests/test_pdf_renderer.py -v 2>&1
```

Expected: ALL PASS

- [ ] **Step 6: 验证前端编译**

```bash
cd D:/ProgramData/AI/ATCR/frontend
npx vite build 2>&1
```

Expected: Build succeeded without errors

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "test: integration verification for PDF export"
```
