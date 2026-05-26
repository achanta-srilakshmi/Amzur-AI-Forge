# Platform Rules — Amzur AI Chat

This is the single source of truth for all platform conventions and non-negotiable rules.
Every agent reads this file as its first discovery step so that every output is consistent
with the platform regardless of which agent is invoked.

---

## Architecture & Layering

- **Router → Service → Schema → Model** — no business logic in router handlers
- Service functions are framework-agnostic and fully unit-testable
- No direct DB access in router handlers
- No AI calls in router handlers

---

## Database

- SQLAlchemy 2.0 style: `select()`, `mapped_column` — never `session.query()` or legacy `Column()`
- UUID primary keys on every table
- `DateTime(timezone=True)` on all timestamp columns — store UTC, convert at the API boundary
- Index every FK column: `Index("ix_<table>_<col>", Model.col)`
- No N+1 queries — use `selectinload` or `joinedload` for related data
- All new models imported in `backend/app/models/__init__.py`
- All schema changes via Alembic migrations only — never raw `ALTER TABLE`
- LangChain `SQLDatabase` requires `postgresql+psycopg2://` — always use `_build_sync_db_url()` to convert from `asyncpg`

---

## AI Layer

- All LLM and embedding clients are defined in `backend/app/ai/llm.py` — **never instantiate them elsewhere**
- LCEL chains only: `prompt | llm | parser` — **never** `LLMChain`, `SequentialChain`, or `ConversationalRetrievalChain`
- Every AI call must include user tracking:
  - Direct OpenAI SDK: `user=current_user.email`
  - LangChain chain invocation: `config={"metadata": {"user_email": current_user.email}}`
- Model references via settings only: `settings.LLM_MODEL`, `settings.IMAGE_GEN_MODEL` — never hardcoded strings
- Proxy URL and key via settings only: `settings.LITELLM_PROXY_URL`, `settings.LITELLM_API_KEY` — never hardcoded
- `OpenAIEmbeddings` always constructed with `base_url=settings.LITELLM_PROXY_URL`
- All user-facing LLM responses streamed — never buffer until full completion
- Prompt templates in `backend/app/ai/prompts/` as `.txt` files — never inline strings in chain files
- Wrap all AI SDK calls in `try/except OpenAIError → 502`; `except Exception → 500`
- `return_intermediate_steps=True` on all SQL and Pandas agents — required to extract generated query from output

---

## Authentication & Security

- JWT stored exclusively in `httpOnly` cookie (`samesite="lax"`, `secure=True` in production) — **never** `localStorage`, response body, or React state
- All protected routes use `Depends(get_current_user)` — no inline auth checks in handlers
- All user input validated by Pydantic schemas before reaching services
- Per-user data isolation: all DB queries must filter by `current_user.id`
- File uploads: validate MIME type server-side — never trust file extension
- File content to disk (`UPLOAD_DIR`) — **never** store as a DB blob; store path + metadata only
- NL-to-SQL: read-only enforced; block all 6 keywords **case-insensitively**: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `TRUNCATE`, `ALTER`
- No raw SQL string interpolation
- No secrets, model names, or URLs hardcoded — always read from `settings`
- No PII written to logs

---

## FastAPI Conventions

- `async def` for all route handlers
- All routes declare explicit `response_model`
- `get_db` injected via `Depends()` — never instantiated inside a handler
- Structured error responses: `raise HTTPException(status_code=N, detail={"error": "<code>", "message": "<text>"})`
- Streaming: `StreamingResponse(media_type="text/event-stream")`

---

## Pydantic Schemas

- All response schemas include `model_config = {"from_attributes": True}`
- No `Any` types — strict types on every field
- Separate request and response schemas — never expose ORM models directly

---

## Frontend

- All API calls through `frontend/src/lib/api.ts` — never call `fetch` or `axios` directly in components
- Server state via TanStack Query — never `fetch` in `useEffect`
- `credentials: 'include'` on every `fetch` call
- No `any` in TypeScript — strict types everywhere
- Message content rendered via `react-markdown` — never `dangerouslySetInnerHTML`
- Streaming renders token-by-token — never buffer until completion
- Tailwind utility classes only — no arbitrary values (`mt-[13px]`, `w-[347px]`)
- Component filenames PascalCase (`ChatMessage.tsx`); hook filenames camelCase (`useThreadList.ts`)
- Named exports for all components; default export only for page-level components

---

## Artifact Paths (Agent Handoff Convention)

| Stage | File Location |
|-------|--------------|
| Feature Specification | `.github/specs/<feature-name>.md` |
| Spec Validation Report | `.github/specs/<feature-name>-validation.md` |
| Technical Architecture Document | `.github/specs/<feature-name>-tad.md` |

These paths are the expected handoff points between agents. Each agent should save its output to the appropriate location and read its input from the previous stage's location.
