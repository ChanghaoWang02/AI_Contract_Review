# ATCR — AI-Powered Contract Review (AI 智能合同审核系统)

## Project Overview

ATCR is a web application that allows users to upload contracts, have them automatically reviewed and evaluated by generative AI, and receive actionable recommendations through an interactive chat interface.

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | Vue 3 + Vite + Naive UI + Pinia + Vue Router | Chinese ecosystem, excellent UI components |
| Backend | Python FastAPI | Async support, SSE streaming, strong ML ecosystem |
| Database | SQL Server | Relational data + native JSON support (`FOR JSON`/`OPENJSON`) |
| LLM | Multi-model via adapter pattern | Claude, OpenAI, Qwen, DeepSeek — config-driven switching |
| Deployment | Docker Compose (FastAPI + SQL Server + Frontend) | Single command startup |

## Architecture: Modular Monolith

```
┌─────────────────────────────────────────────────────────────┐
│  Vue 3 SPA (Vite + Naive UI)                                 │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ ┌─────────────┐ │
│  │ 合同上传  │ │ AI 聊天   │ │ 审核报告    │ │ 规则管理    │ │
│  └──────────┘ └──────────┘ └─────────────┘ └─────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  FastAPI REST + SSE (streaming responses)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ 合同 CRUD │ │ 审核引擎  │ │ 对话引擎  │ │ 规则管理     │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
│  ┌──────────┐ ┌──────────────────────────────────────────┐  │
│  │ 合同解析  │ │ LLM 适配层 (Claude/OpenAI/Qwen/DeepSeek) │  │
│  │ PDF/DOCX │ │ ProviderRegistry → config-driven switch  │  │
│  └──────────┘ └──────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ SQL Server (合同 + 审核记录 + 对话历史 + 自定义规则)  │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Core User Flow

```
Upload Contract → AI Parse → Structured Review → Chat Interaction → Generate Report
(PDF/DOCX/TXT)   (extract    (preset dimensions  (clause-anchored   (export/download)
                  text,       + custom rules)      follow-up Q&A)
                  split clauses)
```

## Frontend Layout

```
┌──────────┬────────────────────────────────────┬──────────────┐
│ Sidebar  │        AI Chat Panel               │ Contract     │
│ ──────── │  ┌──────────────────────────────┐  │ Viewer       │
│ 📋 合同   │  │ Chat messages (SSE stream)   │  │ ──────────── │
│ ➕ 上传   │  │ - AI findings & suggestions  │  │ Clause 1     │
│ ⚙️ 规则   │  │ - User follow-up questions   │  │ Clause 2 🔴 │
│ 📊 历史   │  │                              │  │ Clause 3     │
│          │  │ ┌─────────────────────┐       │  │              │
│          │  │ │ Input (w/ clause    │ Send  │  │ [◀ Collapse] │
│ 240px    │  │ │ anchor support)     │       │  │              │
│          │  │ └─────────────────────┘       │  │ 360px        │
│          │  └──────────────────────────────┘  │ (collapsible)│
├──────────┴────────────────────────────────────┴──────────────┤
│  When collapsed: floating 📄 button to reopen contract panel │
└──────────────────────────────────────────────────────────────┘
```

## LLM Adapter Layer

```
CoreService (review engine / chat engine)
        │
   LLMProvider (abstract base)
   ├── ClaudeAdapter    → Anthropic API
   ├── OpenAIAdapter    → OpenAI API
   ├── QwenAdapter      → 通义千问 API
   └── DeepSeekAdapter  → DeepSeek API
        │
   ProviderRegistry
   resolve(model_name) → Adapter
   Config-driven switch via environment variables
