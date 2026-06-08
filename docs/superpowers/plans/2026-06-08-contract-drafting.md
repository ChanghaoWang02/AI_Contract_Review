# Contract Drafting (合同起草) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 5-step contract drafting wizard that uses AI to generate complete Chinese legal contracts from user-provided form data, with clause-level AI-assisted editing.

**Architecture:** Two new backend SSE endpoints (`/api/draft/generate`, `/api/draft/chat`) + extended contracts API, served by a dedicated drafting System Prompt. Frontend is a new `/draft` page with 5 step components sharing state via `draftStore`, with localStorage draft persistence and navigation guards.

**Tech Stack:** Python FastAPI (backend), Vue 3 + Naive UI + Pinia (frontend), same LLM adapter layer as existing review engine.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/app/schemas/__init__.py` | Modify | Add DraftGenerateRequest, DraftChatRequest schemas |
| `backend/app/api/draft.py` | Create | `/api/draft/generate` and `/api/draft/chat` SSE endpoints |
| `backend/app/api/contracts.py` | Modify | Add JSON body support for saving drafts as contracts |
| `backend/app/main.py` | Modify | Register draft router |
| `frontend/src/stores/draft.ts` | Create | Pinia store: step state, form data, contract text, chat messages |
| `frontend/src/views/DraftView.vue` | Create | 5-step wizard shell, step indicator, navigation guard |
| `frontend/src/components/draft/TypeSelector.vue` | Create | Step 1: 6 contract type cards |
| `frontend/src/components/draft/InfoForm.vue` | Create | Step 2: dynamic form per contract type |
| `frontend/src/components/draft/GenerateView.vue` | Create | Step 3: SSE streaming generation display |
| `frontend/src/components/draft/EditView.vue` | Create | Step 4: left clause preview + right chat panel |
| `frontend/src/components/draft/DraftChatPanel.vue` | Create | Step 4 right side: chat for clause editing |
| `frontend/src/components/draft/SaveView.vue` | Create | Step 5: filename input + save + error handling |
| `frontend/src/router/index.ts` | Modify | Add `/draft` route |
| `frontend/src/components/layout/Sidebar.vue` | Modify | Add "起草合同" nav link |

---

### Task 1: Backend Schemas

**Files:**
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: Add draft request schemas**

Add to `backend/app/schemas/__init__.py` at the end of the file:

```python
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
```

- [ ] **Step 2: Verify schemas import correctly**

Run: `cd backend && python -c "from app.schemas import DraftGenerateRequest, DraftChatRequest; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/__init__.py
git commit -m "feat: add DraftGenerateRequest and DraftChatRequest schemas"
```

---

### Task 2: Backend — Draft Generate Endpoint

**Files:**
- Create: `backend/app/api/draft.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create the draft API module**

Create `backend/app/api/draft.py`:

```python
"""合同起草 API"""

import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.schemas import DraftGenerateRequest
from app.core.llm.base import LLMRequest
from app.core.llm.registry import ProviderRegistry

router = APIRouter()
logger = logging.getLogger(__name__)

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
                yield f"data: {json.dumps({'event': 'token', 'data': token}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'event': 'done', 'data': json.dumps({'content': full_content, 'token_usage': len(full_content) // 2}, ensure_ascii=False)}, ensure_ascii=False)}\n\n"
            logger.info("Draft generate 完成 | 长度=%d chars", len(full_content))
        except Exception as e:
            logger.error("Draft generate 异常 | %s: %s", type(e).__name__, e)
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': str(e)}}, ensure_ascii=False)}\n\n"

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
                yield f"data: {json.dumps({'event': 'token', 'data': token}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'event': 'done', 'data': json.dumps({'revised_clause': full_content, 'note': '条款已更新'}, ensure_ascii=False)}, ensure_ascii=False)}\n\n"
            logger.info("Draft chat 完成 | 长度=%d chars", len(full_content))
        except Exception as e:
            logger.error("Draft chat 异常 | %s: %s", type(e).__name__, e)
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': str(e)}}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

- [ ] **Step 2: Register the draft router in main.py**

In `backend/app/main.py`, add the import and route registration:

Import (near other api imports):
```python
from app.api import contracts, reviews, chat, rules, draft
```

Router registration (near other router registrations):
```python
app.include_router(draft.router, prefix="/api/draft", tags=["合同起草"])
```

- [ ] **Step 3: Verify backend imports cleanly**

Run: `cd backend && python -c "from app.api.draft import router; print('draft module OK')"`
Expected: `draft module OK`

- [ ] **Step 4: Restart backend and test generate endpoint**

Restart uvicorn, then:
```bash
curl -s -X POST http://localhost:8000/api/draft/generate \
  -H "Content-Type: application/json" \
  -d '{"contract_type":"房屋租赁合同","form_data":{"lessor":"张三","lessee":"李四","monthly_rent":5000}}' \
  2>&1 | head -20
```
Expected: SSE stream with `event: token` lines and Chinese contract text.

- [ ] **Step 5: Test chat endpoint**

```bash
curl -s -X POST http://localhost:8000/api/draft/chat \
  -H "Content-Type: application/json" \
  -d '{"anchored_clause":"第三条 租金\n月租金为5000元。","clause_titles":["第一条 租赁标的","第二条 租期","第三条 租金"],"instruction":"把租金改成8000元"}' \
  2>&1 | head -20
```
Expected: SSE stream with modified clause containing "8000元".

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/draft.py backend/app/main.py
git commit -m "feat: add /api/draft/generate and /api/draft/chat SSE endpoints"
```

