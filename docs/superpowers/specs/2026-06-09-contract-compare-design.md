# ATCR — 合同对比审核功能设计

> 状态：已确认 | 创建：2026-06-09

## 1. 概述

在合同面板新增「对比」入口。用户上传新版合同文件 → 系统逐条匹配条款 → 本地 diff 识别变更 → AI 批量分析每条变更对指定视角方的有利/不利影响 → 全屏弹窗展示左右分栏对比 + 变更摘要列表。

不持久化，关闭即消失。

## 2. 用户流程

```
合同面板 [📄 对比] 按钮
  → 文件上传框 + 视角选择（甲方/乙方/中立，默认中立）
  → 确定 → 上传中 → 全屏弹窗打开
  → 进度：解析中 → 匹配条款 → AI 分析变更...
  → 对比视图加载完成
    - 左：原合同原文，变更行高亮
    - 右：新版原文，变更行高亮
    - 右栏：变更摘要列表（风险标签 + 原因）
    - 底部：汇总统计 + 视角标签（只读）
  → 点击摘要条目 → 左右两侧滚动定位
  → 关闭弹窗 → 恢复原布局

特殊情况：两份合同条款内容完全一致 → 弹窗显示提示，无需 AI 调用
```

## 3. API 设计

### 3.1 新增端点

```
POST /api/contracts/{id}/compare
```

**请求**：multipart/form-data

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `file` | file | 是 | 新版合同文件（PDF/DOCX/TXT，≤10MB） |
| `perspective` | string | 否 | `"party_a"` / `"party_b"` / `"neutral"`，默认 `"neutral"`。party_a 通常对应合同中先出现的角色方（出租方、卖方、用人单位等），party_b 为相对方 |
| `provider` | string | 否 | 指定 LLM 提供商，复用现有 fallback 链 |
| `model` | string | 否 | 指定具体模型 |

**响应**：`text/event-stream`（SSE）

| event | 格式 | 说明 |
|-------|------|------|
| `progress` | `{"phase": "parsing"|"matching"|"analyzing", "detail": "..."}` | 阶段进度通知 |
| `clause` | `{"clause_id": "...", "change": "modified"|"added"|"deleted", "risk": "favorable"|"neutral"|"unfavorable"|"unknown", "reason": "...", "old_text": "...", "new_text": "..."}` | 单条变更分析完成 |
| `done` | `{"total": 20, "favorable": 5, "neutral": 10, "unfavorable": 3, "unknown": 0, "added": 1, "deleted": 1, "token_usage": 4500}` | 全部完成 |
| `error` | `"错误信息"` | 致命错误（如合同无法解析） |

- `added`/`deleted` 类型的条款不调用 AI，`risk` 固定为 `"neutral"`，`reason` 固定为 `"新增条款"` 或 `"已删除条款"`
- `unknown`：AI 返回无法解析时标记，不中断整体流程

## 4. 条款匹配算法

```
输入：原合同 clauses[]，新版合同 clauses[]

第1轮 — 编号匹配
  - 提取条款编号（"第三"→3），编号一致 → 相似度验证
  - 全文本相似度 ≥ 0.4（SequenceMatcher） → 匹配成功
  - 相似度 < 0.4 → 认为条款被调序，降级进入第3轮

第2轮 — 标题包含匹配
  - 提取条款标题（"违约责任"）
  - 短标题 ⊂ 长标题 → 相似度验证 ≥ 0.4 → 匹配成功
  - 否则 → 降级进入第3轮

第3轮 — 全文本相似度匹配
  - 对剩余未匹配条款，计算全文本相似度
  - 相似度 ≥ 0.6 → 匹配成功
  - 余下的 → 原合同侧标记「已删除」（change=deleted）
  -         新版侧标记「新增」（change=added）

本地 diff：
  - 匹配成功的条款对，逐对比较原文
  - 文本不同 → change=modified
  - 文本相同 → 不报告

全部条款无变更（total=0）：
  - 跳过 AI 调用
  - 直接发送 done: {"total": 0, "favorable": 0, ...}
  - 前端显示「两份合同条款内容完全一致，未检测到变更」
```

## 5. AI 批量分析

### 5.1 调用策略

- 仅对 `change=modified` 的条款调用 AI
- **批量调用**：每批 ≤ 5 条，一次 LLM 请求分析多条
- 单条解析失败（index 缺失/risk 无效） → 标记 `risk=unknown`，继续下一条
- AI 返回的 JSON 解析失败 → 复用 `_parse_json_response()` 多策略提取（直接解析 → Markdown 代码块提取 → 首尾花括号截取 → 控制字符清理），仍失败则整批标记 `unknown`
- 单批次 LLM 调用失败（网络/超时等） → 该批次所有条目标记 `risk=unknown`

### 5.2 System Prompt

