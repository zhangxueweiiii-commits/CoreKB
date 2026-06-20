# Task 020: Persisted Failure Triage Notes

## Goal

Persist lightweight reviewer notes from the Evaluation Failure Triage page so admins can keep case-level triage status and comments without creating formal annotations or improvement items.

## Scope

Allowed paths:

- `backend/app/models/`
- `backend/app/services/`
- `backend/app/schemas/`
- `backend/app/api/routes/`
- `backend/alembic/versions/`
- `backend/app/tests/`
- `frontend/src/`
- `docs/`
- `agent/tasks/`
- `agent/results/`

Do not modify:

- ingestion pipeline
- embedding pipeline
- indexing pipeline
- retrieval pipeline
- production configuration
- metadata suggestion behavior
- document metadata write paths

## Requirements

1. Add persisted failure triage notes linked to `evaluation_case_results`.
2. Support one current note per case result.
3. Store triage status, note text, author fields, and timestamps.
4. Add admin-only API endpoints to list, get, and upsert notes.
5. Display and edit notes from the Evaluation Failure Triage page.
6. Keep notes advisory only; they must not mutate production metadata, annotations, improvement items, prompts, chunking, rerank configuration, or indexes.
7. Add tests and documentation.

## Acceptance Criteria

- Migration creates the new notes table.
- Admin can create and update a note for a case result.
- Notes can be listed by evaluation run and status.
- Drill-down includes the current triage note.
- Non-admin users remain blocked by existing admin guardrails.
- Frontend build passes.
- Canonical backend tests pass.
- Agent result checker passes.
