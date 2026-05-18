# Feature Specification: Conversational Memory (Rolling Window k=5)

## 1. Overview

Enhance the existing chat backend so that each LLM call receives the last 5 conversation turns (user + assistant message pairs) for its thread rather than a raw 20-message slice. The rolling window is managed by a `ThreadMemory` utility class that wraps `ConversationBufferWindowMemory(k=5)`, fetches the correct messages from PostgreSQL, populates the LangChain memory object, and returns a trimmed `list[BaseMessage]` ready for injection into the LCEL chain prompt. No new database tables, migrations, API routes, or frontend changes are required.

---

## 2. User Stories

- As a user, I want the AI to remember what I said in the last 5 exchanges within a thread so that my conversation feels coherent and context-aware.
- As a developer, I want memory management to be encapsulated in its own module so that the window size and memory strategy can be changed in one place.

---

## 3. Scope

### In Scope
- `ThreadMemory` utility class in `backend/app/ai/memory/conversation.py`
- `load_history` replaced by `ThreadMemory.load()` as the canonical interface
- `chat_service.py` updated to use `ThreadMemory.load()`
- Window size `k=5` (5 human+AI turn pairs = up to 10 messages) configurable via a module-level constant

### Out of Scope
- Persistent in-process memory store — memory is always fetched fresh from DB per request (per AD-05)
- Summarisation or long-term memory beyond the rolling window
- Frontend changes — API contract is unchanged
- New database tables or Alembic migrations — the `messages` table already stores everything needed

---

## 4. Data Model Changes

### New Tables
None. The `messages` table already holds `thread_id`, `role`, `content`, and `created_at` with the correct indexes.

### Migration Plan
No migration required. This feature is a pure service-layer change.

---

## 5. API Contract

### Unchanged Routes
No new or modified endpoints. The existing `POST /{thread_id}/chat` and `GET /{thread_id}/messages` routes are unaffected.

### Pydantic Schemas
No schema changes required.

---

## 6. Service Layer

### 6.1 `ThreadMemory` — `backend/app/ai/memory/conversation.py`

Replace the existing module with the following design:

**Module-level constant:**
```python
MEMORY_WINDOW_K: int = 5  # number of human+AI turn pairs to retain
```

**Class: `ThreadMemory`**

```python
class ThreadMemory:
    def __init__(self, k: int = MEMORY_WINDOW_K) -> None:
        self.k = k

    async def load(
        self, thread_id: uuid.UUID, db: AsyncSession
    ) -> list[BaseMessage]:
        ...
```

**`ThreadMemory.load` — step-by-step logic:**

1. Query the `messages` table for rows matching `thread_id`, ordered by `created_at DESC`, limited to `k * 2` rows (5 pairs = 10 messages). Reverse the result set to restore chronological order.
2. Instantiate a fresh `ConversationBufferWindowMemory(k=self.k, return_messages=True)`.
3. Iterate over the fetched messages in chronological pairs. For each consecutive `(user_msg, assistant_msg)` pair, call `memory.save_context({"input": user_msg.content}, {"output": assistant_msg.content})`.
   - If the final fetched message is a user message with no following assistant message (mid-turn edge case), skip it — it will be re-injected by the chain as `human_input`.
4. Return `memory.buffer_as_messages` — this is the trimmed `list[BaseMessage]` (at most `k * 2` messages) safe for injection into the prompt's `MessagesPlaceholder`.

**DB query (SQLAlchemy 2.0 style):**
```python
result = await db.execute(
    select(Message)
    .where(Message.thread_id == thread_id)
    .order_by(Message.created_at.desc())
    .limit(self.k * 2)
)
rows = list(reversed(result.scalars().all()))
```

**Module-level singleton** (used by `chat_service.py`):
```python
thread_memory = ThreadMemory(k=MEMORY_WINDOW_K)
```

**Backward-compatibility shim** (keep `load_history` so any future callers are not silently broken — delegates to the singleton):
```python
async def load_history(thread_id: str, db: AsyncSession) -> list[BaseMessage]:
    return await thread_memory.load(uuid.UUID(thread_id), db)
```

---

### 6.2 `stream_chat_response` — `backend/app/services/chat_service.py`

**Updated import block** — replace the bare `load_history` import with `ThreadMemory`:
```python
from app.ai.memory.conversation import thread_memory
```

**Updated history loading inside `stream_chat_response`** — replace the existing two lines that call `load_history` and trim the last message:

*Before:*
```python
history = await load_history(str(thread.id), db)
if history and getattr(history[-1], "content", None) == user_message:
    history = history[:-1]
```

