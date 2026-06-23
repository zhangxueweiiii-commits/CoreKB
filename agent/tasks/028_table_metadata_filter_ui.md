# Task 028: Table Metadata Filter UI

## Goal

Add a lightweight structured metadata filter UI to the Search page so table-oriented searches can be narrowed without hand-writing JSON.

## Scope

Allowed paths:

- `frontend/src/pages/SearchPage.tsx`
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

1. Add structured metadata filter controls on the Search page for supported metadata fields:
   - `category`
   - `doc_type`
   - `equipment_model`
   - `fault_code`
   - `material_code`
   - `product_model`
   - `process_name`
   - `sop_code`
   - `version`
2. Preserve the existing advanced metadata filter JSON input.
3. Merge structured filters and advanced JSON before calling the existing Search API.
4. Show the effective metadata filter JSON before search.
5. Keep table result display from Task 027 intact.
6. Do not add backend endpoints or dependencies.

## Acceptance Criteria

- Frontend build passes.
- Canonical backend tests pass.
- Agent result checks pass.
- No migrations or backend runtime pipeline changes are introduced.

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
python scripts/check_agent_result.py agent/results/028_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
