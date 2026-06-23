# Task 027 Result

## Summary

Added a lightweight frontend Search page for table search UX V1. The page uses the existing Search API and highlights table-specific evidence such as sheet name, row range, column names, snippet, and scores.

## Files Changed

- `agent/tasks/027_table_search_ux_v1.md`
- `agent/results/027_result.md`
- `docs/METADATA.md`
- `frontend/src/App.tsx`
- `frontend/src/components/Layout.tsx`
- `frontend/src/pages/SearchPage.tsx`
- `frontend/src/styles.css`

## Behavior Added

- Added a Search navigation item.
- Added a Search page using the existing `api.search` client.
- Users can select knowledge bases, enter a query, set `top_k`, provide optional metadata filter JSON, and toggle rerank.
- Normal results show filename/page/section when available, scores, and chunk text.
- Table results show a table match label, sheet name, row range, column names, scores, and chunk text.

## Tests Run

- From `frontend/`: `npm install`
- From `frontend/`: `npm run build`
- From `backend/`: `python -m pytest -q`
- From repo root: `python scripts/check_agent_result.py agent/results/027_result.md`
- From repo root: `python scripts/check_agent_result.py "agent/results/*_result.md"`
- From repo root: `python agent/runner.py check`

## Test Result

- Frontend build: passed.
- Canonical backend tests: 336 passed, 1 skipped, 15 warnings.
- Agent result checks and agent runner: passed.

## Runtime Impact

- Adds a frontend-only Search page that calls existing APIs.
- Does not add backend endpoints or change retrieval, indexing, embedding, rerank, metadata suggestion, or evaluation behavior.

## Database Impact

- No database models changed.
- No migrations added.
- No production data is modified.

## Risk Notes

- Metadata filter is entered as raw JSON in V1; invalid JSON shows a client-side error.
- The page displays chunk row ranges from existing search response metadata; it does not provide cell-level navigation.

## Rollback Notes

- Revert the Task 027 commit to remove the Search page, nav item, styles, task/result files, and documentation update.
- No data rollback is required.

## Open Questions

- Should a later task add saved search presets for common table lookups such as material code, fault code, or SOP code?