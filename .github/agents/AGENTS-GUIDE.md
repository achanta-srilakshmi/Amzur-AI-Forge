# Amzur AI Chat — Agent System Guide

## Overview

Six specialised VS Code Copilot agents work together to take a feature idea from raw requirement all the way to reviewed, tested, production-ready code. Each agent reads the live codebase before acting, so outputs always match actual project conventions.

**Key innovation:** Agents are fully autonomous and file-driven. They communicate via structured `.md` and `.json` files in `.github/specs/<feature>/`, requiring only human approval gates between stages.

---

## Autonomous Orchestration

Agents run **sequentially in a guaranteed pipeline**. Each agent:
1. **Auto-detects** inputs from previous stage's output files
2. **Processes** independently with no manual path input
3. **Writes** outputs to predefined `.github/specs/<feature>/` folder
4. **Updates** `.progress.json` with status and timestamp
5. **Pauses** for human approval (when required)
6. **Hands off** to next agent automatically (when status = "APPROVED")

See **[`EXECUTION-FLOW.md`](EXECUTION-FLOW.md)** for the complete sequential pipeline diagram.

---

## The 6 Agents

| # | Agent | File | Purpose |
|---|-------|------|---------|
| 1 | **Specification Agent** | `specification-agent.agent.md` | Turns a feature idea into a full implementation-ready spec |
| 2 | **Spec Validation Agent** | `spec-validation-agent.agent.md` | Validates the spec against the real codebase — catches conflicts before implementation |
| 3 | **Architect Agent** | `architect-agent.agent.md` | Turns the validated spec into a concrete Technical Architecture Document |
| 4 | **Engineer Agent** | `engineer-agent.agent.md` | Implements every file from the TAD end-to-end |
| 5 | **QA Agent** | `qa-agent.agent.md` | Generates and runs a complete test suite for the implemented feature |
| 6 | **Reviewer Agent** | `reviewer-agent.agent.md` | Reviews code against all platform conventions and security rules; can auto-fix |

---

## How to Invoke Agents

### Start a New Feature (Automatic Pipeline)
```
User: "Start feature: document-qa"
           ↓
[Specification Agent auto-runs]
[User reviews + approves]
           ↓
[Spec Validation Agent auto-runs]
[If valid, auto-proceeds; if invalid, flags for fix]
           ↓
[Architect Agent auto-runs]
[User reviews + approves]
           ↓
[Engineer Agent auto-runs]
[Writes all files automatically]
           ↓
[QA Agent auto-runs]
[Tests run to completion; if passing, auto-proceeds]
           ↓
[Reviewer Agent auto-runs]
[If clean, status = "APPROVED_FOR_MERGE"]
           ↓
Ready to merge!
```

**Key:** Agents run automatically once the previous stage is "APPROVED". No re-invocation needed.

### Invoke a Specific Agent (Manual Override)
If needed, you can invoke any agent directly:

1. Open the **Chat** panel (`Ctrl+Alt+I`)
2. Click the **agent selector** dropdown
3. Select agent by name — e.g., **Specification Agent**
4. Type your input and press Enter

Most agents will auto-detect their input from `.github/specs/` and proceed.

All agent files live in `.github/agents/` and VS Code Copilot discovers them automatically.

---

## Full Feature Pipeline

```
Feature Idea
     │
     ▼
[1] Specification Agent      →  .github/specs/<feature>.md
     │
     ▼
[2] Spec Validation Agent    →  .github/specs/<feature>-validation.md
     │        │
     │        └── INVALID? → back to [1] with failure list
     │
     ▼  VALID
[3] Architect Agent          →  .github/specs/<feature>-tad.md
     │
     ▼
[4] Engineer Agent           →  All implementation files written
     │
     ▼
[5] QA Agent                 →  Test files written + tests run
     │
     ▼
[6] Reviewer Agent           →  Review report; blockers auto-fixed
     │
     ▼
  Ready to merge
```

---

## Agent Reference

---

### 1. Specification Agent

**When to use:** You have a feature idea and need a complete spec before implementation.

**Example input:**
```
Feature: Document Q&A (RAG)

Description: Users upload PDFs and ask questions about their content.
The system embeds documents using text-embedding-3-large and retrieves
relevant chunks to answer with citations.
```

