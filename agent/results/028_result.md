# Task 028 Result

## Summary

Added a structured metadata filter builder to the Search page for table-heavy retrieval workflows. The UI now lets users fill supported metadata fields, optionally add advanced JSON, and review the effective filter before calling the existing Search API.

## Files Changed

- `agent/tasks/028_table_metadata_filter_ui.md`
- `agent/results/028_result.md`
- `docs/METADATA.md`
- `frontend/src/pages/SearchPage.tsx`
- `frontend/src/styles.css`

## Behavior Added

- Search page supports structured inputs for `category`, `doc_type`, `equipment_model`, `fault_code`, `material_code`, `product_model`, `process_name`, `sop_code`, and `version`.
- Advanced metadata filter JSON remains available and overrides structured fields for duplicate keys.
- Effective metadata filter JSON is shown before search.
- Clear filters action resets both structured and advanced metadata filter inputs.
- Documentation explains that table sheet and row metadata are displayed in results but are not first-version filter fields.

## Tests Run

- `npm install`
- `npm run build`
- `python -m pytest -q`
- `python scripts/check_agent_result.py agent/results/028_result.md`
- `python scripts/check_agent_result.py "agent/results/*_result.md"`
- `python agent/runner.py check`

## Test Result

- Frontend build passed.
- Backend tests passed: 336 passed, 1 skipped, 15 warnings.
- Agent result checks passed.
- Agent runner check passed.

## Runtime Impact

Frontend-only UX change. Existing Search API calls are reused. No backend runtime behavior, ingestion, indexing, retrieval, embedding, metadata suggestion, or evaluation behavior was changed.

## Database Impact

None. No models, migrations, or persisted data write paths were changed.

## Risk Notes

- The UI only exposes fields already supported by the backend metadata filter allowlist.
- Sheet name and row range filtering is intentionally not added because the current backend sanitizer ignores those fields.
- Advanced JSON parse errors are shown as search errors and do not send a malformed request.

## Rollback Notes

Revert the changed Search page, stylesheet, documentation, task file, and result file to remove this UI enhancement.

## Open Questions

- Should a later backend task add exact-match filters for table-specific fields such as `sheet_name` or `source_type`?
