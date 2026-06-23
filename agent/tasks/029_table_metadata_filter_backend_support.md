# Task 029: Table Metadata Filter Backend Support

## Goal

Extend backend metadata filter support so table-specific payload fields can be used by Search and downstream retrieval flows.

## Scope

Allowed paths:

- `backend/app/services/query_metadata_extractor.py`
- `backend/app/services/vector_store.py`
- `backend/app/tests/`
- `docs/`
- `agent/tasks/`
- `agent/results/`

Do not modify:

- frontend runtime code
- database models
- migrations
- ingestion/indexing/embedding logic
- production config
- metadata suggestion review behavior

## Requirements

1. Add backend metadata filter allowlist support for table payload fields:
   - `source_type`
   - `sheet_name`
   - `table_index`
   - `row_start`
   - `row_end`
2. Keep existing business metadata fields supported.
3. Preserve exact-match semantics.
4. Parse numeric table fields as integers before building Qdrant conditions.
5. Ignore unsupported fields, empty values, and invalid numeric table filters.
6. Add tests for sanitization, Qdrant filter construction, and Search API pass-through.
7. Do not add backend endpoints, migrations, dependencies, or pipeline changes.

## Acceptance Criteria

- Targeted metadata filter tests pass.
- Canonical backend tests pass.
- Agent result checks pass.
- No database or runtime pipeline changes are introduced.

## Verification

Run from `backend/`:

```bash
python -m pytest app/tests/test_table_metadata_filter_backend.py app/tests/test_metadata_filter.py app/tests/test_table_row_retrieval_quality.py -q
python -m pytest -q
```

Run from repo root:

```bash
python scripts/check_agent_result.py agent/results/029_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
