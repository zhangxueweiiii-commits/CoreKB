# Task 035: Maintenance Record Draft

## Goal

Add a local Maintenance Record Draft panel to the Maintenance Knowledge page so users can turn the current maintenance query, answer, citations, and evidence into a copyable repair record draft.

## Scope

Allowed paths:

- `frontend/src/pages/MaintenanceKnowledgePage.tsx`
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
- assistant prompt or evaluation logic

## Requirements

1. Add a Maintenance Record Draft panel after an assistant answer is returned.
2. Build the draft from the current equipment model, fault code, symptom, notes, assistant answer, citations, used metadata filter, and top evidence.
3. The draft must be local UI state only.
4. Provide copy-to-clipboard support for the draft.
5. Clearly mark the draft as requiring human review before use.
6. Do not persist records, create work orders, call external systems, or add backend endpoints.

## Acceptance Criteria

- Frontend build passes.
- Canonical backend tests pass.
- Agent result checks pass.
- No backend runtime, database, migration, or indexing changes are introduced.

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
python scripts/check_agent_result.py agent/results/035_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
