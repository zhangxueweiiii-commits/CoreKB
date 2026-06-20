# Task 024: Excel / CSV Deep Parsing V1

## Goal

Harden the first production-oriented Excel/CSV table parsing path so table documents produce readable chunks and stable metadata for retrieval, citations, metadata filters, and evaluation.

## Scope

Allowed paths:

- `backend/app/services/table_parser.py`
- `backend/app/tests/test_table_parser.py`
- `docs/`
- `agent/tasks/`
- `agent/results/`

Do not modify:

- database models
- migrations
- production config
- frontend
- ingestion/indexing/retrieval service behavior outside the parser output contract
- metadata suggestion review behavior
- evaluation workflow behavior

## Requirements

1. Keep `DocumentParser` table parsing integration compatible.
2. Generate readable table section text for CSV/XLSX files.
3. Preserve table metadata: `source_type`, `sheet_name`, `row_start`, `row_end`, `column_names`, `table_index`, and `source_range`.
4. Skip empty spreadsheet sheets and empty data rows.
5. Normalize blank headers and duplicate headers into stable names.
6. Split long tables by row groups while repeating headers in every table section.
7. Keep chunks table-aware and avoid normal character-overlap splitting for table sections.
8. Add tests covering CSV, XLSX, multiple sheets, duplicate/blank headers, empty rows, and long table row grouping.

## Acceptance Criteria

- `python -m pytest app/tests/test_table_parser.py -q` passes.
- Canonical backend tests pass.
- Agent result checks pass.
- No migrations or dependency changes are introduced.

## Verification

Run from `backend/`:

```bash
python -m pytest app/tests/test_table_parser.py -q
python -m pytest -q
```

Run from repo root:

```bash
python scripts/check_agent_result.py agent/results/024_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
