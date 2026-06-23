# Task 030: Enable Table Filter UI Fields

## Goal

Expose the table-specific metadata filter fields added in Task 029 through the Search page metadata filter builder.

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

1. Add structured Search page filter controls for table fields:
   - `source_type`
   - `sheet_name`
   - `table_index`
   - `row_start`
   - `row_end`
2. Keep existing business metadata filter controls.
3. Keep advanced metadata JSON input.
4. Show the effective metadata filter JSON before search.
5. Do not add backend endpoints or dependencies.

## Acceptance Criteria

- Frontend build passes.
- Canonical backend tests pass.
- Agent result checks pass.
- No migrations or backend pipeline changes are introduced.

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
python scripts/check_agent_result.py agent/results/030_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