---

### Task 3: Backend — Contracts API JSON Body Support

**Files:**
- Modify: `backend/app/api/contracts.py`

- [ ] **Step 1: Add JSON body endpoint**

In `backend/app/api/contracts.py`, add a new route that accepts JSON body for saving drafts:

```python
from app.schemas import ContractOut


@router.post("/save", response_model=ContractOut)
async def save_contract_from_draft(
    filename: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db),
):
    """从起草页保存合同（接受 JSON body 中的 filename + content）"""
    import json as _json

    # FastAPI doesn't support mixing JSON and Form easily,
    # so we use a workaround: accept as form fields
    contract = Contract(
        filename=filename,
        original_filename=filename,
        content=content,
        content_type="txt",
        file_size=len(content.encode("utf-8")),
        clause_count=0,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    logger.info("合同已保存 | id=%d | filename=%s | 大小=%d chars", contract.id, filename, len(content))
    return contract
```

Actually, since the frontend will call this with JSON, let's use a proper approach. Add after the existing upload route:

```python
from pydantic import BaseModel


class SaveDraftRequest(BaseModel):
    filename: str
    content: str
    content_type: str = "txt"


@router.post("/save-draft", response_model=ContractOut)
async def save_contract_from_draft(
    body: SaveDraftRequest,
    db: Session = Depends(get_db),
):
    """从起草页保存合同（JSON body）"""
    contract = Contract(
        filename=body.filename,
        original_filename=body.filename,
        content=body.content,
        content_type=body.content_type,
        file_size=len(body.content.encode("utf-8")),
        clause_count=0,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    logger.info("合同已保存 | id=%d | filename=%s | 大小=%d chars", contract.id, body.filename, len(body.content))
    return contract
```

Requires adding `from app.models import Contract` if not already imported (check existing imports).

- [ ] **Step 2: Verify endpoint works**

Restart uvicorn, then:
```bash
curl -s -X POST http://localhost:8000/api/contracts/save-draft \
  -H "Content-Type: application/json" \
  -d '{"filename":"测试合同.txt","content":"第一条 测试\n这是测试内容。"}' | python -m json.tool
```
Expected: JSON response with `id`, `original_filename`, `content_type: "txt"`, `file_size`, `created_at`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/contracts.py
git commit -m "feat: add POST /api/contracts/save-draft for JSON body contract creation"
```

---

### Task 4: Frontend — Draft Store

**Files:**
- Create: `frontend/src/stores/draft.ts`

- [ ] **Step 1: Create draft store**

Create `frontend/src/stores/draft.ts`:

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface DraftChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export interface ContractType {
  key: string
  label: string
  icon: string
}

export const CONTRACT_TYPES: ContractType[] = [
  { key: '房屋租赁合同', label: '房屋租赁合同', icon: '🏠' },
  { key: '买卖合同', label: '买卖合同', icon: '🤝' },
  { key: '劳动合同', label: '劳动合同', icon: '💼' },
  { key: '服务合同', label: '服务合同', icon: '📋' },
  { key: '保密协议', label: '保密协议', icon: '🔒' },
  { key: '自定义', label: '自定义', icon: '✏️' },
]

// 表单字段定义（附录 A）
export const FORM_FIELDS: Record<string, { key: string; label: string; type: 'text' | 'number' | 'textarea' | 'select'; options?: string[] }[]> = {
  '房屋租赁合同': [
    { key: 'lessor', label: '甲方（出租方）', type: 'text' },
    { key: 'lessee', label: '乙方（承租方）', type: 'text' },
    { key: 'address', label: '房屋地址', type: 'text' },
    { key: 'monthly_rent', label: '月租金（元）', type: 'number' },
    { key: 'deposit', label: '押金（元）', type: 'number' },
    { key: 'lease_term_months', label: '租期（月）', type: 'number' },
    { key: 'payment_method', label: '支付方式', type: 'text' },
    { key: 'special_terms', label: '特殊约定', type: 'textarea' },
  ],
  '买卖合同': [
    { key: 'seller', label: '出卖方', type: 'text' },
    { key: 'buyer', label: '买受方', type: 'text' },
    { key: 'goods_description', label: '标的物描述', type: 'textarea' },
    { key: 'price', label: '价款（元）', type: 'number' },
    { key: 'payment_method', label: '支付方式', type: 'text' },
    { key: 'delivery_place', label: '交付地点', type: 'text' },
    { key: 'delivery_deadline', label: '交付期限', type: 'text' },
    { key: 'warranty', label: '质保说明', type: 'textarea' },
  ],
  '劳动合同': [
    { key: 'employer', label: '用人单位', type: 'text' },
    { key: 'employee', label: '劳动者', type: 'text' },
    { key: 'job_title', label: '工作岗位', type: 'text' },
    { key: 'work_location', label: '工作地点', type: 'text' },
    { key: 'monthly_salary', label: '月薪（元）', type: 'number' },
    { key: 'work_hours', label: '工时制度', type: 'select', options: ['标准工时', '综合计算工时', '不定时'] },
    { key: 'contract_term', label: '合同期限', type: 'text' },
    { key: 'probation', label: '试用期', type: 'text' },
    { key: 'benefits', label: '福利待遇', type: 'textarea' },
  ],
  '服务合同': [
    { key: 'client', label: '委托方', type: 'text' },
    { key: 'provider', label: '服务方', type: 'text' },
    { key: 'service_description', label: '服务内容', type: 'textarea' },
    { key: 'service_fee', label: '服务费用（元）', type: 'number' },
    { key: 'payment_schedule', label: '付款节点', type: 'text' },
    { key: 'service_period', label: '服务期限', type: 'text' },
    { key: 'acceptance_criteria', label: '验收标准', type: 'textarea' },
    { key: 'confidentiality', label: '保密要求', type: 'textarea' },
  ],
  '保密协议': [
    { key: 'disclosing_party', label: '信息披露方', type: 'text' },
    { key: 'receiving_party', label: '信息接收方', type: 'text' },
    { key: 'purpose', label: '信息使用目的', type: 'textarea' },
    { key: 'scope', label: '保密信息范围', type: 'textarea' },
    { key: 'duration_years', label: '保密期限（年）', type: 'number' },
    { key: 'exceptions', label: '例外情形', type: 'textarea' },
  ],
}

export const useDraftStore = defineStore('draft', () => {
  // 步骤状态（0-based: 0=选类型, 1=填信息, 2=生成, 3=编辑, 4=保存）
  const currentStep = ref(0)

  // Step 1 数据
  const contractType = ref<string | null>(null)

  // Step 2 数据
  const formData = ref<Record<string, string>>({})

  // Step 3 数据
  const generatedText = ref('')
  const isGenerating = ref(false)
  const generateError = ref<string | null>(null)

  // Step 4 数据
  const chatMessages = ref<DraftChatMessage[]>([])
  const isEditing = ref(false)

  // 辅助
  const hasDraft = computed(() => !!contractType.value)

  function setContractType(type: string) {
    contractType.value = type
    formData.value = {}  // 切换类型时重置表单
    generatedText.value = ''
    chatMessages.value = []
  }

  function setFormData(data: Record<string, string>) {
    formData.value = { ...data }
  }

  function setGeneratedText(text: string) {
    generatedText.value = text
  }

  function addChatMessage(msg: DraftChatMessage) {
    chatMessages.value.push(msg)
  }

  function clearDraft() {
    currentStep.value = 0
    contractType.value = null
    formData.value = {}
    generatedText.value = ''
    chatMessages.value = []
    isGenerating.value = false
    generateError.value = null
    isEditing.value = false
  }

  // localStorage 草稿持久化
  function saveToLocalStorage() {
    const draft = {
      step: currentStep.value,
      contractType: contractType.value,
      formData: formData.value,
      generatedText: generatedText.value,
      chatMessages: chatMessages.value,
    }
    localStorage.setItem('atcr_draft', JSON.stringify(draft))
  }

  function loadFromLocalStorage(): boolean {
    const raw = localStorage.getItem('atcr_draft')
    if (!raw) return false
    try {
      const draft = JSON.parse(raw)
      currentStep.value = draft.step ?? 0
      contractType.value = draft.contractType
      formData.value = draft.formData ?? {}
      generatedText.value = draft.generatedText ?? ''
      chatMessages.value = draft.chatMessages ?? []
      return true
    } catch {
      localStorage.removeItem('atcr_draft')
      return false
    }
  }

  function clearLocalStorage() {
    localStorage.removeItem('atcr_draft')
  }

  return {
    currentStep,
    contractType,
    formData,
    generatedText,
    isGenerating,
    generateError,
    chatMessages,
    isEditing,
    hasDraft,
    setContractType,
    setFormData,
    setGeneratedText,
    addChatMessage,
    clearDraft,
    saveToLocalStorage,
    loadFromLocalStorage,
    clearLocalStorage,
  }
})
```

