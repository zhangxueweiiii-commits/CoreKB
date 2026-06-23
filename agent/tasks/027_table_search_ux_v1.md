# Task 027: Table Search UX V1

## Goal

Add a minimal Search page that makes table search results easier to inspect by showing sheet names, row ranges, columns, snippets, and scores.

## Scope

Allowed paths:

- `frontend/src/App.tsx`
- `frontend/src/components/Layout.tsx`
- `frontend/src/pages/`
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

1. Add a lightweight Search page using the existing `api.search` client.
2. Allow users to select knowledge bases, enter a query, choose top K, provide optional metadata filter JSON, and toggle rerank.
3. Display normal search results with filename, page/section when present, scores, and chunk text.
4. Display table results with explicit sheet name, row range, column names, table match label, and chunk text.
5. Do not add new backend endpoints.
6. Do not introduce new dependencies.

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
python scripts/check_agent_result.py agent/results/027_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
