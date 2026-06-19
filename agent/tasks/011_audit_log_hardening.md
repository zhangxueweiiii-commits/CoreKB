# Task 011: Audit Log Hardening for Metadata Suggestion Review

## Goal

Harden audit logging around metadata suggestion generate, accept, and reject so production-impacting metadata review actions are traceable and safe.

## Scope

Backend tests, minimal backend audit metadata changes, and documentation only.

Allowed paths:

- `backend/app/api/routes/documents.py`
- `backend/app/services/audit_service.py`
- `backend/app/tests/`
- `docs/METADATA.md`
- `docs/COREKB_STATE.md`
- `agent/tasks/`
- `agent/results/`

Do not modify:

- database models
- migrations
- ingestion, indexing, retrieval, or embedding pipelines
- frontend
- production config
- authentication model
- permission model
- unrelated APIs
- dependencies

## Requirements

- Metadata suggestion generate audit must remain present.
- Metadata suggestion accept audit must remain present.
- Metadata suggestion reject audit must remain present.
- Accept audit metadata must include `field`, accepted safe `value`, `suggestion_id`, `index_job_id`, `reindex_triggered`, and `custom_value`.
- Reject audit metadata must include `field`, `suggestion_id`, and `rejected_status`.
- Generate audit metadata must include `suggestion_count`; the document id must be present through audit log fields, not duplicated unnecessarily in metadata.
- Audit metadata must not include full source document content, parsed text, file content, evidence excerpts, API keys, passwords, tokens, or secrets.
- If current behavior already satisfies a requirement, add tests instead of changing runtime code.

## Non-Goals

- No schema changes.
- No audit retention policy implementation.
- No external SIEM integration.
- No frontend audit UI changes.
- No changes to metadata suggestion accept/reject behavior.

## Verification

Run:

```bash
python -m pytest app/tests/test_audit_logs.py app/tests/test_metadata_suggestion_safety.py -q
python -m pytest -q
python scripts/check_agent_result.py agent/results/011_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