- [ ] **Step 2: Verify TypeScript compilation**

Run: `cd frontend && npx vue-tsc --noEmit src/stores/draft.ts 2>&1`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/stores/draft.ts
git commit -m "feat: add draft store with 5-step state and localStorage persistence"
```

---

### Task 5: Frontend — Router + Sidebar + DraftView Shell

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/layout/Sidebar.vue`
- Create: `frontend/src/views/DraftView.vue`

- [ ] **Step 1: Add /draft route**

In `frontend/src/router/index.ts`, add to routes array:

```typescript
{
  path: '/draft',
  name: 'draft',
  component: () => import('@/views/DraftView.vue'),
},
```

- [ ] **Step 2: Add sidebar navigation**

In `frontend/src/components/layout/Sidebar.vue`, add before `sidebar-footer`:

```html
<div class="nav-section" style="margin-top: 12px">
  <router-link to="/draft" class="nav-link draft-link">
    <n-icon><create-outline /></n-icon> 起草合同
  </router-link>
</div>
```

Add the create-outline icon import:
```typescript
import { AddOutline, TrashOutline, SettingsOutline, DownloadOutline, CreateOutline } from '@vicons/ionicons5'
```

Add scoped style:
```css
.draft-link {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #4C6EF5;
  text-decoration: none;
  padding: 8px;
  border-radius: 6px;
  font-weight: 500;
}
.draft-link:hover {
  background: #e8ebff;
}
```

- [ ] **Step 3: Create DraftView shell**

Create `frontend/src/views/DraftView.vue`:

