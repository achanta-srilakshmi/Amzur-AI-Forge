# Agent Contracts — I/O Specifications

Every agent has a clear input/output contract. This document is the single source of truth for what each agent reads, writes, and assumes about its environment.

---

## Contract Template

```
## Agent: <Name>

### Purpose
[One sentence describing the agent's single responsibility]

### Preconditions (Agent assumes these are true)
- [ ] <Condition 1>
- [ ] <Condition 2>

### Inputs

#### Files Read
| File | Purpose | Required? |
|------|---------|-----------|
| `.github/agents/PLATFORM-RULES.md` | Platform rules and conventions | Yes |
| <other files> | ... | ... |

#### Auto-Detection (Folder Scanning)
```python
glob("backend/app/models/*.py")  # → extract all table names, relationships
glob("backend/app/services/*.py") # → extract service patterns
# etc.
```

#### User Input
| Parameter | Format | Required? |
|-----------|--------|-----------|
| Feature name | `kebab-case` | Yes |
| Feature description | Markdown | No (defaults to reading previous output) |

### Processing

[High-level processing steps]

### Outputs

#### Files Written
| File | Format | Purpose |
|------|--------|---------|
| `.github/specs/<feature>/feature.md` | Markdown | Human-readable specification |
| `.github/specs/<feature>/.progress.json` | JSON | Machine-readable progress record |

#### Output Format
- **Markdown (.md):** Human-readable documentation with sections, examples, tables
- **JSON (.json):** Structured data for machine parsing; includes timestamp, status, metrics

#### State Changes
- Updates `.progress.json` with new stage, status, and timestamp
- May set blockers/warnings/suggestions for human review

### Postconditions (Agent guarantees these are true on success)
- [ ] <Condition 1>
- [ ] <Condition 2>

### Error Handling
| Error | Action |
|-------|--------|
| `<error type>` | `<how agent handles it>` |

### Dependencies
- Reads from: <list of agents/files>
- Writes for: <list of agents>
```

---

## 1. Specification Agent

### Purpose
Generate a complete, implementation-ready Feature Specification by auto-discovering existing code patterns.

### Preconditions
- Feature name provided (or user is ready to describe feature)
- Codebase exists (`backend/` and `frontend/` folders readable)
- `PLATFORM-RULES.md` exists

### Inputs

#### Files Read
| File | Purpose | Required? |
|------|---------|-----------|
| `.github/agents/PLATFORM-RULES.md` | Compliance rules | Yes |
| `.github/agents/EXECUTION-FLOW.md` | Understanding full pipeline | No (for context) |
| `backend/app/core/config.py` | Existing settings | Yes |
| `backend/app/ai/llm.py` | AI layer setup | Yes (if AI feature) |
| `backend/app/models/*.py` | Existing table patterns | Yes |
| `backend/app/schemas/*.py` | Existing Pydantic patterns | Yes |
| `backend/app/services/*.py` | Existing service patterns | Yes |
| `backend/app/api/*.py` | Existing router patterns | Yes |
| `frontend/src/lib/api.ts` | API client pattern | Yes |
| `frontend/src/types/index.ts` | Type pattern | Yes |
| `frontend/src/hooks/*.ts` | Hook patterns | Yes |
| `frontend/src/components/**/*.tsx` | Component patterns | Yes |
| `backend/alembic/versions/` | Latest migration (parent revision) | Yes |

#### Auto-Detection
```python
# Scan for patterns to match style and conventions
glob("backend/app/models/*.py")     # → study UUID PK, FK, DateTime patterns
glob("backend/app/schemas/*.py")    # → study request/response shape
glob("backend/app/services/*.py")   # → study function signatures
glob("backend/app/api/*.py")        # → study route decorators, dependencies
glob("frontend/src/hooks/*.ts")     # → study React Query patterns
glob("frontend/src/components/**/*.tsx") # → study component hierarchy
```

#### User Input
| Parameter | Format | Example |
|-----------|--------|---------|
| Feature name | `kebab-case` | `document-qa` |
| Feature description | Markdown or plain text | "Users can upload PDFs and ask questions" |

### Processing
1. Read `PLATFORM-RULES.md`
2. Auto-scan backend and frontend for existing patterns
3. Read latest Alembic migration to determine parent revision
4. Interview user: clarify scope, data model, API endpoints, frontend needs
5. Write Feature Specification with all 10 sections populated
6. Validate specification against `PLATFORM-RULES.md` rules (V1–V6 self-check)