*After:*
```python
history = await thread_memory.load(thread.id, db)
```

The trim guard is no longer needed because `ThreadMemory.load` fetches messages **before** the current user message is saved, and the DB query is bounded to `k * 2` rows by the memory window — it will not inadvertently include the just-saved message as long as the call order (save → load) is preserved. The existing `chat_service.py` already saves the user message first, then loads history — this order must be maintained.

> **Important:** Keep `_save_message` calls and the `thread.updated_at` commit exactly as they are today. `ThreadMemory.load` does not write to the DB; it is read-only.

---

## 7. AI Integration

### Chain
No change to `backend/app/ai/chains/chat_chain.py`. The `MessagesPlaceholder(variable_name="history")` slot already accepts the `list[BaseMessage]` that `ThreadMemory.load` returns.

### Prompt
No change to `backend/app/ai/prompts/chat_system.txt`. The system prompt is unchanged.

### Streaming
Unchanged — `chat_chain.astream({"human_input": ..., "history": history})` is the existing call site; only the `history` value changes (from ≤20 messages to ≤10 messages).

### Model
`settings.LLM_MODEL` — no hardcoding.

---

## 8. Frontend Changes

None. The streaming API response is identical. No new components, hooks, or types are required.

---

## 9. File Change Checklist

| File | Action | Notes |
|------|--------|-------|
| `backend/app/ai/memory/conversation.py` | **Modify** | Add `MEMORY_WINDOW_K`, `ThreadMemory` class, module-level `thread_memory` singleton; replace `load_history` body with shim delegating to singleton |
| `backend/app/services/chat_service.py` | **Modify** | Import `thread_memory` instead of `load_history`; replace `load_history(...)` call + trim guard with `await thread_memory.load(thread.id, db)` |

All other files are unchanged.

---

## 10. Security Checklist

- [x] All routes use `Depends(get_current_user)` — no change, ownership check via `get_thread` is unchanged
- [x] No file uploads involved
- [x] No NL-to-SQL involved
- [x] No secrets hardcoded — window size is a module constant, not an env var
- [x] No file content stored as DB blob
- [x] JWT never in localStorage or response body — auth layer is untouched

---

## 11. Test Plan

### Backend Unit Tests — `tests/test_conversation_memory.py`

| Test | Description |
|------|-------------|
| `test_load_returns_empty_for_new_thread` | No messages in DB → `thread_memory.load()` returns `[]` |
| `test_load_returns_at_most_k_pairs` | Insert 8 message pairs (16 messages) → `load` returns exactly 10 messages (k=5 pairs) |
| `test_load_respects_chronological_order` | Oldest messages are dropped, most-recent 5 pairs are returned in chronological order |
| `test_load_handles_unpaired_trailing_user_message` | Odd number of messages (last is user with no assistant reply) → trailing user message excluded from returned history |
| `test_load_history_shim` | `load_history(str(thread_id), db)` returns same result as `thread_memory.load(uuid, db)` |
| `test_custom_k` | `ThreadMemory(k=2).load(...)` with 4 message pairs → returns 4 messages (2 pairs) |

### Backend Integration Tests — `tests/test_chat_routes.py` (additions)

| Test | Description |
|------|-------------|
| `test_chat_uses_memory_window` | After 7 exchanges, the 8th LLM call receives history of at most 10 messages (mock `chat_chain.astream`, assert `history` arg length ≤ 10) |
| `test_memory_is_thread_scoped` | Two threads with different messages; `thread_memory.load` for thread A does not return messages from thread B |

### Mocking
- Mock `chat_chain.astream` — no real LiteLLM calls in CI
- Use in-memory SQLite or a test-scoped PostgreSQL fixture (per existing `pytest-asyncio` setup)

---

## 12. Open Questions

| # | Question | Impact |
|---|----------|--------|
| 1 | Should `MEMORY_WINDOW_K` be promoted to an env var (`MEMORY_WINDOW_K=5` in `.env`) for runtime tuning without a deploy? | Low — easy addition to `config.py` if needed |
| 2 | The current `load_history` limit is 20 messages. Should the `load_history` shim document the new effective limit (10) in its docstring to avoid confusion for future callers? | Documentation only |
| 3 | If a thread has only assistant messages (e.g. from a future system-generated thread), should the memory loader skip unpaired assistant messages or include them as `AIMessage`? Current spec skips them for pairing consistency. | Edge case — decision needed if system-generated messages are a future use case |
