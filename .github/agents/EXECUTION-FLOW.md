# Execution Flow — Sequential Agent Pipeline

This document describes how agents execute in sequence, with file-based communication and approval gates between each stage.

---

## Feature Artifact Lifecycle

```
.github/specs/<feature>/
├── feature.md                   # Step 1: Specification Agent output
├── feature-validation.md        # Step 2: Spec Validation Agent output
├── feature-tad.md               # Step 3: Architect Agent output
├── feature-implementation.md    # Step 4: Engineer Agent output
├── feature-tests.md             # Step 5: QA Agent output
├── feature-review.md            # Step 6: Reviewer Agent output
└── .progress.json               # Tracks current stage (SPECIFICATION → ARCHITECT → APPROVED)
```

All markdown files are human-readable documentation.
The `.progress.json` file is the handoff contract — each agent reads this to determine its input and what stage to run.

---

## Stage 1: Specification

**Input:**
- User provides feature name and description (or reads from `.github/issue-template.md`)
- Agent auto-detects codebase from `backend/` and `frontend/` folders

**Process:**
- Read `.github/agents/PLATFORM-RULES.md`
- Discover existing models, schemas, services, routes, hooks, components
- Write `.github/specs/<feature>/feature.md`

**Output:**
- `.github/specs/<feature>/feature.md` — complete Feature Specification
- `.github/specs/<feature>/.progress.json` with `{"stage": "SPECIFICATION", "status": "READY_FOR_VALIDATION"}`

**Gate:** Human reviews spec. If approved, update `.progress.json` to `status: "APPROVED"`.

---

## Stage 2: Spec Validation

**Input:**
- Reads `.github/specs/<feature>/feature.md`
- Reads `.github/specs/<feature>/.progress.json` — confirms `stage == "SPECIFICATION"` and `status == "APPROVED"`

**Process:**
- Read `.github/agents/PLATFORM-RULES.md`
- Run 15 validation checks (V1–V15)
- Fail fast: stop if any FAIL check is encountered
- Write `.github/specs/<feature>/feature-validation.md`

**Output:**
- `.github/specs/<feature>/feature-validation.md` — validation report (VALID or INVALID + failures)
- If VALID: update `.progress.json` to `{"stage": "VALIDATION", "status": "READY_FOR_ARCHITECT"}`
- If INVALID: update `.progress.json` to `{"stage": "VALIDATION", "status": "BLOCKED", "failures": [...]}`

**Gate:** If INVALID, user fixes spec and re-runs Specification Agent. If VALID, human approves → update status to "APPROVED".

---

## Stage 3: Architecture

**Input:**
- Reads `.github/specs/<feature>/feature.md`
- Reads `.github/specs/<feature>/feature-validation.md` — confirms validation passed
- Reads `.github/specs/<feature>/.progress.json` — confirms `status == "APPROVED"`

**Process:**
- Read `.github/agents/PLATFORM-RULES.md`
- Discover existing architecture from `backend/app/main.py`, models, services, routers, `frontend/src/lib/api.ts`, etc.
- Write `.github/specs/<feature>/feature-tad.md`

**Output:**
- `.github/specs/<feature>/feature-tad.md` — Technical Architecture Document (copy-paste ready)
- Update `.progress.json` to `{"stage": "ARCHITECT", "status": "READY_FOR_REVIEW"}`

**Gate:** Human reviews TAD. If approved, update status to "APPROVED".

---

## Stage 4: Implementation

**Input:**
- Reads `.github/specs/<feature>/feature-tad.md`
- Reads `.github/specs/<feature>/.progress.json` — confirms `status == "APPROVED"` at ARCHITECT stage

**Process:**
- Read `.github/agents/PLATFORM-RULES.md`
- Auto-detect backend and frontend patterns from existing code
- Create/modify all files per TAD in strict order:
  1. `backend/app/core/config.py` (settings)
  2. `backend/app/models/<feature>.py` + `models/__init__.py`
  3. Alembic migration (auto-generated)
  4. `backend/app/schemas/<feature>.py`
  5. Prompt templates (if AI)
  6. LCEL chains (if AI)
  7. `backend/app/services/<feature>_service.py`
  8. `backend/app/api/<feature>.py`
  9. `backend/app/main.py` (register router)
  10. `frontend/src/types/index.ts` (add types)
  11. `frontend/src/lib/api.ts` (add functions)
  12. `frontend/src/hooks/use<Feature>.ts`
  13. `frontend/src/components/<folder>/<Component>.tsx`
