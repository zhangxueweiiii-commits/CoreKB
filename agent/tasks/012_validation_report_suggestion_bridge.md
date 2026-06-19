# Task 012: Validation Report to Pending Suggestion Bridge

## Goal

Create a safe bridge from persisted metadata validation reports to pending metadata suggestions.

The bridge is a review workflow helper only. It must never accept a suggestion, mutate formal document metadata, or trigger indexing.

## Scope

Allowed paths:

- `backend/app/api/routes/documents.py`
- `backend/app/schemas/document.py`
- `backend/app/services/validation_report_suggestion_bridge.py`
- `backend/app/tests/`
- `docs/`
- `agent/tasks/`
- `agent/results/`

## Requirements

1. Add a service that reads `validation_reports.issues_json`.
2. Create `DocumentMetadataSuggestion` rows with `status=pending` only.
3. Deduplicate by existing `document_id + field + suggested_value`.
4. Skip unsupported fields and issues without a safe current value.
5. Preserve validation report traceability in safe suggestion evidence.
6. Add a permission-checked API for admins/editors on the target document knowledge base.
7. Record a safe audit log with counts only.
8. Add tests proving the bridge does not mutate `documents.metadata`, create index jobs, enqueue reindexing, or create success audits on permission failures.

## Hard Constraints

- Do not modify database models.
- Do not create migrations.
- Do not accept metadata suggestions.
- Do not modify `documents.metadata`.
- Do not trigger indexing or reindexing.
- Do not call an LLM.
- Do not parse source files.
- Do not modify frontend.
- Do not weaken existing tests.

## Verification

Run from `backend/`:

```bash
python -m pytest app/tests/test_validation_report_suggestion_bridge.py app/tests/test_validation_report_api.py app/tests/test_metadata_suggestion_safety.py -q
python -m pytest -q
```

Run from repo root:

```bash
python scripts/check_agent_result.py agent/results/012_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
