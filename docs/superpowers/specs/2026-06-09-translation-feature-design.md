# 合同翻译功能 — 设计规格

## 概述

在 ATCR 系统中新增独立的合同翻译模块，支持外文合同→中文（及反向）的双向翻译。翻译功能与审核、对比平级，三者共用侧边栏合同列表，通过 HomeView 顶部 Tab 切换。

## 用户场景

1. **先翻后审** — 上传英文合同 → 翻译为中文 → 对译文审核
2. **先审后翻** — 上传英文合同 → 直接审核英文原文 → 翻译审核报告为中文
3. **直审中文** — 上传中文合同 → 审核 → 翻译报告为英文给外方看
4. **纯文本翻译** — 审核报告 / 任意文本 → 选择语言方向 → 流式翻译 → 下载

## 关键决策

| 决策 | 选择 |
|------|------|
| 翻译范围 | 完整双语：合同文本双向翻译 + 审核报告双语导出 |
| 语言支持 | 不限语言，Tier 1（英↔中）/ Tier 2（日韩法德）/ Tier 3（其他）分级质量 |
| 入口 | HomeView 顶部 Tab 栏：「审核 \| 翻译 \| 对比」 |
| 翻译结果存储 | 另存为 Contract（source='translated'，parent_contract_id 指向原文） |
| 工作台布局 | 左右对照（左原文 · 右译文） |
| 结果编辑 | 可逐条 inline 编辑 + 单条重新翻译 |
| 导出格式 | DOCX / PDF / TXT（复用 draft/export） |

---

## 架构

```
Frontend (Vue 3)
HomeView.vue
├── TabBar.vue              ← 新增：审核 | 翻译 | 对比
├── TranslatePanel.vue      ← 新增：翻译工作台主体（合同翻译 Tab）
│   ├── TranslateToolbar    ← 语言标签 + 操作按钮
│   └── TranslateClauseRow  ← 单条：左原文 | 右译文（可编辑）
│       └── ClauseEditPopover ← 编辑弹层
├── ChatPanel.vue           ← 复用（审核 Tab）
│   └── [🌐 翻译报告] 按钮  ← ChatPanel 工具栏新增
├── CompareUploadDialog     ← 复用（对比 Tab）
└── ContractViewer.vue      ← 复用（翻译 Tab 激活时自动折叠）

Backend (FastAPI)
api/translate.py            ← 新增路由
core/translator.py          ← 新增翻译引擎
schemas/translate.py        ← 新增 Pydantic 模型
复用: core/llm/, core/chunker.py, core/docx_renderer.py, api/draft.py (export)
```

净新增：后端 3 文件 + 前端 4 组件 + 1 composable。

---

## 翻译管线

### 合同翻译（/translate/generate）

```
1. 语言检测 (LLM)
   → 检测源语言，确定质量 Tier
   → 不确定时弹出语言选择器
   → SSE: progress

2. 条款分块 (ContractChunker)
   → 复用已有分块逻辑
   → 为每条条款注入上下文
   → SSE: progress

3. 逐条流式翻译 (LLM)
   → 每条条款独立调用 LLM
   → SSE 逐字输出 token → clause_done
   → 某条失败标记 skip，不中断全局

4. 后处理（用户操作）
   → 逐条编辑 / 单条重翻 / 下载导出 / 存为合同
```

### 文本翻译（/translate/text）

用于审核报告、任意文本的翻译，不走合同管线：

```
1. 语言检测 (LLM) → SSE: progress
2. 全文流式翻译 → SSE: token → done
3. 结果可下载（复用 /draft/export）
```

---

### SSE 事件序列

合同翻译：
```
event: progress
data: {"stage":"detect","detected":"en","tier":1}

event: progress
data: {"stage":"chunked","total_clauses":8}

event: token
data: {"clause_index":0,"content":"第一"}

event: clause_done
data: {"clause_index":0,"original":"Article 1...","translated":"第一条..."}

event: done
data: {"total_clauses":8,"translated":8,"source_lang":"en","target_lang":"zh"}
```