### Outputs

#### Files Written
| File | Format | Purpose |
|------|--------|---------|
| `.github/specs/<feature>/feature.md` | Markdown | Complete Feature Specification |
| `.github/specs/<feature>/.progress.json` | JSON | Progress tracking initialized |

#### JSON Schema (.progress.json)
```json
{
  "feature": "document-qa",
  "created_at": "2026-05-15T10:30:00Z",
  "stage": "SPECIFICATION",
  "status": "READY_FOR_VALIDATION",
  "stages": {
    "specification": {
      "timestamp": "2026-05-15T10:30:00Z",
      "status": "READY_FOR_VALIDATION",
      "file": "feature.md"
    },
    "validation": { "status": "PENDING" },
    "architect": { "status": "PENDING" },
    "engineer": { "status": "PENDING" },
    "qa": { "status": "PENDING" },
    "reviewer": { "status": "PENDING" }
  }
}
```

#### Markdown Sections (feature.md)
- Overview & User Stories
- Scope (In/Out)
- Data Model Changes (or "No DB changes")
- API Contract (endpoints, schemas)
- Service Layer (function signatures)
- AI Integration (if applicable)
- Frontend Changes (components, hooks, types)
- File Change Checklist
- Security Checklist
- Test Plan
- Open Questions

### Postconditions
- ✓ `.github/specs/<feature>/feature.md` exists and is complete
- ✓ `.github/specs/<feature>/.progress.json` exists with `status: "READY_FOR_VALIDATION"`
- ✓ All schema fields have explicit types (no `Any`)
- ✓ All endpoints have `response_model` declared
- ✓ All AI calls include `user=current_user.email`
- ✓ No hardcoded model names or URLs

### Error Handling
| Error | Action |
|-------|--------|
| Codebase not readable | Fail with clear message: "Cannot read backend/app/ — is the project path correct?" |
| PLATFORM-RULES.md missing | Fail with message: "Copy PLATFORM-RULES.md to .github/agents/" |
| Feature already exists | Warn: "`.github/specs/<feature>/.progress.json` exists. Overwrite? (y/n)" |
| Invalid feature name | Fail: "Feature name must be kebab-case (e.g., document-qa)" |

### Dependencies
- Reads from: None (first agent in pipeline)
- Writes for: Spec Validation Agent

---

## 2. Spec Validation Agent

### Purpose
Validate Feature Specification for internal consistency and codebase compatibility without modifying files.

### Preconditions
- `.github/specs/<feature>/feature.md` exists
- `.github/specs/<feature>/.progress.json` exists with `stage: "SPECIFICATION"` and `status: "APPROVED"`
- `PLATFORM-RULES.md` exists
- Codebase is readable

### Inputs

#### Files Read
| File | Purpose | Required? |
|------|---------|-----------|
| `.github/specs/<feature>/feature.md` | Specification to validate | Yes |
| `.github/specs/<feature>/.progress.json` | Stage and status check | Yes |
| `.github/agents/PLATFORM-RULES.md` | Validation rules | Yes |
| `backend/app/models/__init__.py` | Current table names | Yes |
| `backend/app/api/*.py` | Current route prefixes | Yes |
| `backend/app/schemas/*.py` | Current schema class names | Yes |
| `backend/app/core/config.py` | Current settings fields | Yes |
| `backend/app/ai/llm.py` | Available AI singletons | Yes |
| `frontend/src/lib/api.ts` | Existing API functions | Yes |
| `frontend/src/hooks/*.ts` | Existing hook names | Yes |
| `backend/alembic/versions/` | Latest migration ID | Yes |

#### Auto-Detection
```python
grep("__tablename__", glob("backend/app/models/*.py"))  # → all table names
grep("prefix=", glob("backend/app/api/*.py"))           # → all prefixes
grep("class.*BaseModel", glob("backend/app/schemas/*.py")) # → schema names
```

#### User Input
None — fully automated once spec.md exists and `.progress.json` is "APPROVED"

### Processing
1. Read `.progress.json` — verify `status == "APPROVED"`
2. Read `PLATFORM-RULES.md`
3. Scan codebase for existing names, prefixes, settings
4. Run 15 validation checks (V1–V15) from PLATFORM-RULES
5. Fail fast on first FAIL-level check
6. Write validation report

