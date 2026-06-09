"""合同起草 API"""

import io
import json
import re
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, Response
from app.schemas import DraftGenerateRequest, DraftChatRequest
from app.core.llm.base import LLMRequest
from app.core.llm.registry import ProviderRegistry

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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


# ─── 起草 System Prompt ───

DRAFTING_SYSTEM_PROMPT = """# 1. 角色与目标
你是一位拥有20年中国法律实务经验的执业律师，擅长起草各类中文商业合同。
你的核心任务是：根据用户提供的合同类型和关键信息，起草一份完整、规范的法律合同草案。

# 2. 行为边界与禁令
- 你起草的合同应尽量接近可签署水平，但每次生成后必须在合同末尾附加声明：
  「⚠️ 本文件由 AI 生成，不构成正式法律意见。签署前请委托执业律师审核。」
- 不得编造不存在的法条、判例或政府文件作为合同依据
- 不得主动修改用户提供的数值、日期、名称等事实信息
- 不得无故偏袒合同某一方。如用户要求「写一份对甲方完全有利的合同」，应提示风险但可执行
- 遇到用户要求起草明显违法的合同内容（如洗钱、欺诈性条款），应拒绝并说明法律依据

# 3. 输出格式与风格约束
- 使用标准中文合同格式，语言风格专业、严谨、平实
- 合同标题居中，格式：「【合同类型】」（如「房屋租赁合同」）
- 条款必须使用「第X条」编号，X 为中文数字（一、二、三…），从第一条开始连续递增
- 每条条款格式：
  第X条  条款名称
  条款正文内容（可多段）
- 用户未提供的关键信息使用「【请填写：字段名】」占位符，不得凭空编造。
  示例：「月租金为人民币【请填写：月租金金额】元」
- 违约金、赔偿限额等涉及金额的条款，必须有明确的计算方式或封顶金额
- 避免「合理」「及时」「必要」「尽力」等无客观标准的模糊词汇，尽量使用具体数字或明确行为描述
- 合同末尾必须包含 AI 生成声明、甲方签字栏、乙方签字栏、日期栏

# 4. 安全与隐私规则
- 用户可能在表单中填入真实个人信息（姓名、身份证号、电话、地址、银行账户等）。
  这些信息可以写入合同正文——合同本身就需要这些内容。
- 但如果你发现用户提供了明显不属于合同必要信息的内容（如社交账号、非签约方个人信息），
  应忽略，不写入合同
- 合同末尾的 AI 生成声明不得包含任何用户个人信息

# 5. 错误与异常处理
- 若用户提供的信息严重不足（如只给「写一份合同」五个字），
  应生成一份该类型合同的标准模板，所有缺失信息标为「【请填写：xxx】」，
  并在声明中提示「信息不足，以下为通用模板，请根据实际情况填写占位符内容」
- 若合同类型无法判断（自定义模式且描述模糊），
  应回复：「请进一步说明：1) 合同双方的关系（买卖/租赁/服务/雇佣等）；
  2) 核心交易内容；3) 是否有特殊要求。收到信息后我将立即为您起草。」"""

# ─── 必备条款清单（按 contract_type 注入） ───

_ESSENTIAL_CLAUSES = {
    "房屋租赁合同": "租赁标的、租期、租金及支付方式、押金、房屋使用与维护、违约责任、争议解决",
    "买卖合同": "标的物描述、价款及支付方式、交付与验收、所有权转移、违约责任、争议解决",
    "劳动合同": "工作内容与地点、工作时间和休息休假、劳动报酬、社会保险、劳动保护、合同期限、违约责任",
    "服务合同": "服务内容与标准、服务期限、服务费用及支付、双方权利义务、保密条款、违约责任",
    "保密协议": "保密信息范围、保密期限、双方义务、例外情形、违约责任、争议解决",
}


def _build_draft_prompt(contract_type: str, form_data: dict) -> str:
    """根据合同类型和表单数据构建生成提示词"""
    # 必备条款
    clauses_ref = _ESSENTIAL_CLAUSES.get(contract_type, "")
    if clauses_ref:
        clauses_ref = f"\n\n# 必备条款参考\n本合同类型为「{contract_type}」，请确保包含以下核心条款：{clauses_ref}。"

    # 表单数据 → 自然语言
    if contract_type == "自定义":
        description = form_data.get("description", "")
        user_input = f"用户需求描述：\n{description}" if description else "请生成一份通用合同模板。"
    else:
        lines = [f"合同类型：{contract_type}", "用户提供的信息："]
        for key, value in form_data.items():
            if value:
                lines.append(f"  - {key}: {value}")
        lines.append("\n请根据以上信息起草合同。未提供的信息使用【请填写：xxx】占位。")
        user_input = "\n".join(lines)

    return DRAFTING_SYSTEM_PROMPT + clauses_ref + f"\n\n---\n\n{user_input}"