```html
<template>
  <div class="draft-page">
    <!-- 顶部栏 -->
    <div class="draft-header">
      <n-button text @click="goBack">
        <n-icon><arrow-back-outline /></n-icon>
        返回
      </n-button>
      <h2>合同起草</h2>
    </div>

    <!-- 步骤指示器 -->
    <n-steps :current="draft.currentStep" class="steps-bar">
      <n-step title="选类型" />
      <n-step title="填信息" />
      <n-step title="AI 生成" />
      <n-step title="预览编辑" />
      <n-step title="保存" />
    </n-steps>

    <!-- 步骤内容 -->
    <div class="step-content">
      <TypeSelector v-if="draft.currentStep === 0" />
      <InfoForm v-else-if="draft.currentStep === 1" />
      <GenerateView v-else-if="draft.currentStep === 2" />
      <EditView v-else-if="draft.currentStep === 3" />
      <SaveView v-else-if="draft.currentStep === 4" />
    </div>

    <!-- 草稿恢复弹窗 -->
    <n-modal v-model:show="showDraftRecovery" :closable="false" :mask-closable="false">
      <div class="recovery-modal">
        <h3>检测到未完成的草稿</h3>
        <p>是否继续上次的起草？</p>
        <div class="recovery-actions">
          <n-button @click="discardDraft">丢弃，重新开始</n-button>
          <n-button type="primary" @click="continueDraft">继续起草</n-button>
        </div>
      </div>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'
import { NButton, NIcon, NSteps, NStep, NModal, useDialog } from 'naive-ui'
import { ArrowBackOutline } from '@vicons/ionicons5'
import { useDraftStore } from '@/stores/draft'
import TypeSelector from '@/components/draft/TypeSelector.vue'
import InfoForm from '@/components/draft/InfoForm.vue'
import GenerateView from '@/components/draft/GenerateView.vue'
import EditView from '@/components/draft/EditView.vue'
import SaveView from '@/components/draft/SaveView.vue'

const router = useRouter()
const draft = useDraftStore()
const dialog = useDialog()
const showDraftRecovery = ref(false)

onMounted(() => {
  if (draft.loadFromLocalStorage()) {
    showDraftRecovery.value = true
  }
})

function continueDraft() {
  showDraftRecovery.value = false
}

function discardDraft() {
  draft.clearLocalStorage()
  draft.clearDraft()
  showDraftRecovery.value = false
}

function goBack() {
  if (draft.currentStep >= 2 && draft.hasDraft) {
    // 展示离开确认（通过 onBeforeRouteLeave 处理）
  }
  router.push('/')
}

// 导航守卫
onBeforeRouteLeave((_to, _from, next) => {
  if (draft.currentStep >= 2 && draft.hasDraft) {
    dialog.warning({
      title: '正在起草中，离开将丢失进度',
      positiveText: '保存草稿',
      negativeText: '直接清除',
      closable: true,
      onPositiveClick: () => {
        draft.saveToLocalStorage()
        draft.clearDraft()
        next()
      },
      onNegativeClick: () => {
        draft.clearLocalStorage()
        draft.clearDraft()
        next()
      },
      onClose: () => {
        next(false)  // 取消导航
      },
    })
  } else {
    next()
  }
})
</script>

<style scoped>
.draft-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
}
.draft-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
.draft-header h2 { margin: 0; }
.steps-bar { margin-bottom: 24px; }
.step-content { min-height: 400px; }
.recovery-modal {
  padding: 24px;
  background: #fff;
  border-radius: 8px;
  text-align: center;
}
.recovery-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 16px;
}
</style>
```

- [ ] **Step 4: Verify everything compiles**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1`
Expected: No errors (may have warnings about the step components that don't exist yet — create stub files first, see next task).

- [ ] **Step 5: Create stub components (so DraftView compiles)**

Create all 5 stub component files with minimal content:

`frontend/src/components/draft/TypeSelector.vue`:
```html
<template><div>TypeSelector</div></template>
```

`frontend/src/components/draft/InfoForm.vue`:
```html
<template><div>InfoForm</div></template>
```

`frontend/src/components/draft/GenerateView.vue`:
```html
<template><div>GenerateView</div></template>
```

`frontend/src/components/draft/EditView.vue`:
```html
<template><div>EditView</div></template>
```

`frontend/src/components/draft/DraftChatPanel.vue`:
```html
<template><div>DraftChatPanel</div></template>
```

`frontend/src/components/draft/SaveView.vue`:
```html
<template><div>SaveView</div></template>
```

- [ ] **Step 6: Verify full build**

Run: `cd frontend && npx vite build 2>&1 | tail -5`
Expected: `✓ built in ...`

- [ ] **Step 7: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/components/layout/Sidebar.vue frontend/src/views/DraftView.vue frontend/src/components/draft/
git commit -m "feat: add draft page shell, route, sidebar nav, and component stubs"
```

---

### Task 6: Step 1 — TypeSelector Component

**Files:**
- Rewrite: `frontend/src/components/draft/TypeSelector.vue`

- [ ] **Step 1: Implement TypeSelector**

Replace the stub content in `frontend/src/components/draft/TypeSelector.vue`:

```html
<template>
  <div class="type-selector">
    <h3>选择合同类型</h3>
    <div class="type-cards">
      <div
        v-for="t in CONTRACT_TYPES"
        :key="t.key"
        class="type-card"
        :class="{ selected: draft.contractType === t.key }"
        @click="draft.setContractType(t.key)"
      >
        <span class="type-icon">{{ t.icon }}</span>
        <span class="type-label">{{ t.label }}</span>
      </div>
    </div>
    <div class="step-actions">
      <n-button type="primary" :disabled="!draft.contractType" @click="draft.currentStep = 1">
        下一步
      </n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { NButton } from 'naive-ui'
import { useDraftStore, CONTRACT_TYPES } from '@/stores/draft'

const draft = useDraftStore()
</script>

<style scoped>
.type-selector h3 { margin: 0 0 16px; }
.type-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.type-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px 12px;
  border: 2px solid #e8e8e8;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.type-card:hover { border-color: #c4ccff; background: #f5f6ff; }
.type-card.selected { border-color: #4C6EF5; background: #e8ebff; }
.type-icon { font-size: 32px; }
.type-label { font-size: 14px; font-weight: 500; }
.step-actions { margin-top: 24px; display: flex; justify-content: flex-end; }
</style>
```