**What it does first (dynamic discovery):**
- Reads all existing models, schemas, services, routers
- Reads `config.py`, `llm.py`, latest Alembic migration
- Reads `api.ts`, `types/index.ts`, all hooks and components

**Output sections:**
1. Overview & User Stories
2. Data Model Changes (tables, columns, migration parent revision)
3. API Contract (endpoints + Pydantic schemas)
4. Service Layer (function signatures + logic)
5. AI Integration (chain design, prompt, streaming — if applicable)
6. Frontend Changes (components, hooks, API functions, types)
7. File Change Checklist
8. Security Checklist
9. Test Plan
10. Open Questions

---

### 2. Spec Validation Agent

**When to use:** You have a draft spec and want to verify it before implementation.

**Example input:**
```
Please validate this spec:

[paste the full Feature Specification here]
```

**What it checks (15 checks):**

| # | Check | Outcome |
|---|-------|---------|
| V1 | New table names don't conflict with existing | FAIL |
| V2 | UUID PKs, DateTime(timezone=True) on all timestamps | FAIL |
| V3 | New route prefixes don't conflict | FAIL |
| V4 | Pydantic class names don't shadow existing | WARN |
| V5 | All `settings.<FIELD>` refs exist in `config.py` | FAIL |
| V6 | No hardcoded AI model name strings | FAIL |
| V7 | TypeScript interfaces match backend response schemas | WARN |
| V8 | No duplicate API function names in `api.ts` | FAIL |
| V9 | No duplicate hook names | WARN |
| V10 | Alembic parent revision matches latest migration | FAIL |
| V11 | All required spec sections present | FAIL |
| V12 | Security checklist covers all applicable rules | FAIL |
| V13 | Test plan covers all required categories | WARN |
| V14 | No forbidden LangChain classes (`LLMChain` etc.) | FAIL |
| V15 | All AI call examples include user tracking | FAIL |

**Output:** Validation report with PASS/FAIL/WARN per check, detailed failure descriptions, and next steps.

**This agent never modifies any file.**

---

### 3. Architect Agent

**When to use:** Spec is validated. You need concrete technical decisions before coding.

**Example input:**
```
Here is the validated spec. Please produce the Technical Architecture Document.

[paste the Feature Specification]
```

**What it reads first:**
`main.py`, `db/session.py`, `config.py`, `llm.py`, all models, all routers, all AI chains, `App.tsx`, `api.ts`, `useChat.ts`, `requirements.txt`, `package.json`

**Output:**
- Architecture diagram
- Exact list of files to create / modify
- SQLAlchemy 2.0 model definition (copy-paste ready)
- Service function signatures with step-by-step logic
- Router definition (copy-paste ready)
- LCEL chain design (if AI feature)
- Frontend component tree, state design, API/type definitions
- New dependencies (backend + frontend)
- Security architecture
- Numbered implementation order

---

### 4. Engineer Agent

**When to use:** TAD is complete. Implement the feature.

**Example input (with TAD):**
```
Please implement this feature. Here is the TAD:

[paste the Technical Architecture Document]
```

**Example input (direct):**
```
Implement the prompt templates feature.
```

**Implementation order enforced:**
1. `config.py` additions
2. ORM model + `__init__.py`
3. Alembic migration
4. Pydantic schemas
5. Prompt template (if AI)
6. LCEL chain (if AI)
7. Service functions
8. Router + `main.py` registration
9. TypeScript types
10. API client functions
11. TanStack Query hook
12. React components

**Ends with** a post-implementation checklist confirming all imports resolve and all routers are registered.

---

### 5. QA Agent

**When to use:** Feature is implemented. Generate and run all tests.

**Example input:**
```
Generate and run tests for the document Q&A feature.
```

**Or with specific files:**
```
Generate tests for:
- backend/app/services/document_service.py
- backend/app/api/documents.py
- frontend/src/hooks/useDocuments.ts
```

