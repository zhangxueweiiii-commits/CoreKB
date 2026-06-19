# Agent Task Runner

CoreKB includes a lightweight agent task runner for validating task briefs and creating result stubs.

The runner is intentionally small and read-only by default. It does not execute arbitrary task commands, modify application runtime code, touch production data, or call external services.

## Commands

Run from the repository root.

Check agent workflow files:

```bash
python agent/runner.py check
```

Check a task brief:

```bash
python agent/runner.py check --task agent/tasks/TASK_004.md
```

Create a result stub for a valid task brief:

```bash
python agent/runner.py init-result --task agent/tasks/TASK_004.md
```

The result stub is written to `agent/results/` and follows `agent/results/RESULT_CONTRACT.md`.

## Task Contract

Task briefs should include these headings:

- `Goal`
- `Scope`
- `Hard Constraints`
- `Acceptance Criteria`
- `Verification`

Use `agent/tasks/TASK_TEMPLATE.md` for new tasks.

## Result Contract

Completed task results should include:

- `Summary`
- `Files Changed`
- `Behavior Added`
- `Tests Run`
- `Test Result`
- `Database Impact`
- `Runtime Impact`
- `Risk Notes`
- `Rollback Notes`
- `Open Questions`

## Safety Rules

- The runner only validates markdown structure and writes result stubs when explicitly requested.
- It does not mutate production data.
- It does not create metadata suggestions.
- It does not modify `documents.metadata`.
- It does not trigger indexing or reindexing.
- It does not modify application runtime behavior.
