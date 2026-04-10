# local-kb Refactor Plan

## Goal
Turn `local-kb` from a useful-but-fragile prototype into a maintainable local knowledge app with cleaner architecture, fewer hidden bugs, and a smoother launch/setup story.

## Current Assessment

### What is working
- Strong product concept
- Useful CLI workflow
- Good core feature set: ingest, compile, ask, index, quality check
- UI is simple enough to be usable
- Incremental compile/indexing is the right direction

### Main problems
- `scripts/kb.py` does too much
- API layer is mostly a subprocess wrapper around CLI commands
- State and status logic are duplicated and can drift
- Launch/runtime config is too hardcoded
- Frontend and backend assumptions are brittle
- Error handling is inconsistent and often too quiet
- Cross-platform startup is not designed cleanly

---

## Refactor Principles
1. Keep the product working while refactoring, no rewrite-from-scratch detour.
2. Preserve CLI usability.
3. Move business logic into importable Python modules.
4. Make the API call Python functions, not shell commands, wherever possible.
5. Centralize config and state decisions.
6. Reduce hidden assumptions, ports, hosts, model names, file naming, index status.
7. Add a few smoke tests before big moves.

---

## Target Architecture

### Python package structure
Create a real package under something like:

```text
local_kb/
  __init__.py
  config.py
  paths.py
  models.py
  utils.py
  ingest.py
  extract.py
  compile.py
  retrieval.py
  faiss_index.py
  lint.py
  corrections.py
  health.py
  api_services.py
```

### Keep these entry points
- `scripts/kb.py` → thin CLI wrapper only
- `frontend/api.py` → thin FastAPI layer only

### Desired responsibility split
- `config.py` → load/validate `kb.toml`
- `paths.py` → all directory/file constants
- `ingest.py` → local file/url/pdf/docx ingest logic
- `extract.py` → pdf/docx/html extraction helpers
- `compile.py` → compile/merge/update wiki logic
- `retrieval.py` → TF-IDF fallback + context assembly
- `faiss_index.py` → embedding/index/search/status logic only
- `lint.py` → link + orphan analysis
- `corrections.py` → correction capture + storage
- `health.py` → health-check/report generation
- `api_services.py` → backend-facing orchestration functions returning structured results

---

## Phase 0, Stabilize Before Refactor

### 0.1 Add smoke tests
Create a minimal test set covering:
- ingest a markdown file
- compile one source into one wiki page
- build FAISS index
- ask a question with FAISS disabled
- ask a question with FAISS enabled when index exists
- status endpoint returns sane values

### 0.2 Add fixture KB data
Create a tiny test fixture set under something like:

```text
tests/fixtures/kb/
```

Use 2-3 very small markdown files so tests run fast.

### 0.3 Add a regression test for the stale-index bug
Explicitly test `INDEX.md` handling and FAISS stale state.

---

## Phase 1, Untangle Core Python Code

### 1.1 Extract shared paths/config first
Move these out of `scripts/kb.py`:
- ROOT / KB / RAW / WIKI / OUTPUTS / INDEX paths
- config defaults + `kb.toml` loading
- JSON helpers
- file/path helpers

This is low-risk and makes the rest easier.

### 1.2 Split extraction helpers
Move out:
- `extract_pdf_text`
- `_ocr_pdf`
- `extract_docx_text`
- HTML cleaning / URL-to-markdown conversion
- image download helpers

These belong in `extract.py` and maybe `ingest.py`.

### 1.3 Split compile pipeline
Move out:
- `find_matching_wiki_page`
- `update_doc`
- `_summarize_single`
- `_summarize_chunked`
- `summarize_doc`
- `fallback_article`
- `build_wiki_index`
- compile orchestration

End state:
- a `compile_documents(...)` function returns structured results
- CLI prints those results
- API uses those results directly

### 1.4 Split retrieval and linting
Move out:
- `relevant_pages`
- ask context assembly fallback pieces
- lint logic
- health-check generation

This should make `kb.py` dramatically smaller.

### 1.5 Shrink `scripts/kb.py`
Goal: `scripts/kb.py` becomes mostly:
- parser definitions
- command handlers calling package functions
- result printing

If it’s still 1200 lines after refactor, the refactor failed.

---

## Phase 2, Fix the API Layer

### 2.1 Stop shelling out for internal operations
Current pattern:
- FastAPI endpoint
- subprocess calls CLI
- CLI re-loads config and state
- parse stdout text back into response

Replace with:
- FastAPI endpoint calls Python service function directly
- service function returns typed structured data
- endpoint returns JSON

Keep subprocess only when truly needed, ideally never for local internal actions.

### 2.2 Define response models
Add explicit response models for:
- status
- compile result
- stream progress event
- ask result
- lint result
- index result
- correction result
- health-check result

Right now some of this is implied and loose.

### 2.3 Centralize status logic
Create one backend status function for:
- file counts
- model availability
- FAISS install/build/stale state

No duplicate logic between CLI/API/test code.

### 2.4 Add structured errors
Return clean error payloads instead of relying on stderr-ish strings inside `output`.

Recommended shape:

```json
{
  "ok": false,
  "error": {
    "code": "MODEL_NOT_FOUND",
    "message": "model 'x' not found"
  }
}
```