- [ ] **Step 2: Verify compilation**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/draft/TypeSelector.vue
git commit -m "feat: implement Step 1 - contract type card selector"
```

---

### Task 7: Step 2 — InfoForm Component

**Files:**
- Rewrite: `frontend/src/components/draft/InfoForm.vue`

- [ ] **Step 1: Implement InfoForm**

Replace `frontend/src/components/draft/InfoForm.vue`:

```html
<template>
  <div class="info-form">
    <h3>{{ draft.contractType }} — 填写关键信息</h3>
    <p class="form-hint">所有字段可选填，未填的将由 AI 自动补充。</p>

    <!-- 自定义模式：自由文本 -->
    <div v-if="draft.contractType === '自定义'">
      <n-input
        v-model:value="customDescription"
        type="textarea"
        :autosize="{ minRows: 5, maxRows: 10 }"
        placeholder="请描述您需要的合同：合同双方关系、核心交易内容、特殊要求等"
      />
    </div>

    <!-- 预设类型：动态表单 -->
    <n-form v-else label-placement="top">
      <n-grid :cols="2" :x-gap="16">
        <n-form-item-gi
          v-for="field in currentFields"
          :key="field.key"
          :label="field.label"
        >
          <n-input
            v-if="field.type === 'text'"
            v-model:value="formValues[field.key]"
            :placeholder="'请输入' + field.label"
          />
          <n-input-number
            v-else-if="field.type === 'number'"
            v-model:value="formValues[field.key]"
            :placeholder="'请输入' + field.label"
          />
          <n-select
            v-else-if="field.type === 'select'"
            v-model:value="formValues[field.key]"
            :options="(field.options || []).map(o => ({ label: o, value: o }))"
          />
          <n-input
            v-else-if="field.type === 'textarea'"
            v-model:value="formValues[field.key]"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
            :placeholder="'请输入' + field.label"
          />
        </n-form-item-gi>
      </n-grid>
    </n-form>

    <div class="step-actions">
      <n-button @click="draft.currentStep = 0">上一步</n-button>
      <n-button type="primary" @click="onNext">下一步</n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { NButton, NForm, NFormItemGi, NGrid, NInput, NInputNumber, NSelect } from 'naive-ui'
import { useDraftStore, FORM_FIELDS } from '@/stores/draft'

const draft = useDraftStore()

const currentFields = computed(() => FORM_FIELDS[draft.contractType || ''] || [])
const customDescription = ref('')

// Initialize form values from draft store or defaults
const formValues = ref<Record<string, any>>({})

watch(() => draft.contractType, () => {
  // Reset form when type changes
  const defaults: Record<string, any> = {}
  for (const f of currentFields.value) {
    defaults[f.key] = draft.formData[f.key] ?? (f.type === 'number' ? null : '')
  }
  formValues.value = defaults
  customDescription.value = draft.contractType === '自定义' ? (draft.formData['description'] || '') : ''
}, { immediate: true })

function onNext() {
  if (draft.contractType === '自定义') {
    draft.setFormData({ description: customDescription.value })
  } else {
    const data: Record<string, string> = {}
    for (const [k, v] of Object.entries(formValues.value)) {
      if (v !== null && v !== '' && v !== undefined) {
        data[k] = String(v)
      }
    }
    draft.setFormData(data)
  }
  draft.currentStep = 2
}
</script>

