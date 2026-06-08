# ATCR — 合同起草功能设计

> 状态：设计完成，待用户审核
> 日期：2026-06-08

## 1. 概述

在现有合同审核能力之上，新增「合同起草」功能。用户通过 5 步向导引导 AI 生成一份完整合同，可逐条编辑优化后保存到本地合同库并送审。

## 2. 用户流程

```
Step 1         Step 2         Step 3         Step 4              Step 5
选合同类型  →  填关键信息  →  AI 生成初稿  →  预览 + 逐条编辑  →  保存 + 送审
(6种卡片)     (动态表单)     (SSE 流式)     (条款锚定 + 聊天)   (入库 + 跳转)
```

### Step 1 — 选择合同类型

6 张图标卡片：
- 房屋租赁合同、买卖合同、劳动合同、服务合同、保密协议、自定义

选中后亮起，「下一步」进入 Step 2。

### Step 2 — 填写关键信息

- **5 种预设类型**：每种有一组硬编码表单字段（见附录 A）
- **自定义类型**：一个 5 行的 textarea，placeholder「请描述您需要的合同：合同双方关系、核心交易内容、特殊要求等」
- 所有字段可选填——未填的由 AI 在生成时用 `【请填写：xxx】` 占位
- 底部：「上一步」「下一步」

### Step 3 — AI 生成初稿

- 调用 `POST /api/draft/generate`（SSE 流式）
- 前端用**大文本框**（等宽字体、raw text）展示实时生成的合同文本，不做 markdown 渲染
- 生成完成后展示完整合同 + 三个操作：
  - 「上一步」（回到 Step 2 修改表单）
  - 「重新生成」（用相同参数重新请求 LLM）
  - 「下一步」（进入编辑，合同文本传入 Step 4 用 chunker 切分展示）
- 生成失败：显示错误信息 + 「重试」按钮

### Step 4 — 预览 + 逐条编辑

**布局**：左（条款预览） + 右（AI 编辑助手聊天面板）

**左侧 — 条款预览**：
- 用 `ContractChunker` 将合同文本按条款编号切分
- 每条显示标题 + 正文，只读
- 点击某条款 → 锚定到右侧聊天（高亮该条款）
- **降级处理**：若 AI 未按规范输出编号格式导致 chunker 只返回一整条"全文"，则整个合同作为一个条款显示，仍可锚定进行全局编辑

**右侧 — AI 编辑助手**：
- 使用独立组件 `DraftChatPanel`（不复用 ChatPanel，避免与 chatStore/reviewId 耦合），数据走 `draftStore`
- **仅单条编辑模式**：用户锚定条款后发指令，AI 直接流式输出修改后的条款全文
- 后端发送：`{ anchored_clause: 条款全文, clause_titles: 全部条款标题列表, instruction: 用户指令 }`
- AI 流式输出修订后的条款文本（逐 token），done 事件附带 `{ note: "说明做了什么修改" }`
- 前端收到 done 后，用 `revised_clause`（流式累积的完整文本）替换左侧对应条款，实时刷新预览
- 如果指令目标与锚定条款不符，AI 应回复纠正建议（如"违约金在第三条，要切换到第三条吗？"）
- **聊天记录**：存 `draftStore.chatMessages`，回到 Step 3 不清除，只有离开起草页（导航守卫确认清除）才清
- **不锚定直接发消息**：提示用户「请先点击左侧某条条款，再输入修改指令」

**底部**：「上一步」「保存合同」（进入 Step 5）

### Step 5 — 保存并送审

- 输入文件名（默认使用合同类型 + 日期）
- 点击「保存并送审」→ `POST /api/contracts`（JSON body，复用现有 contracts API，新增 JSON 支持）
- **保存成功**：自动跳转主页，选中新合同，自动触发审核
- **保存失败**：弹出 error toast，留在 Step 5，**不清除 draftStore**，允许用户重试（网络恢复后再次点击保存）

## 3. 导航保护

用户在 Step 3 或 Step 4 时点击侧边栏或浏览器后退：

