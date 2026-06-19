# Task 010: Suggestion Review Guardrail

## Goal

Add minimal review guardrails around existing metadata suggestion review.

## Scope

Small backend/API, frontend display, tests, and documentation changes.

Allowed paths:

- `backend/app/schemas/`
- `backend/app/services/`
- `backend/app/api/routes/`
- `backend/app/tests/`
- `frontend/src/api/`
- `frontend/src/pages/`
- `docs/`
- `agent/tasks/`
- `agent/results/`

Do not modify:

- database models
- migrations
- ingestion, indexing, retrieval, or embedding pipeline behavior
- production config
- dependencies

## Requirements

- Return review guardrail information with metadata suggestion responses.
- Make fallback/custom-value review explicit.
- Require `custom_value=true` when accepting a manual override that cannot be normalized by dictionary or rules.
- Keep generated suggestions advisory until accepted.
- Preserve explicit accept behavior and single-document reindex behavior.
- Display guardrail warnings in the existing document metadata suggestion review area.
- Add tests for guardrail response fields and custom override rejection.

## Non-Goals

- No batch review.
- No approval workflow.
- No LLM extraction.
- No automatic acceptance.
- No database schema changes.

## Verification

Run:

```bash
python -m pytest app/tests/test_document_metadata_suggestions.py -q
python -m pytest -q
npm run build
python scripts/check_agent_result.py agent/results/010_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```

