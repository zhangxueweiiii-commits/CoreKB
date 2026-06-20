# Task 022: Evaluation Workflow Hardening Audit

## Goal

Create a documentation-only hardening audit for the CoreKB evaluation workflow before adding more self-evolution features.

## Scope

Allowed paths:

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
- tests

## Hard Constraints

- Do not add product behavior.
- Do not create or modify APIs.
- Do not create migrations.
- Do not alter evaluation, metadata, suggestion, annotation, improvement, regression, or triage behavior.
- Use repo-relative paths only.

## Acceptance Criteria

- Add an evaluation workflow hardening audit document.
- Clearly state current safety controls.
- Clearly state gaps and recommended follow-up phases.
- Clearly state that advisory evaluation outputs must not directly mutate production data.
- Create `agent/results/022_result.md`.
- Run agent result checker and canonical backend tests.

## Verification

Run:

```bash
python scripts/check_agent_result.py agent/results/022_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```

Run canonical backend verification from `backend/`:

```bash
python -m pytest -q
```

## Notes

This is an audit only. Any follow-up implementation should be split into later scoped PRs.
