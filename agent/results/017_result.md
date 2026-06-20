# Task 017 Result

## Summary

Added a real retrieval evaluation harness that calls the existing CoreKB retrieval evaluation API from a CLI script. The harness is explicitly opt-in, requires an admin token, and requires `--confirm-persist` because the existing API creates evaluation run records.

## Files Changed

- `agent/tasks/017_real_retrieval_evaluation_harness.md`
- `agent/results/017_result.md`
- `scripts/run_real_retrieval_evaluation.py`
- `backend/app/tests/test_real_retrieval_evaluation_harness.py`
- `Makefile`
- `docs/EVALUATION.md`
- `docs/corekb_self_evolution.md`

## Behavior Added

- Added `scripts/run_real_retrieval_evaluation.py` for API-backed real retrieval evaluation runs.
- Added `make eval-real` as a convenience target.
- Supported single-run mode via `POST /api/evaluation/retrieval/run`.
- Supported compare mode via `POST /api/evaluation/retrieval/compare`.
- Added guardrails requiring `COREKB_ADMIN_TOKEN` or `--token` and `--confirm-persist`.
- Added structured JSON output with request summary, metrics summary, response payload, runtime dependency notes, and redacted token display.
- Added tests for endpoint construction, payload construction, persistence confirmation, token requirement, redaction, transport invocation, and compare summary handling.

## Tests Run

- `python -m pytest app/tests/test_real_retrieval_evaluation_harness.py -q` from `backend/`
- `python scripts/run_real_retrieval_evaluation.py --compact` from repo root
- `python scripts/run_real_retrieval_evaluation.py --confirm-persist --compact` from repo root
- `python -m pytest -q` from `backend/`
- `make eval-real` from repo root
- `python scripts/check_agent_result.py agent/results/017_result.md` from repo root
- `python scripts/check_agent_result.py "agent/results/*_result.md"` from repo root
- `python agent/runner.py check` from repo root

## Test Result

- Targeted harness tests passed: `8 passed`.
- Guardrail command without `--confirm-persist` exited non-zero with the expected refusal message.
- Guardrail command with `--confirm-persist` but no token exited non-zero with the expected admin token message.
- Canonical backend tests passed: `307 passed, 1 skipped, 16 warnings`.
- `make eval-real` could not run locally because `make` is not installed on this Windows host; the equivalent Python guardrail commands were run directly.
- Agent result checks and runner check passed.

## Runtime Impact

No application runtime behavior changed. The harness is a CLI tooling script and uses existing API endpoints only. It does not import backend service code or change API behavior.

## Database Impact

No database schema impact. No models or migrations changed. Running the harness against a live API with `--confirm-persist` will create evaluation run records through the existing API by design; this task itself did not create or modify database data.

## Risk Notes

- `eval-real` depends on a running CoreKB API, a valid admin bearer token, and a prepared Evaluation KB with indexed fixtures.
- The harness does not directly verify fixture import readiness before calling the API; readiness errors are returned by the existing API.
- Compare mode can create multiple evaluation run records because it calls the existing compare endpoint.
- The harness intentionally does not hide that persistence happens through the API.

## Rollback Notes

Revert this task's changes to remove `eval-real`, the real retrieval harness, tests, task brief, result file, and documentation additions.

## Open Questions

- Should a future task add a non-persisting backend evaluation API mode for dry-run real retrieval metrics?
- Should a future task add CI-gated integration execution using `RUN_INTEGRATION_TESTS=1` and a disposable CoreKB stack?
