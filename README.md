# ATCR — AI-Powered Contract Review System

AI 智能合同审核系统 | 支持合同解析、AI 审核、风险标注、条款问答、翻译对比、报告导出

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 功能特性

### 核心功能

| 功能 | 说明 |
|------|------|
| 📤 **合同上传** | 支持 PDF、DOCX、TXT 格式，自动解析文本内容 |
| 🔍 **AI 智能审核** | 多维度风险分析，条款级问题标注，高亮风险条款 |
| 💬 **条款问答** | 支持全局问答和条款锚定式问答，深挖合同细节 |
| 📊 **审核报告** | 可视化风险评分、条款卡片、问题详情、修改建议 |
| 📄 **PDF 导出** | 一键导出完整审核报告为 PDF 文件 |
| 🌐 **合同翻译** | 支持合同条款级中英互译 |
| ⚖️ **合同对比** | 两份合同并排对比，差异高亮显示 |
| ✍️ **合同起草** | AI 辅助生成合同文本 |
| ⚙️ **自定义规则** | 配置企业私有审核规则，定制审核维度 |

### AI 模型支持

| 模型 | 提供商 | 适用场景 |
|------|--------|----------|
| Claude | Anthropic | 深度条款分析、长上下文推理 |
| GPT-4o / o4-mini | OpenAI | 通用问答、快速响应 |
| Qwen | 阿里云通义千问 | 中文优化、高性价比 |
| DeepSeek | DeepSeek | 中文优化、深度推理 |

### 技术栈

**后端**
- FastAPI (异步支持、SSE 流式响应)
- SQLAlchemy + SQL Server
- Anthropic / OpenAI / DashScope SDK
- pdfplumber + python-docx (文档解析)
- ReportLab (PDF 生成)

**前端**
- Vue 3 + Composition API
- Vite + TypeScript
- Naive UI (中文优化组件库)
- Pinia (状态管理)
- Vue Router

**基础设施**
- Docker Compose (一键部署)
- SQL Server 2022

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Vue 3 SPA (Naive UI)                         │
│  ┌──────────┐ ┌──────────────┐ ┌───────────┐ ┌──────────────┐  │
│  │ 合同管理  │ │  AI 审核/问答  │ │  翻译对比  │ │   合同起草    │  │
│  └──────────┘ └──────────────┘ └───────────┘ └──────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                    FastAPI REST + SSE                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────┐ │
│  │ 合同 CRUD │ │  审核引擎  │ │  对话引擎  │ │ 翻译引擎  │ │ 起草  │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └───────┘ │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │           LLM 适配层 (Claude/OpenAI/Qwen/DeepSeek)         │  │
│  │              ProviderRegistry 配置驱动切换                 │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              SQL Server (合同 + 审核 + 对话 + 规则)         │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 环境要求

- Docker Desktop (Windows/macOS) 或 Docker Engine (Linux)
- 至少 4GB RAM (SQL Server 需要)

### 1. 克隆项目

```bash
git clone <repository-url>
cd AI_Contract_Review-main
```

### 2. 配置环境变量

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env` 文件，填入必要的 API Key：

```env
# 数据库 (SQL Server)
DB_PASSWORD=YourStrong@Password123

