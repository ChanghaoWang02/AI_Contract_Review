# 审核报告 PDF 导出 — 设计文档

> 状态：已确认 | 创建：2026-06-08 | 更新：2026-06-08

## 1. 决策总览

| 维度 | 选择 | 理由 |
|------|------|------|
| 导出格式 | PDF | 正式交付物，排版固定 |
| PDF 库 | ReportLab | 程序化像素控制，中文支持成熟 |
| 生成时机 | 即时生成（不预存） | 不占存储空间 |
| 内容配置 | 设置页改默认值，一键导出 | 减少操作步骤 |
| 配置存储 | 前端 localStorage | 零后端改动，有用户系统后迁移 |
| 触发入口 | 审核报告弹窗底部 + 历史审核列表 | 两处均可触发 |
| 中文字体 | 微软雅黑 (`C:/Windows/Fonts/msyh.ttc`) | Windows 自带，专业现代 |

## 2. API 设计

### 2.1 新增端点

```
GET /api/reviews/{review_id}/export
  ?risk_filter=high,medium,low
  &sections=cover,summary,clauses,disclaimer
```

**参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `risk_filter` | string (csv) | `high,medium,low` | 按风险等级筛选条款 |
| `sections` | string (csv) | `cover,summary,clauses,disclaimer` | 控制包含的章节 |

**请求头**：无需特殊头。前端按钮进入 loading 态，超时 30s 提示"生成中"。

**成功响应**：
```
HTTP 200
Content-Type: application/pdf
Content-Disposition: attachment; filename="审核报告_{合同名}_{日期}.pdf"
```

**错误响应**：

| 状态码 | 场景 | Body |
|--------|------|------|
| 404 | 审核记录不存在 | `{"detail":"审核记录不存在。"}` |
| 409 | 审核尚未完成 | `{"detail":"审核尚未完成，无法导出报告。当前状态：processing"}` |
| 422 | 审核失败 | `{"detail":"审核未成功（状态：error），无法导出。"}` |
| 500 | `findings_json` 损坏 | `{"detail":"审核数据异常，请联系管理员。"}` (内部记 error log) |
| 500 | ReportLab 渲染失败 | `{"detail":"PDF 生成失败，请重试。"}` (内部记 exception log) |

### 2.2 实现位置

- **路由**：`backend/app/api/reviews.py` 新增 `GET "/{review_id}/export"`
- **生成器**：新建 `backend/app/core/pdf_renderer.py`（PDF 渲染逻辑）
- **依赖**：`reportlab` 加入 `backend/requirements.txt`

## 3. PDF 报告结构

### 3.1 章节概览

```
┌─────────────────────────────────────┐
│ 封面                                 │
│   合同名称 / 审核方 / 日期 / 评分   │
│   风险等级 / AI 模型                 │
│   分批脚注（如有）                   │
├─────────────────────────────────────┤
│ 一、综合评估                         │
│   评分圆环（ReportLab 绘图）          │
│   风险分布：高 N 条 / 中 N 条 / 低 N 条 │
│   整体摘要文本                       │
│   模型链（如有多批次）               │
├─────────────────────────────────────┤
│ 二、逐条分析                         │
│   条款 N（按风险排序，高风险在前）    │
│   ├ 原文（灰色底色 #f5f5f5）         │
│   ├ 风险标签（红/橙/绿 圆角矩形）     │
│   ├ 问题详情（issue.type + detail）  │
│   ├ 修改建议（suggestions 列表）     │
│   └ 修订后文本（revised_text，如有）│
├─────────────────────────────────────┤
│ 附录                                 │
│   免责声明：本报告由 AI 生成，       │
│   不构成正式法律意见，               │
│   重要决策请咨询执业律师。           │
└─────────────────────────────────────┘
```

### 3.2 封面内容

| 字段 | 值来源 |
|------|--------|
| 合同名称 | `Contract.original_filename`（去扩展名） |
| 审核方 | `ATCR AI 智能合同审核系统 · 驱动模型：{model}` |
| 审核日期 | `Review.completed_at` 格式化 |
| 综合评分 | `Review.overall_score`（大号数字） |
| 风险等级 | `Review.risk_level` → 中文（高风险/中风险/低风险） |
| AI 模型 | 分批时取首个 provider；脚注 `*共 N 批次，涉及 M 个模型` |

### 3.3 逐条分析排序规则

1. 按 `risk` 排序：high → medium → low
2. 同级按条款 `index`（原文顺序）排序
3. 应用 `risk_filter` 过滤后再排序

### 3.4 视觉元素实现