### Outputs

#### Files Written
| File | Format | Purpose |
|------|--------|---------|
| `.github/specs/<feature>/feature-validation.md` | Markdown | Validation report (PASS/FAIL/WARN per check) |
| `.github/specs/<feature>/.progress.json` | JSON | Update status |

#### JSON Update (.progress.json)
```json
{
  "stage": "VALIDATION",
  "status": "READY_FOR_ARCHITECT",  // or "BLOCKED"
  "stages": {
    "validation": {
      "timestamp": "2026-05-15T10:35:00Z",
      "status": "READY_FOR_ARCHITECT",
      "file": "feature-validation.md",
      "checks_passed": 15,
      "checks_failed": 0
    }
  }
}
```

#### Markdown Sections (feature-validation.md)
- Summary table (V1–V15 status)
- Failures (if any)
  - F1 — <Title>: Problem, Evidence, Fix, Rule violated
  - F2 — ...
- Warnings (if any)
- Overall Status: **VALID** or **INVALID — Fix Before Proceeding**

### Postconditions
- ✓ `.github/specs/<feature>/feature-validation.md` exists
- ✓ `.github/specs/<feature>/.progress.json` updated with validation timestamp
- ✓ If VALID: `status: "READY_FOR_ARCHITECT"`
- ✓ If INVALID: `status: "BLOCKED", failures: [...]` listed

### Error Handling
| Error | Action |
|-------|--------|
| `.progress.json` missing | Fail: "Run Specification Agent first to create .progress.json" |
| `status != "APPROVED"` | Fail: "Spec not approved yet. Current status: <status>" |
| `feature.md` incomplete | Fail: "Spec sections missing: <list>. Return to Specification Agent." |

### Dependencies
- Reads from: Specification Agent (feature.md, .progress.json)
- Writes for: Architect Agent or Specification Agent (if INVALID)

---

## 3. Architect Agent

### Purpose
Transform validated specification into concrete Technical Architecture Document with copy-paste-ready code examples.

### Preconditions
- `.github/specs/<feature>/feature.md` exists and is complete
- `.github/specs/<feature>/feature-validation.md` exists with "VALID" status
- `.github/specs/<feature>/.progress.json` exists with `stage: "VALIDATION"` and `status: "APPROVED"`
- `PLATFORM-RULES.md` exists

### Inputs

#### Files Read
| File | Purpose | Required? |
|------|---------|-----------|
| `.github/specs/<feature>/feature.md` | Specification to architect | Yes |
| `.github/specs/<feature>/feature-validation.md` | Validation results | Yes (for context) |
| `.github/specs/<feature>/.progress.json` | Stage and status check | Yes |
| `.github/agents/PLATFORM-RULES.md` | Design rules | Yes |
| `backend/app/main.py` | Router registration pattern | Yes |
| `backend/app/db/session.py` | Session factory pattern | Yes |
| `backend/app/core/config.py` | Settings pattern | Yes |
| `backend/app/ai/llm.py` | LLM singletons pattern | Yes |
| `backend/app/models/*.py` | ORM patterns | Yes |
| `backend/app/services/*.py` | Service function patterns | Yes |
| `backend/app/api/*.py` | Router patterns | Yes |
| `frontend/src/lib/api.ts` | API function pattern | Yes |
| `frontend/src/hooks/*.ts` | React Query hook pattern | Yes |
| `backend/requirements.txt` | Installed packages | Yes |
| `frontend/package.json` | Installed packages | Yes |

#### Auto-Detection
```python
# Read existing TADs for related features
glob(".github/specs/*/feature-tad.md") # → extract patterns, decisions
```

#### User Input
None — fully automated once validation passes

### Processing
1. Read `.progress.json` — verify `status == "APPROVED"` at VALIDATION stage
2. Read `PLATFORM-RULES.md`
3. Discover backend and frontend architecture from live codebase
4. Read related TADs (if exist) to extract architectural patterns
5. Write TAD with:
   - Component diagram (ASCII/Mermaid)
   - Exact file-by-file list (new + modify)
   - SQLAlchemy 2.0 model definition (copy-paste ready)
   - Service function signatures (copy-paste ready)
   - Router definition (copy-paste ready)
   - LCEL chain design (if AI)
   - Frontend component tree + API client + hook (copy-paste ready)
   - New dependencies (backend + frontend)
   - Security architecture
   - Numbered implementation order