<style scoped>
.info-form h3 { margin: 0 0 4px; }
.form-hint { color: #999; font-size: 13px; margin: 0 0 16px; }
.step-actions { margin-top: 24px; display: flex; justify-content: space-between; }
</style>
```

- [ ] **Step 2: Verify compilation**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/draft/InfoForm.vue
git commit -m "feat: implement Step 2 - dynamic info form per contract type"
```

---

### Task 8: Step 3 — GenerateView Component

**Files:**
- Rewrite: `frontend/src/components/draft/GenerateView.vue`

- [ ] **Step 1: Implement GenerateView**

Replace `frontend/src/components/draft/GenerateView.vue`:

```html
<template>
  <div class="generate-view">
    <h3>AI 正在生成合同...</h3>

    <!-- 错误 -->
    <n-alert v-if="draft.generateError" type="error" class="error-box">
      {{ draft.generateError }}
    </n-alert>

    <!-- 生成中 / 完成 -->
    <div class="text-preview">
      <n-input
        v-model:value="displayText"
        type="textarea"
        :autosize="{ minRows: 12, maxRows: 20 }"
        readonly
        :placeholder="draft.isGenerating ? '生成中...' : '生成完成后合同将显示在这里'"
        class="contract-textarea"
      />
    </div>

    <div class="step-actions">
      <n-button :disabled="draft.isGenerating" @click="goBack">上一步</n-button>
      <div class="right-actions">
        <n-button
          v-if="!draft.isGenerating && draft.generatedText"
          :loading="draft.isGenerating"
          @click="regenerate"
        >
          重新生成
        </n-button>
        <n-button
          v-if="draft.generateError"
          type="warning"
          @click="regenerate"
        >
          重试
        </n-button>
        <n-button
          type="primary"
          :disabled="draft.isGenerating || !draft.generatedText"
          @click="draft.currentStep = 3"
        >
          下一步
        </n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { NButton, NInput, NAlert } from 'naive-ui'
import { useDraftStore } from '@/stores/draft'

const draft = useDraftStore()
const displayText = ref('')

onMounted(() => {
  displayText.value = draft.generatedText
  if (!draft.generatedText) {
    startGeneration()
  }
})

function goBack() {
  draft.currentStep = 1
}

async function startGeneration() {
  draft.isGenerating = true
  draft.generateError = null
  displayText.value = ''

  const controller = new AbortController()

  try {
    const res = await fetch('/api/draft/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contract_type: draft.contractType,
        form_data: draft.formData,
      }),
      signal: controller.signal,
    })

    if (!res.ok) throw new Error(`请求失败 (HTTP ${res.status})`)

    const reader = res.body?.getReader()
    if (!reader) throw new Error('无法读取响应流')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.event === 'token') {
              displayText.value += data.data
            } else if (data.event === 'done') {
              const doneData = JSON.parse(data.data)
              draft.setGeneratedText(doneData.content || displayText.value)
            } else if (data.event === 'error') {
              draft.generateError = data.data?.message || '生成失败'
            }
          } catch { /* ignore */ }
        }
      }
    }
  } catch (e: any) {
    if (e.name !== 'AbortError') {
      draft.generateError = e.message || '生成失败，请重试'
    }
  } finally {
    draft.isGenerating = false
  }
}

function regenerate() {
  draft.setGeneratedText('')
  displayText.value = ''
  startGeneration()
}
</script>

<style scoped>
.generate-view h3 { margin: 0 0 12px; }
.error-box { margin-bottom: 12px; }
.text-preview { margin-bottom: 16px; }
.contract-textarea :deep(textarea) {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
}
.step-actions { display: flex; justify-content: space-between; align-items: center; }
.right-actions { display: flex; gap: 8px; }
</style>
```

- [ ] **Step 2: Verify compilation**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/draft/GenerateView.vue
git commit -m "feat: implement Step 3 - SSE streaming contract generation"
```

---

### Task 9: Step 4 — EditView + DraftChatPanel Components

**Files:**
- Rewrite: `frontend/src/components/draft/EditView.vue`
- Rewrite: `frontend/src/components/draft/DraftChatPanel.vue`

- [ ] **Step 1: Implement DraftChatPanel**

Replace `frontend/src/components/draft/DraftChatPanel.vue`:

```html
<template>
  <div class="draft-chat-panel">
    <div class="chat-messages" ref="chatEl">
      <div
        v-for="(msg, i) in draft.chatMessages"
        :key="i"
        class="chat-msg"
        :class="msg.role"
      >
        <div class="msg-content">{{ msg.content }}</div>
      </div>
      <div v-if="draft.isEditing && streamingText" class="chat-msg assistant streaming">
        <div class="msg-content">{{ streamingText }}</div>
      </div>
    </div>
    <div class="chat-input-row">
      <n-input
        v-model:value="inputText"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 3 }"
        placeholder="输入修改指令，如：把违约金改成一个月租金"
        :disabled="!anchoredClause || draft.isEditing"
        @keydown.enter.exact.prevent="sendInstruction"
      />
      <n-button
        type="primary"
        size="small"
        :disabled="!anchoredClause || !inputText.trim() || draft.isEditing"
        :loading="draft.isEditing"
        @click="sendInstruction"
      >
        发送
      </n-button>
    </div>
    <div v-if="!anchoredClause" class="no-anchor-hint">
      👈 请先点击左侧某条条款，再输入修改指令
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { NButton, NInput } from 'naive-ui'
import { useDraftStore } from '@/stores/draft'

const props = defineProps<{
  anchoredClause: string | null
  clauseTitles: string[]
}>()

const emit = defineEmits<{
  clauseRevised: [revisedClause: string]
}>()

const draft = useDraftStore()
const inputText = ref('')
const streamingText = ref('')
const chatEl = ref<HTMLElement>()

async function sendInstruction() {
  if (!props.anchoredClause || !inputText.value.trim() || draft.isEditing) return

  const instruction = inputText.value.trim()
  inputText.value = ''

  draft.addChatMessage({ role: 'user', content: instruction })
  draft.isEditing = true
  streamingText.value = ''

  const controller = new AbortController()

  try {
    const res = await fetch('/api/draft/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        anchored_clause: props.anchoredClause,
        clause_titles: props.clauseTitles,
        instruction,
      }),
      signal: controller.signal,
    })

    if (!res.ok) throw new Error(`请求失败 (HTTP ${res.status})`)

    const reader = res.body?.getReader()
    if (!reader) throw new Error('无法读取响应流')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.event === 'token') {
              streamingText.value += data.data
            } else if (data.event === 'done') {
              const doneData = JSON.parse(data.data)
              const revised = doneData.revised_clause || streamingText.value
              draft.addChatMessage({ role: 'assistant', content: revised })
              emit('clauseRevised', revised)
              streamingText.value = ''
            } else if (data.event === 'error') {
              draft.addChatMessage({
                role: 'system',
                content: `❌ ${data.data?.message || '编辑失败'}`,
              })
              streamingText.value = ''
            }
          } catch { /* ignore */ }
        }
      }
    }
  } catch (e: any) {
    if (e.name !== 'AbortError') {
      draft.addChatMessage({ role: 'system', content: `❌ ${e.message}` })
    }
    streamingText.value = ''
  } finally {
    draft.isEditing = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatEl.value) chatEl.value.scrollTop = chatEl.value.scrollHeight
  })
}