# AI 模型 API Keys (至少需要其中一个)
ANTHROPIC_API_KEY=sk-ant-xxxxx
OPENAI_API_KEY=sk-xxxxx
DASHSCOPE_API_KEY=sk-xxxxx
```

### 3. 启动服务 (Docker Compose)

```bash
docker-compose up -d
```

服务启动后访问：
- **前端**: http://localhost:5173
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

### 4. 本地开发启动

**后端：**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**前端：**
```bash
cd frontend
pnpm install
pnpm dev
```

---

## 项目目录结构

```
atcr/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置管理
│   │   ├── api/                 # 路由处理
│   │   │   ├── contracts.py     # 合同管理
│   │   │   ├── reviews.py       # 审核引擎
│   │   │   ├── chat.py          # 对话引擎
│   │   │   ├── rules.py         # 自定义规则
│   │   │   ├── translate.py     # 翻译功能
│   │   │   ├── draft.py         # 合同起草
│   │   │   └── draft.py         # 合同对比
│   │   ├── core/
│   │   │   ├── llm/             # LLM 适配层
│   │   │   │   ├── base.py      # 抽象基类
│   │   │   │   ├── claude.py    # Anthropic
│   │   │   │   ├── openai_adapter.py
│   │   │   │   ├── qwen.py      # 通义千问
│   │   │   │   ├── deepseek.py
│   │   │   │   └── registry.py  # 提供者注册表
│   │   │   ├── parser.py        # 合同解析 (PDF/DOCX/TXT)
│   │   │   ├── reviewer.py      # 审核引擎
│   │   │   ├── chunker.py       # 长文本分块
│   │   │   ├── translator.py    # 翻译器
│   │   │   ├── docx_renderer.py # DOCX 导出
│   │   │   └── pdf_renderer.py  # PDF 导出
│   │   ├── models/              # SQLAlchemy 模型
│   │   ├── schemas/             # Pydantic schema
│   │   └── db/                  # 数据库连接
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── views/               # 页面视图
│   │   ├── components/          # 组件
│   │   │   ├── chat/           # 聊天组件
│   │   │   ├── contract/       # 合同查看/上传
│   │   │   ├── review/         # 审核报告
│   │   │   ├── rules/          # 规则管理
│   │   │   ├── translate/      # 翻译
│   │   │   ├── compare/        # 合同对比
│   │   │   ├── draft/          # 合同起草
│   │   │   └── layout/         # 布局组件
│   │   ├── composables/        # 组合式函数
│   │   ├── stores/             # Pinia 状态
│   │   └── router/            # 路由配置
│   ├── package.json
│   └── vite.config.ts
├── docs/                       # 设计文档
├── docker-compose.yml
├── CLAUDE.md                   # 项目规范 (给 AI 阅读)
└── README.md
```

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/contracts/upload` | 上传合同文件 |
| GET | `/api/contracts` | 合同列表 |
| GET | `/api/contracts/{id}` | 合同详情 |
| DELETE | `/api/contracts/{id}` | 删除合同 |
| POST | `/api/reviews` | 创建审核任务 |
| GET | `/api/reviews/{id}` | 获取审核结果 |
| GET | `/api/reviews/{id}/stream` | SSE: 审核进度流 |
| POST | `/api/chat/stream` | SSE: 对话流 (支持条款锚定) |
| GET | `/api/chat/{review_id}/history` | 对话历史 |
| GET | `/api/rules` | 规则列表 |
| POST | `/api/rules` | 创建/更新规则 |
| DELETE | `/api/rules/{id}` | 删除规则 |
| POST | `/api/translate/contract` | 整合同翻译 |
| POST | `/api/translate/text` | 单条文本翻译 |
| GET | `/api/compare/{id1}/{id2}` | 对比两份合同 |
| POST | `/api/draft/generate` | AI 生成合同 |
| POST | `/api/draft/save` | 保存合同草稿 |

### SSE 流式响应格式

```javascript
// 审核/对话 token
event: token
data: {"content": "...", "clause_id": "clause_2"}

// 完成
event: done
data: {"review_id": "xxx", "token_usage": 1523}

// 错误
event: error
data: {"message": "模型调用超时，已切换至备用模型重试"}
```

---

## 配置说明

### LLM 模型优先级

```env
LLM_PROVIDER=claude
LLM_FALLBACK_PROVIDERS=openai,qwen,deepseek
```

### 风险等级说明

| 等级 | 颜色 | 说明 |
|------|------|------|
| high | 🔴 红色 | 高风险，建议修改 |
| medium | 🟡 黄色 | 中风险，注意条款 |
| low | 🟢 绿色 | 低风险，基本合理 |

---

## 数据模型

```sql
Contract      -- 合同文件 (id, filename, content, file_type, ...)
Review        -- 审核记录 (id, contract_id, status, summary, risk_level, findings JSON)
Message       -- 对话历史 (id, review_id, role, content, anchor_clause_id)
CustomRule    -- 自定义规则 (id, user_id, name, prompt_template, category)
```

### findings JSON 结构

```json
{
  "clauses": [
    {
      "id": "clause_1",
      "original_text": "...",
      "summary": "违约责任条款",
      "risk": "high",
      "issues": [
        { "type": "模糊用语", "detail": "..." }
      ],
      "suggestions": ["建议修改为..."],
      "revised_text": "推荐的修改后文本"
    }
  ],
  "overall_score": 72,
  "summary": "合同整体评估..."
}
```

---

## 开发指南

### 添加新的 LLM Provider

1. 在 `backend/app/core/llm/` 创建新的 adapter 类，继承 `LLMProvider`
2. 实现 `completion()` 和 `stream_completion()` 方法
3. 在 `registry.py` 注册新的 provider

```python
# backend/app/core/llm/your_model.py
from .base import LLMProvider

class YourModelAdapter(LLMProvider):
    async def completion(self, messages, **kwargs):
        # 实现
        pass
```

### 自定义审核规则

1. 进入前端「规则管理」页面
2. 创建新规则，填写名称和 prompt 模板
3. 规则将自动注入到审核流程中

---

## License

MIT License