| 元素 | ReportLab 实现 |
|------|---------------|
| 评分圆环 | `wedge()` + `circle()` + 文字标注（评估章节） |
| 风险标签 | `RoundRect` + 对应颜色背景 + 白色文字 |
| 原文底色 | `Table` 单元格 `BACKGROUND=#f5f5f5` |
| 页码 | `PageTemplate.onPage` 回调，格式 `第 X 页 / 共 Y 页` |
| 条款跨页 | 条款标题行设 `keepWithNext`；Table `repeatRows=1` |

### 3.5 字体注册

```python
# 启动时/首次调用时注册
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

FONT_PATH = "C:/Windows/Fonts/msyh.ttc"
FONT_NAME = "MicrosoftYaHei"

pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
```

启动时检测字体是否存在，缺失时 log warning 并降级到 `Helvetica`（英文），功能不 crash。

## 4. 数据流

```
用户点击"导出 PDF"
  ↓
前端：按钮 loading 态
  ↓
GET /api/reviews/{id}/export?risk_filter=...&sections=...
  ↓
reviews.py endpoint:
  1. 查询 Review + 关联 Contract
  2. 校验 status == "completed"，否则返回 409/422
  3. 解析 findings_json，失败返回 500
  4. 调用 pdf_renderer.build_report(findings, contract, options)
  5. 返回 StreamingResponse(report_bytes, media_type="application/pdf")
  ↓
前端：收到 blob → 创建临时 URL → 触发浏览器下载
  ↓
前端：解除 loading 态
```

## 5. 文件命名规则

```
审核报告_{合同名}_{YYYY-MM-DD}.pdf
```

- 合同名：去除文件扩展名，替换非法字符 `\ / : * ? " < > |` 为下划线
- 日期：`Review.completed_at` 的日期部分

## 6. 前端改动

### 6.1 ReviewReport 弹窗

[ReviewReport.vue](frontend/src/components/review/ReviewReport.vue) 底部新增按钮：

```html
<div class="report-actions">
  <n-button type="primary" :loading="exporting" @click="exportPDF">
    <template #icon><n-icon><download-outline /></n-icon></template>
    导出 PDF
  </n-button>
</div>
```

### 6.2 历史审核列表

侧边栏每条审核记录右侧操作列新增导出图标按钮（`<n-button text>` + DownloadOutline icon）。

### 6.3 导出 composable

新建 `frontend/src/composables/useExportPDF.ts`，封装：

- 调用导出 API
- 处理 blob 响应
- 触发浏览器下载
- 错误提示
- loading 状态

### 6.4 导出设置

<!-- TODO: 后续版本在设置页实现。当前版默认全选，参数硬编码在前端 composable 中。 -->
当前版本默认值：`risk_filter=high,medium,low&sections=cover,summary,clauses,disclaimer`。

## 7. 错误处理矩阵

| 场景 | HTTP | 前端行为 |
|------|------|---------|
| 审核不存在 | 404 | `message.error("审核记录不存在")` |
| 审核未完成 | 409 | `message.warning("审核正在进行中，完成后即可导出")` |
| 审核失败 | 422 | `message.error("审核未成功，请重新审核")` |
| findings 损坏 | 500 | `message.error("数据异常，请联系管理员")` |
| PDF 生成异常 | 500 | `message.error("PDF 生成失败，请重试")` |
| 网络超时 | — | `message.error("导出超时，请检查网络后重试")` |
| 服务不可达 | — | `message.error("服务暂不可用，请稍后重试")` |

## 8. 依赖变更

`backend/requirements.txt` 新增：

```
reportlab>=4.2
```

## 9. 测试要点

| 测试场景 | 验证项 |
|----------|--------|
| 正常导出 | PDF 可打开，内容完整，封面字段正确 |
| 中文渲染 | 条款原文、摘要、建议均无 tofu 方块 |
| 风险筛选 | `risk_filter=high` 仅含高风险条款 |
| 章节开关 | `sections=cover` 仅封面，无逐条分析 |
| 空合同 | 仅一条"合同全文"条款，正常导出 |
| 分批审核 | 封面显示主模型，脚注正确 |
| 审核未完成 | 409 + 前端提示 |
| findings 损坏 | 500 + 不 crash |
| 字体缺失 | warn 日志 + 降级英文（不 crash） |
| 大合同 30+ 条款 | 正常分页 + 页码正确 |

## 10. 范围边界（本期不做）

- 不预生成 PDF 存储
- 不实现导出设置页 UI（参数默认全选）
- 不支持水印/Logo 上传
- 不支持 Word/Markdown 导出
- 不生成合同原文之后的完整合同拼接