- Write `.github/specs/<feature>/feature-implementation.md` (summary of changes)

**Output:**
- All implementation files (backend + frontend)
- `.github/specs/<feature>/feature-implementation.md` — file-by-file checklist + verification steps
- Update `.progress.json` to `{"stage": "ENGINEER", "status": "READY_FOR_TESTING"}`

**Gate:** Human verifies all files created and imports resolve. If any issues, fixes are applied manually or Engineer Agent re-runs. Update status to "APPROVED".

---

## Stage 5: Testing

**Input:**
- Reads `.github/specs/<feature>/feature-tad.md` (for test strategy)
- Reads `.github/specs/<feature>/.progress.json` — confirms `status == "APPROVED"` at ENGINEER stage
- Auto-detects implemented files from file system

**Process:**
- Read `.github/agents/PLATFORM-RULES.md`
- Discover all service functions, routes, components, hooks by scanning filesystem
- Generate test files:
  - `backend/tests/test_<feature>_service.py` (unit tests)
  - `backend/tests/test_<feature>_api.py` (integration tests)
  - `backend/tests/test_<feature>_chain.py` (if AI)
  - `frontend/src/components/<folder>/<Component>.test.tsx`
  - `frontend/src/hooks/use<Feature>.test.ts`
- Run `pytest` + `npm run test`
- Fix all failures
- Write `.github/specs/<feature>/feature-tests.md` (test summary + coverage report)

**Output:**
- All test files created and passing
- `.github/specs/<feature>/feature-tests.md` — test coverage report + pass/fail status
- Update `.progress.json` to `{"stage": "QA", "status": "READY_FOR_REVIEW"}`

**Gate:** Human confirms all tests pass. Update status to "APPROVED".

---

## Stage 6: Review

**Input:**
- Reads `.github/specs/<feature>/feature.md` (original spec)
- Reads `.github/specs/<feature>/feature-tad.md` (architecture decisions)
- Reads `.github/specs/<feature>/.progress.json` — confirms `status == "APPROVED"` at QA stage
- Auto-detects all implementation files

**Process:**
- Read `.github/agents/PLATFORM-RULES.md`
- Read convention baselines from `backend/app/services/auth_service.py`, `backend/app/api/auth.py`, etc.
- Run full review checklist (Architecture, Database, API, Security, AI, Frontend, Testing)
- Categorize findings: BLOCKER / WARNING / SUGGESTION
- Optionally apply auto-fixes to BLOCKER items
- Write `.github/specs/<feature>/feature-review.md`

**Output:**
- `.github/specs/<feature>/feature-review.md` — BLOCKER / WARNING / SUGGESTION report
- If any BLOCKERs: update `.progress.json` to `{"stage": "REVIEWER", "status": "BLOCKED", "blockers": [...]}`
- If clean: update `.progress.json` to `{"stage": "REVIEWER", "status": "APPROVED_FOR_MERGE"}`

**Gate:** If BLOCKERs exist, Engineer Agent re-runs to fix. If clean, feature is ready to merge.

---

## File-Based Auto-Detection

Each agent implements auto-detection to avoid asking the user for file paths:

### Specification Agent
```python
# Auto-detect existing patterns
glob("backend/app/models/*.py") → read each model
glob("backend/app/services/*.py") → read each service
glob("backend/app/schemas/*.py") → read each schema
glob("backend/app/api/*.py") → read each router
glob("frontend/src/hooks/*.ts") → read each hook
glob("frontend/src/components/**/*.tsx") → read component tree
read("backend/app/core/config.py")
read("backend/app/ai/llm.py")
read("frontend/src/lib/api.ts")
```

### Architect Agent
```python
# Auto-detect same baseline + find TAD candidates
if exists(".github/specs") → glob("*.tad.md") → extract related decisions
```

### Engineer Agent
```python
# Auto-detect existing file patterns to match style
glob("backend/app/models/*.py") → extract import style, type hints
glob("backend/app/services/*.py") → extract function signature pattern
glob("backend/app/api/*.py") → extract router pattern
glob("frontend/src/hooks/*.ts") → extract hook pattern
glob("frontend/src/components/**/*.tsx") → extract component pattern
```

### QA Agent
```python
# Auto-detect what was just implemented
glob("backend/app/services/<feature>*.py")
glob("backend/app/api/<feature>*.py")
glob("frontend/src/hooks/use<Feature>.ts")
glob("frontend/src/components/**/*<Feature>*.tsx")
```