```markdown
# 角色与任务
你是一位合同审核律师。对以下条款变更逐条评估，判断对指定方是否有利。

分析视角：{perspective_label}

# 输入格式
{每条：原条款 | 新条款，编号}

# 输出格式（严格 JSON 数组）
[
  {"index": 0, "risk": "favorable", "reason": "违约金从10%降至5%，减轻违约责任"},
  {"index": 1, "risk": "neutral", "reason": "仅调整条款顺序，未改变权利义务"},
  {"index": 2, "risk": "unfavorable", "reason": "新增单方解除权，赋予对方任意终止合同的权利"}
]

# 判定标准
- favorable：分析视角方获得更多权利、更少义务、更低风险
- neutral：实质性权利义务未改变（措辞微调、结构调整、错别字修正）
- unfavorable：分析视角方承担更多义务、更少权利、更高风险

# 约束
- reason 不超过 30 字，不引用法条
- 无法判断时返回 "neutral"
- 只返回 JSON 数组，不要其他内容
```

## 6. 前端设计

### 6.1 组件树

```
HomeView
  ├── UploadDialog (新增视角选择：甲方/乙方/中立 radio group)
  └── CompareModal (n-modal, fullscreen)
        ├── ComparePanel ×2 (左：原版，右：新版)
        │     └── 条款行 + 高亮背景色
        ├── ChangeList (右栏：变更摘要)
        │     └── 条目：风险标签 + 变更类型 + reason
        └── CompareSummary (底部固定栏)
              ├── 统计数字 + token 用量
              └── 视角标签（只读展示，不可切换）
```

### 6.2 交互

| 交互 | 行为 |
|------|------|
| 点击合同面板 [📄 对比] | 弹出上传对话框（含视角选择 radio group） |
| 选择文件 + 视角 → 确定 | 开始上传 + SSE 连接，全屏弹窗打开 |
| 上传阶段 | 弹窗显示上传进度条 |
| 解析/匹配阶段 | 弹窗显示旋转 loading + 阶段文字（progress 事件驱动） |
| 分析阶段 | 逐条 clause 事件：左右两侧对应条款高亮 + 变更列表追加一行 |
| 点击变更列表条目 | 左右两侧滚动定位到对应条款 |
| 全部无变更 | 弹窗显示「两份合同条款内容完全一致，未检测到变更」|
| 关闭弹窗 | 断开 SSE，清空状态，恢复原布局 |
| 左右分栏 | 同步滚动 |

### 6.3 高亮色方案

| 变更类型 | 背景色 | 说明 |
|----------|--------|------|
| `modified + unfavorable` | `#fff0f0` 浅红 | 不利变更 |
| `modified + favorable` | `#f0fff0` 浅绿 | 有利变更 |
| `modified + neutral` | `#fffff0` 浅黄 | 中性变更 |
| `added` | `#f0f4ff` 浅蓝 | 新增条款 |
| `deleted` | `#f5f5f5` 浅灰 | 已删除条款 |

## 7. 后端实现要点

### 7.1 文件结构

```
backend/app/
  api/contracts.py          ← 新增 POST /{id}/compare 端点
  core/contract_compare.py  ← 新增：条款匹配 + diff 逻辑
```

### 7.2 compare 端点流程

```
1. 验证原合同存在
2. 解析上传文件 → 提取文本
3. ContractChunker.split() 切分两份合同
4. 条款匹配（3 轮算法）
5. 本地 diff 识别变更
6. 发送 progress: matching
7. 将 modified 条款分批（≤5 条/批）
8. 发送 progress: analyzing
9. 逐批调用 AI → SSE clause 事件
   - 通过 ProviderRegistry 解析，复用现有 fallback 链
10. 汇总 → SSE done 事件
```

### 7.3 错误处理

| 场景 | 处理 |
|------|------|
| 上传文件无法解析 | SSE error 事件，关闭连接 |
| 原合同无内容 | SSE error: "原合同内容为空" |
| 两份合同无法匹配任何条款 | SSE error: "两份合同结构差异过大，无法对比" |
| AI 批次调用失败 | 该批次全部标记 unknown，继续下一批 |
| 客户端断开 | 同现有 SSE 连接处理（GeneratorExit + BaseException 捕获） |

## 8. 范围边界

**本期不做**：
- 对比结果保存/历史记录
- 从合同库选择两份库内合同对比
- 对比结果导出为 PDF/DOCX
- 差异忽略/接受审核（如"此变更已确认可接受"）
- AI 提供具体修改建议（仅做简洁评估）
- 更多于5条/批的配置化

## 9. 关键决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 入口位置 | 合同面板顶部按钮 | 用户需先查看原合同才有对比意图 |
| 展示方式 | 全屏弹窗 | 隔离当前聊天/审核状态，关闭不丢失 |
| 匹配粒度 | 条款级（复用 Chunker）| 复用现有切分，法律分析有上下文 |
| AI 分析深度 | 简洁（风险标签 + ≤30字原因）| 快速决策，不需要逐条长篇分析 |
| 批量调用 | 每批 ≤5 条 | 平衡延迟和准确率 |
| 持久化 | 不做 | v1 验证效果，后续按需添加 |
| 分析视角 | 甲方/乙方/中立 | 同一变更对不同方意义不同 |