文本翻译：
```
event: progress
data: {"stage":"detect","detected":"zh","tier":1}

event: token
data: {"content":"This Agreement"}

event: done
data: {"content":"全文...", "source_lang":"zh","target_lang":"en"}
```

---

### 错误处理

| 场景 | 前端 | 后端 |
|------|------|------|
| 某条翻译超时 | 显示 ⚠️ + 重试按钮 | fallback 重试 1 次，仍失败 mark skip |
| 语言无法检测 | 弹出语言选择器 | 返回 ambiguous:true |
| SSE 断连 | 自动重连，已完成条款保留 | 支持 resume（传入已完成 clause_index） |
| 全文完成但有失败条款 | 显示原文 + "手动重翻此条" | done 事件带 skipped_clauses 列表 |

---

## API 设计

### POST /api/translate/generate（SSE）

流式翻译合同全文（逐条）。

Request:
```json
{
  "contract_id": 42,
  "target_lang": "zh",
  "provider": null,
  "model": ""
}
```

Response: SSE stream（progress → token → clause_done → done）

---

### POST /api/translate/clause（SSE）

单条条款重新翻译。

Request:
```json
{
  "contract_id": 42,
  "clause_index": 2,
  "original_text": "The Seller agrees to indemnify...",
  "instruction": "请将 indemnify 翻译为'赔偿'"
}
```

Response: SSE stream（token → done）

---

### POST /api/translate/text（SSE）

翻译任意文本（审核报告等），不依赖合同。

Request:
```json
{
  "content": "根据审核，本合同存在以下主要风险...",
  "source_lang": "zh",
  "target_lang": "en",
  "provider": null,
  "model": ""
}
```

- `source_lang` 可为 null，此时自动检测
- `target_lang` 必填

Response: SSE stream（progress → token → done）

---

### POST /api/translate/save（JSON）

翻译结果存为子合同。

Request:
```json
{
  "contract_id": 42,
  "translated_content": "第一条 合同期限...",
  "source_lang": "en",
  "target_lang": "zh",
  "filename": "Contract_EN_2024_ZH"
}
```

Response:
```json
{
  "id": 43,
  "parent_contract_id": 42,
  "source": "translated",
  "source_lang": "en",
  "target_lang": "zh",
  "clause_count": 8
}
```

- 保存时自动调用 `ContractChunker.split()` 重新分块，写入正确的 `clause_count`
- 确保译文合同可以直接被审核

---

### 复用已有端点

| 端点 | 复用场景 |
|------|---------|
| POST /api/draft/export | 译文下载 DOCX/PDF/TXT |
| POST /api/reviews | 译文存为合同后发起审核 |

---

## System Prompt 设计

### 翻译专用 Prompt

```
# 角色与目标
你是一位拥有 20 年双语法律实务经验的合同翻译专家，精通中英文法律文书。
核心任务：将源语言合同条款准确翻译为目标语言，保持法律效力和格式。

# 行为边界
- 法律术语必须使用目标语言司法辖区对应的标准术语
  - 例：indemnification → 赔偿/免责（视语境）
  - 例：force majeure → 不可抗力
  - 不确定的术语用「【需确认：术语】」标注
- 不得增删条款内容，不得改变权利义务关系
- 保持原文的条款编号、层级结构不变

# 输出格式
- 直接输出翻译后的条款文本
- 条款标题保持「第X条 标题」格式（中文）或「Article X — Title」格式（英文）
- 占位符保持原文格式：「【请填写：xxx】」

# 质量要求
- 准确 > 流畅：法律含义不可为追求语言通顺而牺牲
- 术语一致性：同一原文术语在全文中使用同一译文
- 句式保留：原文的列举、但书、条件从句结构应尽量保留
```

### Tier-Specific 追加