### Reviewer Agent
```python
# Auto-detect all implementation files
# Read same baselines as Engineer Agent discovered
# Match against PLATFORM-RULES.md
```

---

## Progress JSON Schema

```json
{
  "feature": "document-qa",
  "created_at": "2026-05-15T10:30:00Z",
  "stage": "ENGINEER",
  "status": "APPROVED",
  "stages": {
    "specification": {
      "timestamp": "2026-05-15T10:30:00Z",
      "status": "APPROVED",
      "file": "feature.md"
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
      "file": "feature-tad.md"
    },
    "engineer": {
      "timestamp": "2026-05-15T11:20:00Z",
      "status": "APPROVED",
      "file": "feature-implementation.md",
      "files_created": 13,
      "files_modified": 3
    },
    "qa": {
      "timestamp": null,
      "status": "PENDING",
      "file": null
    },
    "reviewer": {
      "timestamp": null,
      "status": "PENDING",
      "file": null
    }
  },
  "blockers": [],
  "warnings": []
}
```

---

## User Approval Gates

Between each stage, the system pauses for human approval. Approval is recorded in `.progress.json`:

**Stage Complete:**
```
[Agent generates output file]
[Output saved to .github/specs/<feature>/<stage>.md]
[Progress updated: status = "READY_FOR_X"]
[System pauses and displays summary]
```

**User Action:**
```
Human reviews output in editor
If OK: 
  - Inline comment or confirmation: "Approved"
  - System updates .progress.json: status = "APPROVED"
  - Next agent auto-starts (agent detects status = "APPROVED")

If Issues:
  - Inline edits or feedback
  - System updates .progress.json: status = "BLOCKED"
  - Return to previous agent with context
```

---

## Example: User Interaction Flow

```
User: "Start feature: document Q&A"
[Specification Agent runs]
[Reads codebase, writes .github/specs/document-qa/feature.md]
[Displays: "✓ Spec created. Review and approve to continue."]

User: "Approved"
[System updates .progress.json]
[Spec Validation Agent auto-starts]
[Runs 15 checks, writes .github/specs/document-qa/feature-validation.md]
[Displays: "✓ Validation passed all 15 checks. Proceeding to architecture."]

[Architect Agent auto-starts]
[Discovers patterns, writes .github/specs/document-qa/feature-tad.md]
[Displays: "✓ TAD created. Review and approve to continue."]

User: "Approved"
[System updates .progress.json]
[Engineer Agent auto-starts]
[Writes all implementation files, tests compile/import check]
[Displays: "✓ 13 files created. Proceeding to testing."]

[QA Agent auto-starts]
[Generates tests, runs pytest + npm test]
[Displays: "✓ 47 tests passing. Proceeding to review."]

[Reviewer Agent auto-starts]
[Reviews all files]
[Displays: "✓ Clean review. Ready to merge!"]

User: Merges to main
```

---

## Extensibility: Adding a New Feature

To add a new feature (e.g., "Document Summarization"):

1. Create `.github/specs/document-summarization/.progress.json` with `{"stage": null, "status": "NOT_STARTED"}`
2. Invoke Specification Agent with feature name
3. **Rest is automatic** — each agent reads `.progress.json`, executes, updates it, and hands off to the next

No changes to any agent code required.

---

## Folder Structure

```
.github/
├── agents/
│   ├── PLATFORM-RULES.md           # Single source of truth (all agents read)
│   ├── EXECUTION-FLOW.md           # This file
│   ├── AGENT-CONTRACTS.md          # I/O contracts per agent
│   ├── AGENTS-GUIDE.md             # Quick reference
│   ├── architect-agent.agent.md
│   ├── engineer-agent.agent.md
│   ├── qa-agent.agent.md
│   ├── reviewer-agent.agent.md
│   ├── specification-agent.agent.md
│   └── spec-validation-agent.agent.md
├── specs/
│   ├── conversational-memory/      # Example: existing feature
│   │   ├── feature.md
│   │   ├── feature-validation.md
│   │   ├── feature-tad.md
│   │   ├── feature-implementation.md
│   │   ├── feature-tests.md
│   │   ├── feature-review.md
│   │   └── .progress.json
│   └── document-qa/                # Example: new feature
│       ├── feature.md
│       ├── feature-validation.md
│       ├── feature-tad.md
│       ├── ...
│       └── .progress.json
└── issue-template.md               # Pre-filled feature description template (optional)
```
