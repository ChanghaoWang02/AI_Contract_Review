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
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Flowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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
        cx = self.size / 2
        cy = self.size / 2
        r_outer = self.size / 2 - 4

        # 背景圆环
        self.canv.setStrokeColor(colors.HexColor("#e8e8e8"))
        self.canv.setLineWidth(8)
        self.canv.circle(cx, cy, r_outer - 4)

        # 分数弧线（extent 过小时 ReportLab bezierArc 会出现除零错误）
        extent = (self.score / 100) * 360
        if extent < 1:
            extent = 1  # 最低 1 度，防止 ZeroDivisionError
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
                       -90, extent)

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
        if risk_level == "high":
            risk_color_hex = "#e03131"
        elif risk_level == "medium":
            risk_color_hex = "#f08c00"
        else:
            risk_color_hex = "#2f9e44"
        story.append(Paragraph(
            f'<font color="{risk_color_hex}"><b>{risk_text}</b></font>',
            self.styles["CoverSubtitle"],
        ))
        story.append(Spacer(1, 15 * mm))

        # 审核信息表 — 提取首个 provider 用于封面
        if "→" in provider_used:
            first_provider = provider_used.split("→")[0].strip().split("(")[0].strip()
        else:
            first_provider = provider_used

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
            ["高风险", str(high_count)],
            ["中风险", str(medium_count)],
            ["低风险", str(low_count)],
            ["合  计", str(len(clauses))],
        ]
        stats_table = Table(stats_data, colWidths=[70, 50])
        stats_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
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
