# Technical Architecture Document: Conversational Memory (Rolling Window k=5)

## 1. Architecture Overview

```
POST /{thread_id}/chat
        │
        ▼
  chat.py (router)
        │  Depends(get_current_user, get_db)
        ▼
  chat_service.stream_chat_response()
        │
        ├─── _save_message(user)            ← unchanged
        │
        ├─── thread_memory.load(thread.id, db)   ← NEW: replaces load_history()
        │         │
        │         └── SELECT messages WHERE thread_id=…
        │               ORDER BY created_at DESC LIMIT k*2
        │               → reversed → paired → ConversationBufferWindowMemory
        │               → returns list[BaseMessage] (≤10 messages)
        │
        ├─── chat_chain.astream({"human_input":…, "history": history})  ← unchanged
        │
        └─── _save_message(assistant)       ← unchanged
```

This is a pure service-layer change. No routers, schemas, models, migrations, or frontend files change.

---

## 2. Backend Architecture

### 2.1 New Files

None.

### 2.2 Files to Modify

| File Path | Change Required |
|-----------|----------------|
| `backend/app/ai/memory/conversation.py` | Full replacement — add `MEMORY_WINDOW_K`, `ThreadMemory` class, `thread_memory` singleton; convert `load_history` to backward-compat shim |
| `backend/app/services/chat_service.py` | Replace `load_history` import with `thread_memory`; replace history-loading block (2 lines → 1 line) |

### 2.3 Database Design

No changes. The `messages` table already has:
- `thread_id` — FK with `index=True`
- `created_at` — `DateTime(timezone=True)`
- `role` — `MessageRole` enum (`user` / `assistant`)

The new query uses `ORDER BY created_at DESC LIMIT k*2`, which hits the existing `thread_id` index efficiently.

### 2.4 Service Layer Design — `backend/app/ai/memory/conversation.py`

**Complete replacement of the current file:**

```python
"""Conversation memory — rolling window of the last k turn-pairs per thread."""
import uuid

from langchain.memory import ConversationBufferWindowMemory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageRole

# Number of human+AI turn pairs to retain in the context window.
# Increase to allow more history; decrease to reduce token usage.
MEMORY_WINDOW_K: int = 5


class ThreadMemory:
    """Fetches the last k turn-pairs for a thread and returns them as
    a list[BaseMessage] ready for injection into a MessagesPlaceholder."""

    def __init__(self, k: int = MEMORY_WINDOW_K) -> None:
        self.k = k

    async def load(
        self, thread_id: uuid.UUID, db: AsyncSession
    ) -> list[BaseMessage]:
        """Return at most k*2 messages (k pairs) in chronological order."""
        result = await db.execute(
            select(Message)
            .where(Message.thread_id == thread_id)
            .order_by(Message.created_at.desc())
            .limit(self.k * 2)
        )
        rows = list(reversed(result.scalars().all()))

        memory = ConversationBufferWindowMemory(k=self.k, return_messages=True)

        i = 0
        while i < len(rows) - 1:
            current = rows[i]
            nxt = rows[i + 1]
            if (
                current.role == MessageRole.user
                and nxt.role == MessageRole.assistant
            ):
                memory.save_context(
                    {"input": current.content},
                    {"output": nxt.content},
                )
                i += 2
            else:
                i += 1  # skip unpaired message

        return memory.buffer_as_messages  # type: ignore[return-value]


# Module-level singleton — import this in chat_service.py
thread_memory = ThreadMemory(k=MEMORY_WINDOW_K)


async def load_history(thread_id: str, db: AsyncSession) -> list[BaseMessage]:
    """Backward-compatibility shim. Delegates to thread_memory.load().
    Effective history limit is now MEMORY_WINDOW_K*2 messages (default 10),
    down from the previous hard-coded limit of 20."""
    return await thread_memory.load(uuid.UUID(thread_id), db)
```

**`ThreadMemory.load` — step-by-step logic:**