### Outputs

#### Files Written
| File | Format | Purpose |
|------|--------|---------|
| `.github/specs/<feature>/feature-tad.md` | Markdown | Technical Architecture Document |
| `.github/specs/<feature>/.progress.json` | JSON | Update status |

#### JSON Update (.progress.json)
```json
{
  "stage": "ARCHITECT",
  "status": "READY_FOR_REVIEW",
  "stages": {
    "architect": {
      "timestamp": "2026-05-15T10:45:00Z",
      "status": "READY_FOR_REVIEW",
      "file": "feature-tad.md"
    }
  }
}
```

#### Markdown Sections (feature-tad.md)
1. Architecture Overview (diagram + 1-paragraph description)
2. Backend Architecture
   - 2.1 New Files (table of files to create)
   - 2.2 Files to Modify (table + changes)
   - 2.3 Database Design (SQLAlchemy 2.0 model + indexes)
   - 2.4 Service Layer Design (function signatures + step-by-step logic)
   - 2.5 Router Design (route handlers with Depends())
   - 2.6 AI Chain Design (LCEL syntax, prompt path, user tracking)
3. Frontend Architecture
   - 3.1 New Files
   - 3.2 Component Tree
   - 3.3 State Management (TanStack Query keys)
   - 3.4 API Client and Types
   - 3.5 Streaming (if applicable)
4. New Dependencies (backend + frontend)
5. Security Architecture
6. Implementation Order (numbered)

### Postconditions
- ✓ `.github/specs/<feature>/feature-tad.md` exists and is complete
- ✓ `.github/specs/<feature>/.progress.json` updated to `status: "READY_FOR_REVIEW"`
- ✓ All code examples are copy-paste ready
- ✓ All code examples comply with `PLATFORM-RULES.md`

### Error Handling
| Error | Action |
|-------|--------|
| Validation status not "APPROVED" | Fail: "Spec validation must be approved first" |
| Codebase patterns unreadable | Fail: "Cannot read existing code patterns. Check path permissions." |
| Spec sections missing | Fail: "Incomplete spec. Return to Specification Agent." |

### Dependencies
- Reads from: Spec Validation Agent (feature-validation.md, .progress.json)
- Writes for: Engineer Agent

---

## 4. Engineer Agent

### Purpose
Implement all files end-to-end in strict order, ensuring imports resolve and routers are registered.

### Preconditions
- `.github/specs/<feature>/feature-tad.md` exists
- `.github/specs/<feature>/.progress.json` exists with `stage: "ARCHITECT"` and `status: "APPROVED"`
- `PLATFORM-RULES.md` exists
- Project writable (`backend/`, `frontend/` folders)

### Inputs

#### Files Read
| File | Purpose | Required? |
|------|---------|-----------|
| `.github/specs/<feature>/feature-tad.md` | Implementation blueprint | Yes |
| `.github/specs/<feature>/.progress.json` | Stage and status check | Yes |
| `.github/agents/PLATFORM-RULES.md` | Compliance rules | Yes |
| `backend/app/models/*.py` | Style matching (UUID, FK pattern) | Yes |
| `backend/app/schemas/*.py` | Style matching (Pydantic) | Yes |
| `backend/app/services/*.py` | Style matching (function signatures) | Yes |
| `backend/app/api/*.py` | Style matching (routers) | Yes |
| `frontend/src/hooks/*.ts` | Style matching (React Query) | Yes |
| `frontend/src/components/**/*.tsx` | Style matching (components) | Yes |

#### Auto-Detection
```python
# Read existing code to match style exactly
glob("backend/app/models/*.py")     # → study ORM pattern
glob("backend/app/services/*.py")   # → study service signature pattern
glob("backend/app/api/*.py")        # → study router pattern
glob("frontend/src/hooks/*.ts")     # → study hook pattern
glob("frontend/src/components/**/*.tsx") # → study component pattern
```

#### User Input
None — fully automated once TAD is approved