**Output files:**
- `backend/tests/test_<feature>_service.py` — unit tests (success + not-found + isolation)
- `backend/tests/test_<feature>_api.py` — integration tests (201/200, 401, 404)
- `backend/tests/test_<feature>_chain.py` — chain tests with mocked LLM (if AI)
- `frontend/src/components/<folder>/<Component>.test.tsx` — component tests
- `frontend/src/hooks/use<Feature>.test.ts` — hook tests

**Then runs:** `pytest` + `npm run test` and fixes all failures.

---

### 6. Reviewer Agent

**When to use:** Feature is implemented. Review before merging.

**Example input (simple):**
```
Review the document Q&A feature.
```

**Example input (with spec):**
```
Review the document Q&A feature against this spec:
[paste spec]
```

**To apply fixes after review:**
```
Apply all the fixes from the review report.
```

**Review categories:**
| Category | What's Checked |
|----------|---------------|
| Architecture & Layering | No logic in routers, service is framework-agnostic |
| Database | SQLAlchemy 2.0, UUIDs, timezones, indexes, N+1 |
| API & Schemas | response_model, async, auth dependency, error format |
| Security | OWASP Top 10 + all project-specific rules |
| AI Layer | LCEL, llm.py singletons, user tracking, no hardcoding |
| Frontend | TanStack Query, strict TS, Tailwind, streaming pattern |
| Testing | Coverage, mocking, dependency_overrides.clear() |

**Output:** BLOCKER / WARNING / SUGGESTION report with exact file + code + required fix per finding.

---

## Example: Full Feature from Scratch

```
Step 1 — Specification Agent
"Build a feature where users can save and re-use prompt templates."

Step 2 — Spec Validation Agent
"Validate this spec: [paste output from step 1]"

Step 3 — Architect Agent
"Produce a TAD for this validated spec: [paste spec]"

Step 4 — Engineer Agent
"Implement this feature using the TAD: [paste TAD]"

Step 5 — QA Agent
"Generate and run tests for the prompt templates feature."

Step 6 — Reviewer Agent
"Review the prompt templates feature."
"Apply all fixes from the review."
```

## Example: Review and Fix Existing Code

```
Reviewer Agent:
"Review backend/app/services/chat_service.py and backend/app/api/chat.py"

(review report shows blockers)

"Apply all fixes from the review."
```

## Example: Tests Only

```
QA Agent:
"Generate tests for the RAG feature.
Files: backend/app/services/rag_service.py, backend/app/api/documents.py"
```

---

## Key Documentation

| File | Purpose |
|------|---------|
| [`PLATFORM-RULES.md`](PLATFORM-RULES.md) | **Single source of truth** for all platform rules. Every agent reads this first. |
| [`EXECUTION-FLOW.md`](EXECUTION-FLOW.md) | **Pipeline diagram** — 6 stages, approval gates, `.progress.json` contract. |
| [`AGENT-CONTRACTS.md`](AGENT-CONTRACTS.md) | **I/O specification** for each agent (inputs, outputs, auto-detection). |
| `AGENTS-GUIDE.md` | This file — quick reference for invoking agents. |

---

## Platform Rules

All platform conventions, security requirements, and non-negotiable rules are maintained in **[`PLATFORM-RULES.md`](PLATFORM-RULES.md)**. Every agent reads this file at the start of its discovery pass.

Categories covered: Architecture & Layering · Database · AI Layer · Authentication & Security · FastAPI Conventions · Pydantic Schemas · Frontend · Artifact Paths.

To update a rule, edit `PLATFORM-RULES.md` once — all agents pick it up automatically.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Agent produces generic code not matching project | Discovery pass skipped | Ask agent to "read existing patterns first" before generating |
| Spec validation fails V10 (wrong parent revision) | Spec written before latest migration | Update parent revision to match latest file in `alembic/versions/` |
| Tests fail `ModuleNotFoundError: psycopg2` | Missing package | Add `psycopg2-binary` to `requirements.txt` |
| Reviewer finds `LLMChain` in generated code | LCEL rule not followed | Run Reviewer Agent and apply fixes |
| `httpx.ConnectError: getaddrinfo failed` on AI calls | Not on Amzur VPN | Connect to VPN — `litellm.amzur.com` is internal only |
| `ModuleNotFoundError: No module named 'gspread'` | Separate from google-auth | Add `gspread` explicitly to `requirements.txt` |
