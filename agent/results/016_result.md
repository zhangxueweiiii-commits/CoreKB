# Task 016 Result

## Summary

Added a deterministic retrieval evaluation smoke test runner and a `make eval-smoke` target. The smoke runner loads `eval_cases.json`, uses fake retrieval results, and exercises the existing `EvaluationService.evaluate_case()` plus metric calculation path without live infrastructure.

## Files Changed

- `agent/tasks/016_retrieval_evaluation_smoke_test.md`
- `agent/results/016_result.md`
- `scripts/run_retrieval_evaluation_smoke.py`
- `backend/app/tests/test_retrieval_evaluation_smoke.py`
- `Makefile`
- `docs/EVALUATION.md`
- `docs/corekb_self_evolution.md`

## Behavior Added

- Added `scripts/run_retrieval_evaluation_smoke.py` for read-only retrieval evaluation smoke checks.
- Added `make eval-smoke` as a convenience target.
- Added tests for passing smoke metrics, no-answer handling, metadata filter usage, read-only dependency flags, and CLI exit behavior.
- Documented that the smoke test does not measure live retrieval quality and does not persist evaluation runs or case results.

## Tests Run

- `python -m pytest app/tests/test_retrieval_evaluation_smoke.py -q` from `backend/`
- `python scripts/run_retrieval_evaluation_smoke.py --cases backend/tests/evaluation/fixtures/expected/eval_cases.json` from repo root
- `make eval-smoke` from repo root
- `python -m pytest -q` from `backend/`
- `python scripts/check_agent_result.py agent/results/016_result.md` from repo root
- `python scripts/check_agent_result.py "agent/results/*_result.md"` from repo root
- `python agent/runner.py check` from repo root

## Test Result

- Targeted smoke tests passed: `6 passed`.
- Direct smoke command passed and reported `smoke_passed: true` for 5 eval cases.
- `make eval-smoke` could not run locally because `make` is not installed on this Windows host; the equivalent Python command passed.
- Canonical backend tests passed: `299 passed, 1 skipped, 15 warnings`.
- Agent result checks and runner check passed.

## Runtime Impact

No application runtime behavior changed. The new smoke runner is repository tooling only. It is not imported by API, ingestion, indexing, retrieval, embedding, Celery, or frontend runtime code.

## Database Impact

No database impact. No models, migrations, evaluation runs, case result records, documents metadata, suggestions, or index jobs were changed.

## Risk Notes

- This smoke test uses deterministic fake retrieval; it confirms evaluation logic wiring, not production retrieval quality.
- It does not exercise Qdrant payload filters, embeddings, rerank providers, permissions, or API persistence.
- The local host lacks `make`, so Makefile target execution is verified indirectly through the equivalent Python command.

## Rollback Notes

Revert this task's changes to remove `eval-smoke`, the smoke runner, tests, task brief, result file, and documentation additions.

## Open Questions

- Should a later task add an explicit CI job for `make eval` and `make eval-smoke` on Linux where `make` is available?
- Should a later task add a separate integration smoke test that runs against a real Evaluation KB when `RUN_INTEGRATION_TESTS=1` is enabled?
