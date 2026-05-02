# Amzur AI Chat

An internal multi-user conversational AI platform built with **FastAPI**, **React 18**, and **LangChain**. Supports threaded persistent chat, email/password + Google OAuth authentication, streaming LLM responses, and conversational memory — all routed through the Amzur LiteLLM proxy.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Tailwind CSS v4, Vite |
| Backend | FastAPI, Python 3.11+, SQLAlchemy 2.0, Alembic |
| AI | LangChain (LCEL), LiteLLM proxy (`litellm.amzur.com`) |
| Models | `gemini/gemini-2.5-flash`, `text-embedding-3-large` |
| Database | PostgreSQL (async via `asyncpg`) |
| Auth | Email/password (bcrypt + JWT) + Google OAuth 2.0 |
| Vector Store | ChromaDB |

---

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+
- Access to the Amzur VPN (`litellm.amzur.com` is an internal endpoint)

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/achanta-srilakshmi/Amzur-AI-Forge.git
cd amzur-ai-forge
```

### 2. Backend setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and fill in SECRET_KEY, DATABASE_URL, LITELLM_API_KEY
```

### 3. Database migration

```bash
# From backend/
alembic upgrade head
```

### 4. Run the backend

```bash
uvicorn app.main:app --reload
# API available at http://localhost:8000
# Swagger UI at http://localhost:8000/docs (development only)
```

### 5. Frontend setup

```bash
cd ../frontend

npm install
npm run dev
# App available at http://localhost:5173
```

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and set:

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Random string for JWT signing |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `LITELLM_API_KEY` | Yes | API key for the Amzur LiteLLM proxy |
| `LITELLM_PROXY_URL` | Yes | `https://litellm.amzur.com` |
| `ALLOWED_DOMAINS` | No | JSON array of allowed email domains (default: `["amzur.com","evokesystems.com"]`) |
| `FRONTEND_URL` | No | Frontend origin for OAuth redirects (default: `http://localhost:5173`) |
| `GOOGLE_CLIENT_ID` | No | Google OAuth client ID (leave blank to disable) |
| `GOOGLE_CLIENT_SECRET` | No | Google OAuth client secret |

See `backend/.env.example` for the full list.

---

## Project Structure

```
/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers — HTTP only, no business logic
│   │   ├── services/     # All business logic
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   ├── ai/
│   │   │   ├── llm.py    # LiteLLM client singletons — import from here
│   │   │   ├── chains/   # LCEL chains
│   │   │   ├── memory/   # Conversation memory
│   │   │   ├── rag/      # ChromaDB client, ingestion, retrieval
│   │   │   └── prompts/  # Prompt templates
│   │   ├── db/           # Session factory, Alembic env
│   │   └── core/         # Settings, logging
│   ├── alembic/          # Database migrations
│   ├── tests/            # pytest test suite
│   ├── requirements.txt
│   └── .env.example
│
└── frontend/
    └── src/
        ├── components/   # React components
        ├── hooks/        # Custom React hooks
        ├── lib/          # API client, utilities
        └── types/        # Shared TypeScript interfaces
```

---

## Running Tests

```bash
cd backend
pytest
```

AI chains use mocked LiteLLM responses — no real API calls in CI.

---

## Key Architecture Decisions

- **Single AI gateway**: All AI calls route through `litellm.amzur.com`. No direct calls to OpenAI, Google, or Anthropic.
- **JWT in `httpOnly` cookie**: Tokens are never stored in `localStorage`. The cookie is inaccessible to JavaScript, mitigating XSS token theft.
- **DB memory**: Conversational history is fetched from the database on every request — no in-process memory stores.
- **Per-user ChromaDB collections**: Documents are isolated per user (`user_{user_id}`) to prevent cross-user retrieval.

---

## Code Quality

```bash
# Backend — lint and format
pip install ruff
ruff check .
ruff format .

# Frontend — lint
npm run lint
```

---

## License

Internal use only. Not for public distribution.
