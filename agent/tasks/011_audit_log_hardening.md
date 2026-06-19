# Task 011: Audit Log Hardening

## Goal

Harden CoreKB audit logging around controlled self-evolution and metadata suggestion review.

## Scope

Small backend service/test documentation changes only.

Allowed paths:

- `backend/app/services/`
- `backend/app/tests/`
- `docs/`
- `agent/tasks/`
- `agent/results/`

Do not modify:

- database models
- migrations
- ingestion, indexing, retrieval, or embedding pipelines
- frontend
- production config
- dependencies

## Requirements

- Recursively redact sensitive audit metadata, including nested dictionaries and lists.
- Keep audit metadata string values bounded.
- Preserve request context fields such as `request_id`, IP address, and user agent when available.
- Strengthen tests for metadata suggestion audit logs so generate/accept actions remain traceable and do not store full source content.
- Document audit log redaction boundaries.

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