### Processing
1. Read `.progress.json` — verify `status == "APPROVED"` at ARCHITECT stage
2. Read `PLATFORM-RULES.md`
3. Auto-detect existing file patterns (imports, type hints, decorators)
4. Implement in strict order:
   1. `backend/app/core/config.py` (add settings)
   2. `backend/app/models/<feature>.py` + update `models/__init__.py`
   3. Generate Alembic migration (`alembic revision --autogenerate`)
   4. `backend/app/schemas/<feature>.py`
   5. `backend/app/ai/prompts/<feature>.txt` (if AI)
   6. `backend/app/ai/chains/<feature>_chain.py` (if AI)
   7. `backend/app/services/<feature>_service.py`
   8. `backend/app/api/<feature>.py`
   9. Update `backend/app/main.py` (register router)
   10. `frontend/src/types/index.ts` (add types)
   11. `frontend/src/lib/api.ts` (add functions)
   12. `frontend/src/hooks/use<Feature>.ts`
   13. `frontend/src/components/<folder>/<Component>.tsx`
5. Verify all imports resolve
6. Verify all routers registered
7. Write implementation summary

### Outputs

#### Files Written
| File | Format | Purpose |
|------|--------|---------|
| All implementation files | Python/TypeScript/TSX | Live implementation |
| `.github/specs/<feature>/feature-implementation.md` | Markdown | Implementation checklist + verification |
| `.github/specs/<feature>/.progress.json` | JSON | Update status |

#### JSON Update (.progress.json)
```json
{
  "stage": "ENGINEER",
  "status": "READY_FOR_TESTING",
  "stages": {
    "engineer": {
      "timestamp": "2026-05-15T11:20:00Z",
      "status": "READY_FOR_TESTING",
      "file": "feature-implementation.md",
      "files_created": 13,
      "files_modified": 3
    }
  }
}
```

#### Markdown Sections (feature-implementation.md)
- File-by-file checklist (✓ created, ✓ modified, ✓ verified)
- Imports resolution check (✓ all imports resolve)
- Router registration check (✓ main.py updated)
- Build verification (✓ no syntax errors)
- Migration status (✓ Alembic migration created)
- Ready for testing (✓ all green)

### Postconditions
- ✓ All implementation files exist
- ✓ All imports resolve
- ✓ All routers registered in `main.py`
- ✓ Alembic migration created
- ✓ `.progress.json` updated to `status: "READY_FOR_TESTING"`
- ✓ No hardcoded secrets, model names, or URLs

### Error Handling
| Error | Action |
|-------|--------|
| TAD status not "APPROVED" | Fail: "TAD must be approved first" |
| File already exists | Ask: "Overwrite <file>? This will replace existing code." |
| Import resolution fails | Fail: "Import error in <file>: <error message>. Fix and re-run." |
| Syntax error | Fail: "Syntax error in <file>: <error message>" |

### Dependencies
- Reads from: Architect Agent (feature-tad.md, .progress.json)
- Writes for: QA Agent

---

## 5. QA Agent

### Purpose
Generate and run complete test suite for implemented feature; fix all failures.

### Preconditions
- All implementation files exist
- `.github/specs/<feature>/.progress.json` exists with `stage: "ENGINEER"` and `status: "APPROVED"`
- `pytest` + `npm run test` available
- `PLATFORM-RULES.md` exists

### Inputs

#### Files Read
| File | Purpose | Required? |
|------|---------|-----------|
| `.github/specs/<feature>/feature-tad.md` | Test strategy | Yes |
| `.github/specs/<feature>/.progress.json` | Stage and status check | Yes |
| `.github/agents/PLATFORM-RULES.md` | Test rules | Yes |
| All implementation files (backend + frontend) | Source code to test | Yes |
| `backend/tests/test_*.py` | Test pattern matching | Yes |
| `frontend/src/**/*.test.tsx` | Test pattern matching | Yes |

#### Auto-Detection
```python
glob("backend/app/services/<feature>*.py")    # → what to test
glob("backend/app/api/<feature>*.py")         # → what to test
glob("frontend/src/hooks/use<Feature>.ts")    # → what to test
glob("frontend/src/components/**/*<Feature>*.tsx") # → what to test
glob("backend/tests/test_*.py")               # → test pattern
glob("frontend/src/**/*.test.tsx")            # → test pattern
```

#### User Input
None — fully automated

