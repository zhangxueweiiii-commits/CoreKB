# Task 015 Result

## Summary

Implemented a read-only evaluation fixture baseline runner and wired `make eval` to it. The runner validates `eval_cases.json` shape and summarizes fixture coverage without connecting to live services or mutating data.

## Files Changed

- `agent/tasks/015_evaluation_runner_baseline.md`
- `agent/results/015_result.md`
- `scripts/run_evaluation_baseline.py`
- `backend/app/tests/test_evaluation_runner_baseline.py`
- `Makefile`
- `docs/EVALUATION.md`
- `docs/corekb_self_evolution.md`

## Behavior Added

- Added `scripts/run_evaluation_baseline.py` for deterministic fixture readiness checks.
- Updated `make eval` to run the baseline command instead of a placeholder.
- Added tests for loading eval cases, duplicate id detection, required-field checks, coverage summaries, unknown metadata field reporting, and invalid fixture exit behavior.
- Documented that this baseline is read-only and does not run live retrieval, assistant chat, rerank, metadata filtering, indexing, database writes, Qdrant writes, or LLM calls.

## Tests Run

- `python -m pytest app/tests/test_evaluation_runner_baseline.py -q` from `backend/`
- `python scripts/run_evaluation_baseline.py --cases backend/tests/evaluation/fixtures/expected/eval_cases.json` from repo root
- `make eval` from repo root
- `python -m pytest -q` from `backend/`
- `python scripts/check_agent_result.py agent/results/015_result.md` from repo root
- `python scripts/check_agent_result.py "agent/results/*_result.md"` from repo root
- `python agent/runner.py check` from repo root

## Test Result

- Targeted runner tests passed: `6 passed`.
- Direct baseline command passed and reported `ready: true` for 5 eval cases.
- `make eval` could not run locally because `make` is not installed on this Windows host; the equivalent Python command passed.
- Canonical backend tests passed: `293 passed, 1 skipped, 15 warnings`.
- Agent result checks and runner check passed.

## Runtime Impact

No application runtime behavior changed. The new runner is a repository tooling command only and is not imported by API, ingestion, indexing, retrieval, embedding, Celery, or frontend runtime code.

## Database Impact

No database impact. No models, migrations, data, validation reports, suggestions, documents metadata, or index jobs were changed.

## Risk Notes

- The baseline validates fixture readiness only; it does not measure retrieval quality, answer quality, citation quality, or rerank effectiveness.
- The current fixture includes `quality_item` inside `expected_metadata`; the runner reports it as an unknown metadata field for visibility but does not fail readiness.
- Local `make eval` verification was blocked by missing `make`; CI or Unix-like environments should execute the Makefile target directly.

## Rollback Notes

Revert this task's changes to restore the placeholder `eval` target and remove the baseline runner, tests, task brief, and documentation additions.

## Open Questions

- Should a later task promote unknown expected metadata fields from warnings into hard failures once the metadata field contract is finalized?
- Should a later task add an optional live evaluation mode that creates persisted evaluation runs after explicit operator approval?