```

### Model Selection Strategy

| Scenario | Recommended Model | Reason |
|----------|-------------------|--------|
| Deep clause analysis | Claude | Long context, strong reasoning |
| Chinese polishing | Qwen / DeepSeek | Chinese-optimized |
| Quick Q&A | Any available | Low latency |
| Custom rule execution | Follow user config | Flexibility |

### Fallback Chain

```
LLM_PROVIDER=claude
LLM_FALLBACK_PROVIDERS=openai,qwen
# Timeout or error → auto-fallback to next provider
```

## Chat Interaction Modes

| Mode | Description |
|------|-------------|
| Global conversation | Free-form Q&A based on full contract text |
| Clause-anchored | Click a clause → chat context auto-scoped to that clause |
| Review follow-up | AI flags a risk → user can ask "How should I revise this?" |

## Data Model (SQL Server)

- **Contract**: id, filename, content (TEXT), file_type, file_size, user_id, created_at
- **Review**: id, contract_id (FK), status, summary, risk_level, findings (JSON — NVARCHAR(MAX)), created_at
- **Message**: id, review_id (FK), role (user/assistant), content, anchor_clause_id, created_at
- **CustomRule**: id, user_id, name, prompt_template, category, is_active, created_at

### Review.findings JSON structure

```json
{
  "clauses": [
    {
      "id": "clause_1",
      "original_text": "...",
      "summary": "违约责任条款",
      "risk": "high",
      "issues": [
        { "type": "模糊用语", "detail": "..." },
        { "type": "法律风险", "detail": "..." }
      ],
      "suggestions": ["建议修改为...", "可参考..."],
      "revised_text": "推荐的修改后文本"
    }
  ],
  "overall_score": 72,
  "summary": "合同整体评估..."
}
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/contracts/upload` | Upload contract (multipart/form-data) |
| GET | `/api/contracts` | List contracts |
| GET | `/api/contracts/{id}` | Contract detail + full text |
| DELETE | `/api/contracts/{id}` | Delete contract |
| POST | `/api/reviews` | Create review (triggers AI analysis) |
| GET | `/api/reviews/{id}` | Get review result |
| GET | `/api/reviews/{id}/stream` | SSE: review progress |
| POST | `/api/chat/stream` | SSE: chat with clause-anchor support |
| GET | `/api/chat/{review_id}/history` | Chat history |
| GET | `/api/rules` | List custom rules |
| POST | `/api/rules` | Create/update rule |
| DELETE | `/api/rules/{id}` | Delete rule |

### SSE Stream Format

```
event: token
data: {"content": "...", "clause_id": "clause_2"}

event: done
data: {"review_id": "xxx", "token_usage": 1523}

event: error
data: {"message": "模型调用超时，已切换至备用模型重试"}
```

## Error Handling

| Scenario | Frontend | Backend |
|----------|----------|---------|
| LLM timeout | Show "Generating..."; prompt retry after 30s | Auto-fallback model; error after 2 failures |
| File too large (>10MB) | Pre-upload validation | Secondary validation; return 400 |
| Unsupported format | Filter on upload | Return 400 with supported formats |
| Token limit exceeded | — | Auto-chunk: split into clauses, review individually |
| Network disconnect | SSE auto-reconnect | — |

## Project Directory Structure

```
atcr/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Configuration management
│   │   ├── api/                 # Route handlers
│   │   │   ├── contracts.py
│   │   │   ├── reviews.py
│   │   │   ├── chat.py
│   │   │   └── rules.py
│   │   ├── core/
│   │   │   ├── llm/             # LLM adapter layer
│   │   │   │   ├── base.py      # Abstract LLMProvider
│   │   │   │   ├── claude.py
│   │   │   │   ├── openai_adapter.py
│   │   │   │   ├── qwen.py
│   │   │   │   └── registry.py  # ProviderRegistry
│   │   │   ├── parser.py        # Contract file parser (PDF/DOCX/TXT)
│   │   │   ├── reviewer.py      # Review engine
│   │   │   └── chunker.py       # Long contract chunking
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   └── db/                  # Database connection & init
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── HomeView.vue     # Main view (chat + contract panel)
│   │   │   └── RulesView.vue    # Rule configuration
│   │   ├── components/
│   │   │   ├── layout/          # AppLayout, Sidebar
│   │   │   ├── chat/            # ChatPanel, MessageBubble, ChatInput
│   │   │   ├── contract/        # ContractViewer, UploadDialog
│   │   │   ├── review/          # ReviewReport, ClauseCard, RiskBadge, ScoreGauge
│   │   │   └── rules/           # RuleList, RuleEditor
│   │   ├── composables/         # useChat, useReview, useContract, useSSE
│   │   ├── stores/              # Pinia stores
│   │   └── router/              # Vue Router config
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml           # FastAPI + SQL Server + Frontend
└── README.md
```

## Key Design Decisions

1. **Modular monolith over microservices** — single developer, 0→1 phase; module boundaries are clean for later split
2. **Adapter pattern for LLM** — lightweight self-built abstraction (not LiteLLM/LangChain), <200 lines, no heavy dependencies
3. **SSE over WebSocket** — simpler, unidirectional streaming fits chat + review progress; auto-reconnect built in
4. **SQL Server JSON column** for findings — avoids separate NoSQL store; SQL Server native JSON functions suffice
5. **Low temperature (0.3)** for contract review — consistency matters more than creativity in legal analysis
6. **Naive UI over Element Plus** — better Tree-shaking, cleaner TypeScript support, modern Vue 3 composition API
7. **Contract panel collapsible** — maximizes chat real estate while keeping contract accessible via floating button
