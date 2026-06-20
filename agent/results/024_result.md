## Summary

Implemented Excel / CSV Deep Parsing V1 hardening for CoreKB table documents. Table parsing now produces readable row-oriented section text, stable column names, and richer row-range metadata while preserving the existing `DocumentParser` and `Chunker` integration contract.

## Files Changed

- agent/tasks/024_excel_csv_deep_parsing_v1.md
- agent/results/024_result.md
- backend/app/services/table_parser.py
- backend/app/tests/test_table_parser.py
- docs/METADATA.md

## Behavior Added

- Replaced mojibake table section text with readable `File`, `Sheet`, `Rows`, `Columns`, and `Row` formatting.
- Preserved table metadata for `source_type`, `sheet_name`, `row_start`, `row_end`, `column_names`, `table_index`, and `source_range`.
- Skips empty Excel sheets and empty data rows.
- Normalizes blank headers to `Column N`.
- Normalizes duplicate headers to stable suffixed names such as `model_2`.
- Splits long tables into row-group sections while repeating table context in every section.

## Tests Run

- `python -m pytest app/tests/test_table_parser.py -q`
- `python -m pytest -q`
- `python scripts/check_agent_result.py agent/results/024_result.md`
- `python scripts/check_agent_result.py "agent/results/*_result.md"`
- `python agent/runner.py check`

## Test Result

Passed. Targeted table parser tests passed with 7 passed. Canonical backend tests passed with 327 passed, 1 skipped, and 15 warnings. Agent result checks passed for the Task 024 result file, all result files, and `python agent/runner.py check`.

## Runtime Impact

Limited parser output behavior change for CSV/XLSX/XLS table documents. No ingestion orchestration, indexing, retrieval, embedding, frontend, production config, or metadata suggestion review behavior changed.

## Database Impact

None. No database models, migrations, schemas, or data writes changed.

## Risk Notes

Readable table section text changes future parsed chunks for newly indexed or reindexed table documents. Existing indexed chunks are unchanged until documents are reprocessed. V1 still does not infer merged cells, multiple independent tables inside one sheet, or formula evaluation semantics.

## Rollback Notes

Revert this task's parser, test, documentation, task, and result files to restore the previous table parser output behavior. No database rollback is required.

## Open Questions

None.
