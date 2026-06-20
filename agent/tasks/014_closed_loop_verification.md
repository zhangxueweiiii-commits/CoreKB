# Task 014: Closed Loop Verification

## Goal

Verify the controlled CoreKB metadata self-evolution loop from diagnostic report to reviewed metadata action.

This task adds tests and documentation only. It must not introduce new product behavior.

## Scope

Allowed paths:

- `backend/app/tests/`
- `docs/`
- `agent/tasks/`
- `agent/results/`

## Requirements

1. Add tests that cover the closed loop:
   - persisted validation report
   - validation report read APIs
   - validation-report-to-pending-suggestion bridge
   - explicit reviewer accept
   - explicit reviewer reject
   - audit boundaries
   - reindex boundary
2. Prove the bridge stage does not mutate `documents.metadata`.
3. Prove the bridge stage does not create index jobs or enqueue reindexing.
4. Prove only explicit accept writes metadata and creates/enqueues one index job.
5. Prove explicit reject does not write metadata or reindex.
6. Update documentation to describe the closed-loop verification boundary.

## Hard Constraints

- Do not modify runtime application logic.
- Do not modify frontend.
- Do not modify database models.
- Do not create migrations.
- Do not modify ingestion, embedding, indexing, retrieval, or vector store logic.
- Do not call an LLM.
- Do not add dependencies.
- Do not weaken existing tests.

## Verification

Run from `backend/`:

```bash
python -m pytest app/tests/test_closed_loop_verification.py -q
python -m pytest app/tests/test_closed_loop_verification.py app/tests/test_validation_report_suggestion_bridge.py app/tests/test_metadata_suggestion_safety.py -q
python -m pytest -q
```

Run from repo root:

```bash
python scripts/check_agent_result.py agent/results/014_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
