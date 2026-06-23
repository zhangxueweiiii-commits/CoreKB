# Task 026: Table Row Retrieval Quality Tests

## Goal

Add focused backend tests for table row retrieval quality so table chunks keep row-level evidence through retrieval, search API responses, chat citations, and evaluation snapshots.

## Scope

Allowed paths:

- `backend/app/services/evaluation_service.py`
- `backend/app/tests/`
- `docs/`
- `agent/tasks/`
- `agent/results/`

Do not modify:

- database models
- migrations
- production config
- ingestion/indexing/embedding/vector store logic
- metadata suggestion review behavior
- frontend

## Requirements

1. Verify `RetrievalService` preserves table metadata from `DocumentChunk.meta`.
2. Verify Search API responses include `sheet_name`, `row_start`, and `row_end`.
3. Verify Chat citations include table row range fields.
4. Verify retrieval evaluation `top_results` include row citation fields.
5. Verify persisted evaluation case result snapshots keep row citation fields.
6. Use fake embedding/vector/retrieval services; do not require live Qdrant, LLM, rerank provider, Redis, or Celery.

## Acceptance Criteria

- Targeted table row retrieval quality tests pass.
- Canonical backend tests pass.
- Agent result checks pass.
- No migrations or dependency changes are introduced.

## Verification

Run from `backend/`:

```bash
python -m pytest app/tests/test_table_row_retrieval_quality.py -q
python -m pytest -q
```

Run from repo root:

```bash
python scripts/check_agent_result.py agent/results/026_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
