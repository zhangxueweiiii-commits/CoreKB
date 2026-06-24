# Task 033: Maintenance Knowledge MVP

## Goal

Add a minimal maintenance knowledge workspace that wraps the existing maintenance assistant for equipment fault lookup and repair guidance.

## Scope

Allowed paths:

- `frontend/src/App.tsx`
- `frontend/src/components/Layout.tsx`
- `frontend/src/pages/`
- `frontend/src/api/client.ts`
- `frontend/src/styles.css`
- `docs/`
- `agent/tasks/`
- `agent/results/`

Do not modify:

- backend runtime APIs
- database models
- migrations
- ingestion/indexing/retrieval/embedding logic
- production config
- metadata suggestion review behavior

## Requirements

1. Add a lightweight Maintenance Knowledge page.
2. Reuse the existing `maintenance` assistant preset and assistant chat API.
3. Provide fields for equipment model, fault code, symptom, and optional notes.
4. Default metadata filter must include `category=maintenance`.
5. Use rerank by default.
6. Display answer, citations, used metadata filter, rerank status, and no-answer state.
7. Add navigation entry for logged-in users.
8. Do not add Agent, Workflow, new backend endpoints, migrations, or dependencies.

## Acceptance Criteria

- Frontend build passes.
- Canonical backend tests pass.
- Agent result checks pass.
- No backend runtime pipeline changes are introduced.

## Verification

Run from `frontend/`:

```bash
npm install
npm run build
```

Run from `backend/`:

```bash
python -m pytest -q
```

Run from repo root:

```bash
python scripts/check_agent_result.py agent/results/033_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