### Processing
1. Read `.progress.json` — verify `status == "APPROVED"` at ENGINEER stage
2. Read `PLATFORM-RULES.md`
3. Auto-detect implemented files
4. Generate test files:
   - `backend/tests/test_<feature>_service.py` (unit tests: success + not-found + isolation)
   - `backend/tests/test_<feature>_api.py` (integration tests: 200/201, 401, 404)
   - `backend/tests/test_<feature>_chain.py` (if AI: chain with mocked LLM)
   - `frontend/src/components/<folder>/<Component>.test.tsx` (render, interaction)
   - `frontend/src/hooks/use<Feature>.test.ts` (TanStack Query, API call)
5. Run `pytest backend/tests/test_<feature>*.py -v`
6. Run `npm run test -- src/**/<feature>*.test.tsx --reporter=verbose`
7. Fix all failures
8. Run until 100% passing
9. Write test summary

### Outputs

#### Files Written
| File | Format | Purpose |
|------|--------|---------|
| `backend/tests/test_<feature>_*.py` | Python | Test files (all passing) |
| `frontend/src/**/<feature>.test.tsx` | TypeScript | Test files (all passing) |
| `.github/specs/<feature>/feature-tests.md` | Markdown | Test summary + coverage report |
| `.github/specs/<feature>/.progress.json` | JSON | Update status |

#### JSON Update (.progress.json)
```json
{
  "stage": "QA",
  "status": "READY_FOR_REVIEW",
  "stages": {
    "qa": {
      "timestamp": "2026-05-15T11:45:00Z",
      "status": "READY_FOR_REVIEW",
      "file": "feature-tests.md",
      "tests_created": 47,
      "tests_passing": 47,
      "tests_failing": 0
    }
  }
}
```

#### Markdown Sections (feature-tests.md)
- Test Summary (total tests, passing, failing, coverage %)
- Backend Unit Tests (service functions tested)
- Backend Integration Tests (routes tested)
- Backend AI Tests (chains with mocked LLM)
- Frontend Component Tests (rendering + interaction)
- Frontend Hook Tests (API calls + query invalidation)
- Coverage Report (lines covered %)
- All Tests Passing (✓ 47/47)

### Postconditions
- ✓ All test files exist and are passing
- ✓ 100% of new code is covered by tests
- ✓ `.progress.json` updated to `status: "READY_FOR_REVIEW"`
- ✓ No real API calls in tests (all mocked)

### Error Handling
| Error | Action |
|-------|--------|
| Engineer status not "APPROVED" | Fail: "Engineer stage must be approved first" |
| Test fails | Run fix logic → update test → re-run until passing |
| Syntax error in test | Fail: "Test syntax error in <file>: <error>" |

### Dependencies
- Reads from: Engineer Agent (implementation files, .progress.json)
- Writes for: Reviewer Agent

---

## 6. Reviewer Agent

### Purpose
Review all implementation against platform rules and spec without modifying files (unless auto-fix is requested).

### Preconditions
- All implementation files exist
- All tests passing
- `.github/specs/<feature>/feature.md` exists (original spec)
- `.github/specs/<feature>/feature-tad.md` exists (architecture)
- `.github/specs/<feature>/.progress.json` exists with `stage: "QA"` and `status: "APPROVED"`
- `PLATFORM-RULES.md` exists

### Inputs

#### Files Read
| File | Purpose | Required? |
|------|---------|-----------|
| `.github/specs/<feature>/feature.md` | Original spec | Yes |
| `.github/specs/<feature>/feature-tad.md` | Architecture decisions | Yes |
| `.github/specs/<feature>/.progress.json` | Stage and status check | Yes |
| `.github/agents/PLATFORM-RULES.md` | Review criteria | Yes |
| All implementation files | Code to review | Yes |
| `backend/app/services/auth_service.py` | Convention baseline | Yes |
| `backend/app/api/auth.py` | Convention baseline | Yes |
| `backend/app/models/user.py` | Convention baseline | Yes |

#### Auto-Detection
```python
glob("backend/app/services/<feature>*.py")     # → review these
glob("backend/app/api/<feature>*.py")          # → review these
glob("frontend/src/hooks/use<Feature>.ts")     # → review these
glob("frontend/src/components/**/*<Feature>*.tsx") # → review these
```

#### User Input
Optional: `--fix` flag to auto-fix BLOCKER items