```
┌─────────────────────────────────────────────┐
│  正在起草中，离开将丢失进度                    │
│                                             │
│  [保存草稿]    [直接清除]    [取消]           │
└─────────────────────────────────────────────┘
```

- **保存草稿**：写入 localStorage → 导航离开。下次进入 `/draft` 自动检测并提示恢复
- **直接清除**：清空状态 → 导航离开
- **取消**：留在当前页面

**草稿机制**：
- localStorage key：`atcr_draft`
- 内容：`{ step, contractType, formData, generatedText, chatMessages }`
- 只存一份，新草稿覆盖旧草稿
- 进入 `/draft` 时检测：有草稿 → 弹「你有未完成的草稿，要继续吗？」→ 继续/丢弃

## 4. 后端 API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/draft/generate` | SSE: 接收类型+表单 → 流式输出合同 |
| POST | `/api/draft/chat` | SSE: 接收 clause + instruction → 流式输出修改后的条款 |

### `POST /api/draft/generate`

**Request Body**：
```json
{
  "contract_type": "房屋租赁合同",
  "form_data": {
    "lessor": "张三",
    "lessee": "李四",
    "address": "北京市朝阳区XX路XX号",
    "monthly_rent": 5000,
    "deposit": 5000,
    "lease_term_months": 12
  },
  "provider": "deepseek"
}
```

自定义模式时 `form_data` 为 `{ "description": "用户自由文本..." }`。

**Response**：SSE 流
```
event: token     → data: "第"
event: token     → data: "一条"
...
event: done      → data: { "content": "完整合同", "token_usage": 1200 }
event: error     → data: { "message": "生成失败原因" }
```

**实现要点**：
- 调用 LLM，使用起草 System Prompt（见附录 B）
- 根据 `contract_type` 动态选择必备条款清单注入 System Prompt
- 支持 provider 指定和 fallback

### `POST /api/draft/chat`

**Request Body**：
```json
{
  "anchored_clause": "第四条 维修责任\n房屋的自然损耗由甲方负责维修...",
  "clause_titles": ["第一条 租赁标的", "第二条 租期", "第三条 租金", "第四条 维修责任"],
  "instruction": "把维修责任改成乙方承担小修，甲方承担大修",
  "provider": "deepseek"
}
```

**Response**：SSE 流
```
event: token     → data: "第"
event: token     → data: "四条..."
...
event: done      → data: { "revised_clause": "第四条 维修责任\n...", "note": "已将维修责任按大小修分拆给甲乙双方" }
event: error     → data: { "message": "错误信息" }
```

**实现要点**：
- System Prompt：条款编辑专用，角色为合同编辑律师
- 指令与条款不符时，AI 返回纠正建议而非强行修改

### `POST /api/contracts` — 扩展

现有 `POST /api/contracts/upload` 只接受 multipart/form-data。新增 JSON body 支持（在同一路由或 `POST /api/contracts`）：

```json
{
  "filename": "房屋租赁合同_2026-06-08.txt",
  "content": "完整合同文本...",
  "content_type": "txt"
}
```

返回 `ContractOut`，与上传接口一致。

## 5. 前端新增文件

| 文件 | 职责 |
|------|------|
| `views/DraftView.vue` | 5 步向导主框架，步骤指示器，导航守卫 |
| `components/draft/TypeSelector.vue` | Step 1：6 张类型选择卡片 |
| `components/draft/InfoForm.vue` | Step 2：动态表单（5 种类型配置 + 自定义 textarea） |
| `components/draft/GenerateView.vue` | Step 3：SSE 流式生成 + 重新生成 + 错误重试 |
| `components/draft/EditView.vue` | Step 4：左条款预览 + 右 DraftChatPanel + 锚定联动 |
| `components/draft/DraftChatPanel.vue` | Step 4 右侧：独立聊天组件，数据走 draftStore |
| `components/draft/SaveView.vue` | Step 5：文件名输入 + 保存确认 + 错误重试 |
| `stores/draft.ts` | Pinia store：步骤状态、表单数据、合同文本、聊天消息 |

### 路由

```typescript
// router/index.ts 新增
{
  path: '/draft',
  name: 'draft',
  component: () => import('@/views/DraftView.vue'),
}
```