| Step | Detail |
|------|--------|
| 1 | `SELECT … WHERE thread_id = :id ORDER BY created_at DESC LIMIT k*2` — fetches the most-recent `k*2` rows |
| 2 | `reversed(…)` — restores chronological order |
| 3 | Instantiate a fresh `ConversationBufferWindowMemory(k=self.k, return_messages=True)` |
| 4 | Walk rows in a `while` loop; pair consecutive `(user, assistant)` rows via `memory.save_context`; skip any unpaired leading/trailing messages |
| 5 | Return `memory.buffer_as_messages` — a `list[BaseMessage]` of at most `k*2` messages |

**Error cases:** None — an empty DB result returns `[]` (the memory's `buffer_as_messages` is empty), which the chain handles correctly via `MessagesPlaceholder`.

### 2.5 Router Design

No changes to any router.

### 2.6 Service Layer Change — `backend/app/services/chat_service.py`

Two targeted edits only.

**Edit 1 — Import line:**

```python
# Before
from app.ai.memory.conversation import load_history

# After
from app.ai.memory.conversation import thread_memory
```

**Edit 2 — History-loading block inside `stream_chat_response`:**

```python
# Before
history = await load_history(str(thread.id), db)
if history and getattr(history[-1], "content", None) == user_message:
    history = history[:-1]

# After
history = await thread_memory.load(thread.id, db)
```

The trim guard is eliminated because `ThreadMemory.load` queries `DESC LIMIT k*2` **after** the user message is already committed, and pairs only `(user, assistant)` rows. A just-committed user message with no following assistant message is naturally skipped by the pairing loop (trailing unpaired user row).

**Call-order invariant preserved:** `_save_message(user)` → `db.commit()` → `thread_memory.load()` → `chat_chain.astream()` — identical to today.

### 2.7 AI Chain Design

No changes. `chat_chain.py`:
```python
chat_chain = prompt | llm | StrOutputParser()
```
The `MessagesPlaceholder(variable_name="history")` slot already accepts `list[BaseMessage]`. The value injected changes from ≤20 arbitrary messages to ≤10 paired messages, but the type and variable name are unchanged.

---

## 3. Frontend Architecture

No changes. The streaming SSE response is byte-for-byte identical. No new components, hooks, types, or API functions.

---

## 4. New Dependencies

### Backend

`langchain.memory.ConversationBufferWindowMemory` ships inside the `langchain` package, which is already pinned as `langchain>=0.3` in `requirements.txt`.

| Package | Already in `requirements.txt`? | Action |
|---------|--------------------------------|--------|
| `langchain>=0.3` | Yes | No change |

No new packages needed.

### Frontend

None.

---

## 5. Security Architecture

| Concern | Decision |
|---------|----------|
| Auth boundary | Unchanged — `stream_chat_response` is called only after `Depends(get_current_user)` + `get_thread` ownership check in the router |
| Per-user data isolation | `ThreadMemory.load` queries `WHERE thread_id = :id`; thread ownership is already validated upstream — no cross-thread leakage possible |
| Input validation | `thread_id` is a validated `uuid.UUID` parameter; passed directly as a typed SQLAlchemy bind — no string interpolation, no injection vector |
| DB access | Read-only — `ThreadMemory.load` issues only `SELECT`; no `INSERT/UPDATE/DELETE` |
| Token budget | Window capped at `k*2 = 10` messages — reduces prompt token risk relative to the previous 20-message ceiling |

---

## 6. Implementation Order

| Step | Action | File |
|------|--------|------|
| 1 | Replace `conversation.py` with `ThreadMemory` class, `thread_memory` singleton, and `load_history` shim | `backend/app/ai/memory/conversation.py` |
| 2 | Update import: `load_history` → `thread_memory` | `backend/app/services/chat_service.py` |
| 3 | Replace 2-line history-loading block with single `await thread_memory.load(thread.id, db)` | `backend/app/services/chat_service.py` |

No migration, no dependency install, no config change, no frontend change required. Steps 2 and 3 are in the same file and should be applied together.

---

## Engineer Agent Handover

Switch to the **Engineer Agent** and paste:

```
Implement this feature using the TAD below.

[paste contents of this file]
```