watch(() => [draft.chatMessages.length, streamingText.value], scrollToBottom)
</script>

<style scoped>
.draft-chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}
.chat-msg {
  margin-bottom: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  max-width: 90%;
}
.chat-msg.user {
  background: #e8ebff;
  margin-left: auto;
  text-align: right;
}
.chat-msg.assistant {
  background: #f5f5f5;
}
.chat-msg.system {
  background: #fff3f3;
  color: #d32f2f;
}
.msg-content { font-size: 13px; line-height: 1.5; white-space: pre-wrap; }
.chat-input-row {
  display: flex;
  gap: 8px;
  padding: 8px;
  border-top: 1px solid #eee;
  align-items: flex-end;
}
.no-anchor-hint {
  padding: 8px 12px;
  font-size: 12px;
  color: #999;
  text-align: center;
  background: #fafafa;
  border-top: 1px solid #eee;
}
</style>
```

- [ ] **Step 2: Implement EditView**

Replace `frontend/src/components/draft/EditView.vue`:

```html
<template>
  <div class="edit-view">
    <div class="edit-layout">
      <!-- 左侧：条款预览 -->
      <div class="clause-preview">
        <h4>合同预览</h4>
        <div class="clause-list">
          <div
            v-for="(clause, i) in clauses"
            :key="i"
            class="clause-item"
            :class="{ anchored: anchoredIndex === i }"
            @click="selectClause(i)"
          >
            <div class="clause-title">{{ clause.title }}</div>
            <div class="clause-body">{{ clause.body }}</div>
          </div>
          <n-empty v-if="clauses.length === 0" description="无法解析合同条款" />
        </div>
      </div>

      <!-- 右侧：聊天面板 -->
      <div class="chat-area">
        <DraftChatPanel
          :anchored-clause="anchoredClause"
          :clause-titles="clauseTitles"
          @clause-revised="onClauseRevised"
        />
      </div>
    </div>

    <div class="step-actions">
      <n-button @click="draft.currentStep = 2">上一步</n-button>
      <n-button type="primary" @click="draft.currentStep = 4">保存合同</n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { NButton, NEmpty } from 'naive-ui'
import { useDraftStore } from '@/stores/draft'
import DraftChatPanel from './DraftChatPanel.vue'

const draft = useDraftStore()

interface ClauseItem {
  title: string
  body: string
}

const clauses = ref<ClauseItem[]>([])
const anchoredIndex = ref<number | null>(null)

const anchoredClause = computed(() => {
  if (anchoredIndex.value === null || !clauses.value[anchoredIndex.value]) return null
  const c = clauses.value[anchoredIndex.value]
  return c.title + '\n' + c.body
})

const clauseTitles = computed(() => clauses.value.map(c => c.title))

function parseClauses(text: string): ClauseItem[] {
  // 按「第X条」切分
  const parts = text.split(/(?=第[一二三四五六七八九十百千]+条\s)/)
  const result: ClauseItem[] = []
  for (const part of parts) {
    const trimmed = part.trim()
    if (!trimmed) continue
    const newlineIdx = trimmed.indexOf('\n')
    if (newlineIdx > 0) {
      result.push({
        title: trimmed.slice(0, newlineIdx).trim(),
        body: trimmed.slice(newlineIdx + 1).trim(),
      })
    } else {
      // 降级：整个作为一条
      result.push({ title: trimmed.slice(0, 30), body: trimmed })
    }
  }
  return result.length > 0 ? result : [{ title: '全文', body: text }]
}

function selectClause(index: number) {
  anchoredIndex.value = anchoredIndex.value === index ? null : index
}

function onClauseRevised(revisedClause: string) {
  if (anchoredIndex.value !== null && clauses.value[anchoredIndex.value]) {
    // 替换该条款
    clauses.value[anchoredIndex.value] = {
      title: clauses.value[anchoredIndex.value].title,
      body: revisedClause.replace(clauses.value[anchoredIndex.value].title + '\n', '').replace(clauses.value[anchoredIndex.value].title, ''),
    }
    // 更新完整合同文本
    draft.setGeneratedText(clauses.value.map(c => c.title + '\n' + c.body).join('\n\n'))
  }
}

onMounted(() => {
  clauses.value = parseClauses(draft.generatedText)
})
</script>

