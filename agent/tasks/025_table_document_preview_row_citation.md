# Task 025: Table Document Preview & Row Citation

## Goal

Add a minimal table document preview and make row-level table citation behavior visible to reviewers.

## Scope

Allowed paths:

- `backend/app/api/routes/documents.py`
- `backend/app/schemas/document.py`
- `backend/app/services/table_parser.py`
- `backend/app/tests/`
- `frontend/src/api/`
- `frontend/src/pages/KnowledgeBaseDetail.tsx`
- `frontend/src/styles.css`
- `docs/`
- `agent/tasks/`
- `agent/results/`

Do not modify:

- database models
- migrations
- production config
- ingestion/indexing/retrieval/embedding pipeline behavior
- metadata suggestion accept/reject behavior
- evaluation workflow behavior

## Requirements

1. Add a read-only table preview API for CSV/XLSX/XLS documents.
2. The preview must include sheet name, headers, row numbers, row values, row counts, column counts, and source row range.
3. The preview must not update `documents.metadata`, create suggestions, create index jobs, or trigger reindexing.
4. Add a frontend document detail section that displays a read-only table preview for table documents.
5. Keep existing row citation fields compatible: `sheet_name`, `row_start`, and `row_end`.
6. Add tests proving preview output and read-only behavior.

## Acceptance Criteria

- Targeted backend tests pass.
- Canonical backend tests pass.
- Frontend build passes.
- Agent result checks pass.
- No migration or dependency change is introduced.

## Verification

Run from `backend/`:

```bash
python -m pytest app/tests/test_table_document_preview.py app/tests/test_table_parser.py -q
python -m pytest -q
```

Run from `frontend/` if frontend changed:

```bash
npm install
npm run build
```

Run from repo root:

```bash
python scripts/check_agent_result.py agent/results/025_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```