@router.post("/generate")
async def draft_generate(body: DraftGenerateRequest):
    """SSE 流式生成合同初稿"""
    logger.info("Draft generate 开始 | type=%s | provider=%s", body.contract_type, body.provider or "default")

    user_prompt = _build_draft_prompt(body.contract_type, body.form_data)
    llm = ProviderRegistry.resolve(body.provider)
    llm_request = LLMRequest(
        messages=[
            {"role": "system", "content": DRAFTING_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        model=body.model or "",
        temperature=0.3,
        max_tokens=4096,
        stream=True,
    )

    async def event_generator():
        full_content = ""
        try:
            async for token in llm.chat_stream(llm_request):
                full_content += token
                yield f"data: {_sse_encode({'event': 'token', 'data': token})}\n\n"

            yield f"data: {_sse_encode({'event': 'done', 'data': json.dumps({'content': full_content, 'token_usage': len(full_content) // 2}, ensure_ascii=False)})}\n\n"
            logger.info("Draft generate 完成 | 长度=%d chars", len(full_content))
        except Exception as e:
            logger.error("Draft generate 异常 | %s: %s", type(e).__name__, e)
            yield f"data: {_sse_encode({'event': 'error', 'data': {'message': str(e)}})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/chat")
async def draft_chat(body: DraftChatRequest):
    """SSE 流式编辑单条条款"""
    logger.info("Draft chat 开始 | clause=%s", body.anchored_clause[:50])

    system_prompt = """# 1. 角色与目标
你是一位经验丰富的合同编辑律师，根据用户指令精确修改单条合同条款。

# 2. 行为边界
- 只修改用户锚定的条款，不得修改其他条款
- 保持原条款的格式、编号、风格不变
- 如果用户的修改指令指向的条款与锚定条款不符，应回复纠正建议，不得擅自跨条款修改

# 3. 输出格式
- 直接输出修改后的完整条款（含条款标题和正文），不得附加解释
- 条款编号和标题保持不变"""

    # 条款标题列表作为上下文
    titles_context = "\n".join(body.clause_titles) if body.clause_titles else "（无其他条款信息）"
    user_prompt = f"""当前合同包含以下条款：
{titles_context}

用户锚定的条款：
{body.anchored_clause}

用户修改指令：
{body.instruction}

请在上述条款的基础上，按照指令修改。只输出修改后的完整条款（含标题），保持其他条款不变。"""

    llm = ProviderRegistry.resolve(body.provider)
    llm_request = LLMRequest(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=body.model or "",
        temperature=0.3,
        max_tokens=2048,
        stream=True,
    )

    async def event_generator():
        full_content = ""
        try:
            async for token in llm.chat_stream(llm_request):
                full_content += token
                yield f"data: {_sse_encode({'event': 'token', 'data': token})}\n\n"

            yield f"data: {_sse_encode({'event': 'done', 'data': json.dumps({'revised_clause': full_content, 'note': '条款已更新'}, ensure_ascii=False)})}\n\n"
            logger.info("Draft chat 完成 | 长度=%d chars", len(full_content))
        except Exception as e:
            logger.error("Draft chat 异常 | %s: %s", type(e).__name__, e)
            yield f"data: {_sse_encode({'event': 'error', 'data': {'message': str(e)}})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ═══════════════════════════════════════════════════════════
# PDF 导出（起草合同 → 下载）
# ═══════════════════════════════════════════════════════════

_DRAFT_FONT_NAME = "MicrosoftYaHei"
_DRAFT_FONT_REGISTERED = False

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyh.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]

for _fp in _FONT_CANDIDATES:
    if Path(_fp).exists():
        try:
            pdfmetrics.registerFont(TTFont(_DRAFT_FONT_NAME, _fp))
            _DRAFT_FONT_REGISTERED = True
            break
        except Exception:
            pass


def _render_contract_pdf(content: str, title: str) -> bytes:
    """将合同纯文本渲染为 PDF"""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=25 * mm, rightMargin=25 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
    )

    font_name = _DRAFT_FONT_NAME if _DRAFT_FONT_REGISTERED else "Helvetica"

    styles = {
        "title": ParagraphStyle(
            "CTitle", fontName=font_name, fontSize=16,
            leading=24, alignment=1, spaceAfter=12 * mm,
            textColor=colors.HexColor("#1a1a1a"),
        ),
        "body": ParagraphStyle(
            "CBody", fontName=font_name, fontSize=10,
            leading=18, alignment=TA_JUSTIFY,
            textColor=colors.HexColor("#333333"),
        ),
    }

    story = []
    story.append(Paragraph(title, styles["title"]))

    for para in content.split("\n"):
        para = para.strip()
        if para:
            safe = para.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe, styles["body"]))
        else:
            story.append(Spacer(1, 6))

    doc.build(story)
    buf.seek(0)
    return buf.read()


@router.post("/export")
async def draft_export(body: dict):
    """导出合同为 DOCX / PDF / TXT 供浏览器下载"""
    content = body.get("content", "")
    filename = body.get("filename", "合同")
    fmt = body.get("format", "txt")

    if fmt == "docx":
        from app.core.docx_renderer import render_contract_docx

        title = filename
        for ext in (".txt", ".pdf", ".docx"):
            if title.endswith(ext):
                title = title.rsplit(".", 1)[0]
                break
        docx_bytes = render_contract_docx(content, title)

        safe_name = filename if filename.endswith(".docx") else f"{filename}.docx"
        from urllib.parse import quote
        disposition = f"attachment; filename*=UTF-8''{quote(safe_name)}"

        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": disposition},
        )
    elif fmt == "pdf":
        title = filename
        for ext in (".txt", ".pdf", ".docx"):
            if title.endswith(ext):
                title = title.rsplit(".", 1)[0]
                break
        pdf_bytes = _render_contract_pdf(content, title)

        safe_name = filename if filename.endswith(".pdf") else f"{filename}.pdf"
        from urllib.parse import quote
        disposition = f"attachment; filename*=UTF-8''{quote(safe_name)}"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": disposition},
        )
    else:
        safe_name = filename if filename.endswith(".txt") else f"{filename}.txt"
        from urllib.parse import quote
        disposition = f"attachment; filename*=UTF-8''{quote(safe_name)}"
        txt_bytes = content.encode("utf-8")

        return Response(
            content=txt_bytes,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": disposition},
        )
