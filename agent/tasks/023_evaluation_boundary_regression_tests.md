# Task 023: Evaluation Boundary Regression Tests

## Goal

Add regression tests that protect CoreKB evaluation workflow boundaries. Evaluation review workflows may create evaluation-domain advisory records, but they must not mutate production document metadata, metadata suggestions, indexing jobs, annotations, improvement items, regressions, or other production-impacting records unless explicitly scoped.

## Scope

Allowed paths:

- `backend/app/tests/`
- `agent/tasks/`
- `agent/results/`
- `docs/`

Do not modify:

- backend runtime code
- frontend runtime code
- database models
- migrations
- ingestion, indexing, retrieval, or embedding pipelines
- production configuration

## Hard Constraints

- Do not change runtime behavior.
- Do not create migrations.
- Do not add dependencies.
- Do not weaken or narrow existing tests.
- Do not call LLMs.
- Do not create production data mutation paths.

## Acceptance Criteria

- Add tests proving drill-down reads persisted snapshots without production mutations.
- Add tests proving missing snapshot compare returns unavailable without rerunning or creating case results.
- Add tests proving batch triage writes only triage notes and not structured review or production records.
- Update documentation with the new boundary regression coverage.
- Create `agent/results/023_result.md`.
- Run targeted tests, canonical backend tests, and agent result checks.

## Verification

Run from `backend/`:

```bash
python -m pytest app/tests/test_evaluation_boundary_regression.py -q
python -m pytest -q
```

Run from repo root:

```bash
python scripts/check_agent_result.py agent/results/023_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