| Tier | 追加指令 |
|------|---------|
| 1（英↔中） | 无额外指令 |
| 2（日韩法德→中） | 「注意：源语言与中文法律体系存在差异，不确定处请标注【需确认】」 |
| 3（其他→中） | 先翻译为英文再翻译为中文（两阶段），每句标注置信度 |

---

## 数据模型变更

Contract 表新增字段：

```python
# 在 models/__init__.py 的 Contract 类中新增：
parent_contract_id = Column(
    Integer,
    ForeignKey("contracts.id", ondelete="CASCADE"),
    nullable=True,
)
source_lang = Column(NVARCHAR(10), nullable=True)   # en / zh / ja / ko ...
target_lang = Column(NVARCHAR(10), nullable=True)

# 自引用关系（与现有 back_populates 风格一致）
parent = relationship("Contract", back_populates="children", remote_side=[id])
children = relationship("Contract", back_populates="parent", cascade="all, delete-orphan")
```

- `parent_contract_id` — 译文指向原文（仅 source='translated' 时有值）
- `source_lang` / `target_lang` — 语言代码，翻译产生时写入
- `source` 字段已有 `'draft'` 值，新增 `'translated'` 值
- **级联删除**：父合同删除时，所有子译文自动 CASCADE 删除（由 FK ondelete 保证）
- **删除端点**：无需额外修改，数据库层 CASCADE 已覆盖

---

## 前端组件说明

### TabBar.vue
- 三个 Tab：审核 | 翻译 | 对比
- activeTab 状态在 HomeView 内部管理
- 切换 Tab 时保持侧边栏选中合同

### TranslatePanel.vue（合同翻译 Tab）
- 状态机：idle → ready → translating → done
- idle：未选中合同或选中中文合同（翻译方向无意义）
- ready：检测到非中文合同，显示语言信息 + 开始按钮
- translating：SSE 流式接收，逐条渲染 TranslateClauseRow
- done：全部完成，显示操作工具栏
- **激活时 ContractViewer 自动折叠**，翻译工作台占满主区域

### ChatPanel 变更（审核 Tab）
- 审核结果面板顶部新增「🌐 翻译报告」按钮
- 点击 → 弹出语言选择（中→英 / 英→中）
- 调用 `/api/translate/text`，SSE 流式输出翻译后的报告全文
- 完成后显示下载按钮

### TranslateClauseRow.vue
- 左列：原文（只读，灰色边框）
- 右列：译文（可编辑，点击进入 inline 编辑模式）
- 操作：「重翻此条」按钮（发送 clause 指令）
- 失败状态：红色边框 + 重试按钮

### Sidebar 变更
- 译文合同在原文下方缩进显示（父子关系）
- 原文合同旁显示源语言标签（EN/JA/KO 等）
- 选中合同跨 Tab 保持

---

## 质量 Tier 系统

```
detect_language(text) → (lang, tier)
  en ↔ zh  → Tier 1  ✅ 全功能
  ja/ko/fr/de → zh  → Tier 2  ⚠️ 需人工复核术语
  other → zh         → Tier 3  ⚠️ 经英文中转 + 强提示复核
```

Tier 影响：
- System Prompt 的 disclaimer 强度
- 翻译结果顶部的质量提示横幅
- Tier 3 走两阶段翻译（原文→英文→中文）

---

## 测试要点

1. 语言检测准确性（中/英/日/韩/法/德/混合语言）
2. 逐条翻译完整性（条款数、编号、内容对应）
3. 文本翻译（审核报告英译中、中译英）
4. SSE 断连 → 重连恢复
5. 单条重翻后全文中该条替换
6. 译文保存为子合同 → 自动分块（clause_count > 0）
7. 译文合同可独立审核
8. DOCX/PDF 导出格式正确（中文/英文/多语）
9. Parent 合同删除 → 子译文级联删除
10. 翻译 Tab 激活时 ContractViewer 自动折叠