### 侧边栏导航

在 Sidebar.vue 的 `sidebar-footer` 上方新增「✏️ 起草合同」入口。

## 6. Step 4 聊天 System Prompt（条款编辑专用）

```
# 1. 角色与目标
你是一位经验丰富的合同编辑律师，根据用户指令精确修改单条合同条款。

# 2. 行为边界
- 只修改用户锚定的条款，不得修改其他条款
- 保持原条款的格式、编号、风格不变
- 如果用户的修改指令指向的条款与锚定条款不符，应回复纠正建议，不得擅自跨条款修改

# 3. 输出格式
- 直接输出修改后的完整条款（含条款标题和正文），不得附加解释
- 条款编号和标题保持不变
```

## 附录 A — 5 种合同类型表单字段

### 房屋租赁合同
| 字段 | 标签 | 类型 |
|------|------|------|
| lessor | 甲方（出租方） | text |
| lessee | 乙方（承租方） | text |
| address | 房屋地址 | text |
| monthly_rent | 月租金（元） | number |
| deposit | 押金（元） | number |
| lease_term_months | 租期（月） | number |
| payment_method | 支付方式 | text |
| special_terms | 特殊约定 | textarea |

### 买卖合同
| 字段 | 标签 | 类型 |
|------|------|------|
| seller | 出卖方 | text |
| buyer | 买受方 | text |
| goods_description | 标的物描述 | textarea |
| price | 价款（元） | number |
| payment_method | 支付方式 | text |
| delivery_place | 交付地点 | text |
| delivery_deadline | 交付期限 | text |
| warranty | 质保说明 | textarea |

### 劳动合同
| 字段 | 标签 | 类型 |
|------|------|------|
| employer | 用人单位 | text |
| employee | 劳动者 | text |
| job_title | 工作岗位 | text |
| work_location | 工作地点 | text |
| monthly_salary | 月薪（元） | number |
| work_hours | 工时制度 | select: 标准工时/综合计算工时/不定时 |
| contract_term | 合同期限 | text |
| probation | 试用期 | text |
| benefits | 福利待遇 | textarea |

### 服务合同
| 字段 | 标签 | 类型 |
|------|------|------|
| client | 委托方 | text |
| provider | 服务方 | text |
| service_description | 服务内容 | textarea |
| service_fee | 服务费用（元） | number |
| payment_schedule | 付款节点 | text |
| service_period | 服务期限 | text |
| acceptance_criteria | 验收标准 | textarea |
| confidentiality | 保密要求 | textarea |

### 保密协议
| 字段 | 标签 | 类型 |
|------|------|------|
| disclosing_party | 信息披露方 | text |
| receiving_party | 信息接收方 | text |
| purpose | 信息使用目的 | textarea |
| scope | 保密信息范围 | textarea |
| duration_years | 保密期限（年） | number |
| exceptions | 例外情形 | textarea |

## 附录 B — 起草 System Prompt

```
# 1. 角色与目标
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
  2) 核心交易内容；3) 是否有特殊要求。收到信息后我将立即为您起草。」
- 若用户要求修改某条款但修改指令不明确（如「把这条改好一点」），
  应回复：「请具体说明您期望的修改方向，例如：调整金额、修改时间节点、增加或删除某项义务等」

# 必备条款参考
（辅助信息，不作为硬性指令，根据 contract_type 注入对应条目）
- 房屋租赁：租赁标的、租期、租金及支付、押金、使用与维护、违约责任、争议解决
- 买卖合同：标的物、价款及支付、交付与验收、权利转移、违约责任、争议解决
- 劳动合同：工作内容与地点、工作时间、劳动报酬、社会保险、合同期限、违约责任
- 服务合同：服务内容与标准、期限、费用与支付、双方权利义务、保密、违约责任
- 保密协议：保密范围、期限、双方义务、例外情形、违约责任、争议解决
```

## 附录 C — 范围边界（本期不做）

- Word/DOCX 格式导出（可后续加）
- 多用户协作起草
- 合同版本历史/回滚
- 从模板库选择而非 AI 生成
- 上传现有合同作为起草参考
- 移动端适配