### Processing
1. Read `.progress.json` — verify `status == "APPROVED"` at QA stage
2. Read `PLATFORM-RULES.md`
3. Auto-detect all implementation files
4. Review checklist (Architecture, Database, API, Security, AI, Frontend, Testing)
5. Categorize findings: BLOCKER / WARNING / SUGGESTION
6. If `--fix` requested: apply auto-fixes to BLOCKERs
7. Write review report

### Outputs

#### Files Written
| File | Format | Purpose |
|------|--------|---------|
| `.github/specs/<feature>/feature-review.md` | Markdown | Review report |
| `.github/specs/<feature>/.progress.json` | JSON | Update status |
| Implementation files (if `--fix` used) | Python/TypeScript | Auto-fixed code |

#### JSON Update (.progress.json)
```json
{
  "stage": "REVIEWER",
  "status": "APPROVED_FOR_MERGE",  // or "BLOCKED"
  "stages": {
    "reviewer": {
      "timestamp": "2026-05-15T12:00:00Z",
      "status": "APPROVED_FOR_MERGE",
      "file": "feature-review.md",
      "blockers": 0,
      "warnings": 2,
      "suggestions": 3
    }
  }
}
```

#### Markdown Sections (feature-review.md)
- Overall Status: **APPROVED FOR MERGE** or **BLOCKED — Fix Before Merge**
- Summary Table (Architecture, Database, API, Security, AI, Frontend, Testing)
- BLOCKERs (if any)
  - B1 — <Title>: File, Problem, Code Found, Required Fix, Rule
  - B2 — ...
- WARNINGs (if any)
- SUGGESTIONs (if any)

### Postconditions
- ✓ `.github/specs/<feature>/feature-review.md` exists
- ✓ If BLOCKERs: `.progress.json` status is "BLOCKED"
- ✓ If clean: `.progress.json` status is "APPROVED_FOR_MERGE"
- ✓ If `--fix` used: all BLOCKER fixes applied to implementation files

### Error Handling
| Error | Action |
|-------|--------|
| QA status not "APPROVED" | Fail: "Tests must be approved first" |
| Implementation file not found | Fail: "Expected file not found: <file>. Engineer stage may be incomplete." |
| Auto-fix fails | Fail: "Cannot auto-fix <file>: <error>. Apply fix manually." |

### Dependencies
- Reads from: QA Agent (test files, .progress.json), Specification Agent (spec.md), Architect Agent (tad.md)
- Writes for: Git merge (final stage)

---

## Progress JSON Full Schema

```json
{
  "feature": "document-qa",
  "created_at": "2026-05-15T10:30:00Z",
  "updated_at": "2026-05-15T12:00:00Z",
  "stage": "REVIEWER",
  "status": "APPROVED_FOR_MERGE",
  "stages": {
    "specification": {
      "timestamp": "2026-05-15T10:30:00Z",
      "status": "APPROVED",
      "file": "feature.md",
      "notes": "Spec covers RAG, embeddings, citations"
    },
    "validation": {
      "timestamp": "2026-05-15T10:35:00Z",
      "status": "APPROVED",
      "file": "feature-validation.md",
      "checks_passed": 15,
      "checks_failed": 0
    },
    "architect": {
      "timestamp": "2026-05-15T10:45:00Z",
      "status": "APPROVED",
      "file": "feature-tad.md",
      "notes": "TAD includes LCEL chain for RAG, ChromaDB collection per user"
    },
    "engineer": {
      "timestamp": "2026-05-15T11:20:00Z",
      "status": "APPROVED",
      "file": "feature-implementation.md",
      "files_created": 13,
      "files_modified": 3,
      "migration_created": "8f7c6e5d4c3b_add_documents_table"
    },
    "qa": {
      "timestamp": "2026-05-15T11:45:00Z",
      "status": "APPROVED",
      "file": "feature-tests.md",
      "tests_created": 47,
      "tests_passing": 47,
      "tests_failing": 0,
      "coverage_percent": 95
    },
    "reviewer": {
      "timestamp": "2026-05-15T12:00:00Z",
      "status": "APPROVED_FOR_MERGE",
      "file": "feature-review.md",
      "blockers": 0,
      "warnings": 2,
      "suggestions": 3,
      "auto_fixes_applied": 0
    }
  },
  "milestones": [
    "spec_approved",
    "validation_passed",
    "tad_approved",
    "implementation_complete",
    "tests_passing",
    "review_clean"
  ]
}
```