You can still include raw details for debugging.

---

## Phase 3, Clean Up the Frontend

### 3.1 Make runtime config real
Stop hardcoding:
- API base URL
- frontend assumptions about backend port

Use env vars consistently:
- `NEXT_PUBLIC_API_BASE`

### 3.2 Create shared hooks
Current components repeat patterns like:
- load models/status
- loading state
- result state
- try/catch boilerplate

Extract hooks like:
- `useStatus()`
- `useModels()`
- `useCommandAction()`
- `useFileList(category)`

### 3.3 Reduce component sprawl-by-copying
The tabs are readable, but they duplicate result panels, loading/error handling, model loading, button patterns.
Make small shared UI pieces:
- `CommandResultPanel`
- `SectionCard`
- `ModelSelect`
- `StatusBadge`

### 3.4 Fix UX inconsistencies
Examples:
- default model dropdown in sidebar does nothing
- compile stream exists, other long actions don’t stream
- some actions refresh status automatically, some don’t
- file counts can go stale until manual refresh

Need one coherent UI behavior model.

### 3.5 Explorer hardening
Add:
- better empty states
- explicit binary preview message from backend
- refresh button per tab or auto-refresh after delete/promote/compile
- maybe pagination if vault gets large

---

## Phase 4, Runtime and Setup Cleanup

### 4.1 Replace ad hoc startup with proper config-driven startup
Current startup is fragile because it assumes:
- fixed ports
- installed frontend deps
- local-only hostnames
- OS-specific launch behavior

Add a simple config strategy:
- backend port env var
- frontend port env var
- API base env var

### 4.2 Provide three supported launch modes
Document and support:
1. CLI only
2. dev UI mode
3. packaged/local service mode

### 4.3 Cross-platform scripts
Keep:
- `start-ui.bat`
- `start-ui.py`

But make them both use the same environment/config model.

### 4.4 Preflight checks
Before startup:
- verify Python deps
- verify `frontend/node_modules`
- verify required ports are free or print better guidance
- verify Ollama reachable, or at least warn clearly

---

## Phase 5, Data and State Reliability

### 5.1 Formalize index state
Current FAISS state relies on multiple files and implicit assumptions.
Document and centralize:
- what files define index existence
- what makes it stale
- whether `INDEX.md` counts
- what happens when wiki pages are deleted

### 5.2 Formalize docs-to-wiki mapping
`docs.json` is important but under-disciplined.
Define its contract clearly:
- source file path
- source digest
- output wiki page
- updated timestamp
- maybe compile mode used

### 5.3 Corrections storage strategy
The correction feature is good product-wise, but it needs a clean data model.
Define where corrections live and how they are applied:
- append-only correction notes?
- dedicated corrections folder?
- merge-on-compile behavior?

Right now it risks becoming magical.

### 5.4 Safer file operations
Anything destructive should be clearer and easier to reason about.
Potential improvements:
- soft delete / trash for UI deletes
- audit log for destructive actions
- explicit warnings when deleting wiki vs raw source

---

## Recommended Sequence of Work

### Milestone 1, Safety net
- Add smoke tests
- Add regression test for stale FAISS bug
- Add fixture data

### Milestone 2, Shared internals
- Extract `config.py`, `paths.py`, `utils.py`
- Extract `extract.py`
- Extract `lint.py`

### Milestone 3, Compile/retrieval split
- Extract compile pipeline module
- Extract retrieval module
- Reduce `kb.py` size heavily

### Milestone 4, API cleanup
- Replace subprocess-backed endpoints with direct Python calls
- Add typed response models
- Centralize status logic

### Milestone 5, frontend cleanup
- Env-based API config
- Shared hooks/components
- unify result/status refresh behavior

### Milestone 6, launch/setup cleanup
- better startup scripts
- preflight checks
- cross-platform docs

---

## Top 10 Concrete Issues to Fix First
1. Split `scripts/kb.py`
2. Remove hardcoded frontend API base URL
3. Replace API subprocess wrappers with direct service calls
4. Centralize FAISS stale/build status logic
5. Add tests for compile/index/ask/status
6. Add startup preflight checks
7. Make status/file counts auto-refresh after mutations
8. Make model selection behavior real and consistent
9. Clean up correction-flow data model
10. Reduce silent exception swallowing

---

## What Not To Do
- Do not rewrite the whole app from scratch
- Do not replace the CLI with the API, keep both
- Do not over-engineer with a giant framework or database too early
- Do not add more features before stabilizing architecture
- Do not keep piling logic into `kb.py`

---

## Definition of Success
You’ll know this refactor worked when:
- `kb.py` is small enough to understand in one sitting
- the API no longer depends on parsing CLI stdout for core app behavior
- startup works predictably across machines
- FAISS/index state is boring and reliable
- adding a new feature means touching 1-3 files, not 9
- regressions like the stale-index bug get caught by tests

---

## Recommended Immediate Next Step
Start with a small PR that does only this:
- create `config.py`, `paths.py`, `utils.py`
- move shared helpers there
- keep behavior identical
- add one smoke test for `status`

That gives you a clean base without destabilizing the app.