<style scoped>
.edit-view { display: flex; flex-direction: column; }
.edit-layout {
  display: flex;
  gap: 16px;
  height: 500px;
}
.clause-preview {
  flex: 1;
  overflow-y: auto;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 12px;
}
.clause-preview h4 { margin: 0 0 8px; }
.clause-item {
  padding: 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 6px;
  border: 1px solid transparent;
  transition: all 0.15s;
}
.clause-item:hover { background: #f5f6ff; }
.clause-item.anchored { border-color: #4C6EF5; background: #e8ebff; }
.clause-title { font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.clause-body { font-size: 13px; color: #555; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.chat-area { width: 380px; min-width: 380px; }
.step-actions { display: flex; justify-content: space-between; margin-top: 16px; }
</style>
```

- [ ] **Step 3: Verify compilation**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1`
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/draft/EditView.vue frontend/src/components/draft/DraftChatPanel.vue
git commit -m "feat: implement Step 4 - clause preview + draft chat panel"
```

---

### Task 10: Step 5 — SaveView Component

**Files:**
- Rewrite: `frontend/src/components/draft/SaveView.vue`

- [ ] **Step 1: Implement SaveView**

Replace `frontend/src/components/draft/SaveView.vue`:

```html
<template>
  <div class="save-view">
    <h3>保存合同</h3>

    <n-form label-placement="top">
      <n-form-item label="文件名">
        <n-input v-model:value="filename" placeholder="输入文件名" />
      </n-form-item>
    </n-form>

    <n-alert v-if="saveError" type="error" class="save-error" closable @update:show="saveError = ''">
      {{ saveError }}
    </n-alert>

    <div class="save-hint">
      保存后将自动跳转到主页并发起 AI 审核。
    </div>

    <div class="step-actions">
      <n-button :disabled="saving" @click="draft.currentStep = 3">上一步</n-button>
      <n-button type="primary" :loading="saving" :disabled="!filename.trim()" @click="saveAndReview">
        保存并送审
      </n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NForm, NFormItem, NInput, NAlert, useMessage } from 'naive-ui'
import { useDraftStore } from '@/stores/draft'

const router = useRouter()
const message = useMessage()
const draft = useDraftStore()

const filename = ref('')
const saving = ref(false)
const saveError = ref('')

onMounted(() => {
  const today = new Date()
  const dateStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  filename.value = `${draft.contractType || '合同'}_${dateStr}.txt`
})

async function saveAndReview() {
  saving.value = true
  saveError.value = ''

  try {
    const res = await fetch('/api/contracts/save-draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: filename.value.trim(),
        content: draft.generatedText,
        content_type: 'txt',
      }),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: '保存失败' }))
      throw new Error(err.detail || `保存失败 (HTTP ${res.status})`)
    }

    const contract = await res.json()
    draft.clearLocalStorage()
    draft.clearDraft()

    message.success('合同已保存，正在跳转...')
    // 跳转主页并触发审核
    router.push({ path: '/', query: { review_contract: String(contract.id) } })
  } catch (e: any) {
    saveError.value = e.message || '保存失败，请重试'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.save-view h3 { margin: 0 0 16px; }
.save-error { margin-bottom: 12px; }
.save-hint { color: #999; font-size: 13px; margin-bottom: 16px; }
.step-actions { display: flex; justify-content: space-between; }
</style>
```

- [ ] **Step 2: Update HomeView to handle query param for auto-review**

In `frontend/src/views/HomeView.vue`, add to `onMounted`:

```typescript
import { useRoute } from 'vue-router'

const route = useRoute()

onMounted(async () => {
  await contractStore.fetchContracts()
  // 从起草页跳转过来，自动触发审核
  const reviewContractId = route.query.review_contract
  if (reviewContractId) {
    const id = Number(reviewContractId)
    if (!isNaN(id)) {
      router.replace({ path: '/', query: {} })  // clear query
      await onSelectContract(id)
    }
  }
})
```

Requires adding `useRoute` import (from 'vue-router') and `router` (already imported as `useRouter()`).

- [ ] **Step 3: Verify compilation and build**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1 && npx vite build 2>&1 | tail -5`
Expected: No TS errors + `✓ built in ...`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/draft/SaveView.vue frontend/src/views/HomeView.vue
git commit -m "feat: implement Step 5 - save contract and auto-review via query param"
```

---

### Task 11: Integration Testing

**Files:** No new files — manual verification.

- [ ] **Step 1: Start backend and frontend**

Terminal 1:
```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Terminal 2:
```bash
cd frontend && npx vite --host 0.0.0.0
```

- [ ] **Step 2: Test full 5-step flow**

1. Open http://localhost:5173 → click "起草合同" in sidebar
2. Step 1: Select "房屋租赁合同" → 下一步
3. Step 2: Fill in a few fields (lessor=张三, monthly_rent=5000) → 下一步
4. Step 3: Watch SSE streaming generate the contract → 验证中文条款编号格式 → 下一步
5. Step 4: Click a clause → type instruction in chat → verify clause updates → 保存合同
6. Step 5: Verify default filename → 保存并送审 → verify auto-navigation to home + review trigger

- [ ] **Step 3: Test edge cases**

- **Custom mode**: Step 1 select 自定义 → Step 2 enter description → verify generation
- **Re-generate**: In Step 3, click 重新生成 → verify new text
- **Navigation guard**: In Step 3, click sidebar contract → verify dialog appears
- **Save draft**: In dialog, click 保存草稿 → navigate away → return to /draft → verify recovery dialog
- **Discard draft**: In recovery dialog, click 丢弃 → verify clean state
- **Save error**: Stop backend → click 保存并送审 → verify error toast + stay on Step 5
- **Same contract click**: Click sidebar current contract → verify no navigation

- [ ] **Step 4: Commit final verification notes**

```bash
git add -A
git commit -m "test: integration verification of contract drafting 5-step flow"
```

---

## Verification Checklist

- [ ] Step 1: Contract type cards render, selection works, next button enables
- [ ] Step 2: Dynamic form renders correct fields per type, custom mode shows textarea
- [ ] Step 3: SSE streaming displays real-time contract text, re-generate works, error retry works
- [ ] Step 4: Clauses parsed from generated text, click anchors to chat, edit instruction updates clause
- [ ] Step 5: Default filename populated, save creates contract in DB, auto-navigate + auto-review triggers
- [ ] Navigation guard: 3-option dialog appears when leaving Step 3/4
- [ ] LocalStorage: save draft persists, recovery dialog on re-entry, discard clears
- [ ] Error handling: generate failure shows retry, save failure shows toast + stays on step
