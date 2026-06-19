# Agent PR Workflow

CoreKB Codex tasks must be reviewed through pull requests instead of manual copy-paste or direct pushes.

## Flow

```text
Codex task branch
    ↓
agent result file
    ↓
PR
    ↓
GitHub Actions
    ↓
review
    ↓
merge
```

## Required Codex Sequence

Every future Codex task must follow this sequence:

1. Read `AGENTS.md`.
2. Read the task file under `agent/tasks/`.
3. Create a branch named `agent/task-XXX-task-name`.
4. Make only scoped changes.
5. Create `agent/results/XXX_result.md`.
6. Run canonical backend tests.
7. Run the agent result checker.
8. Commit changes to the task branch.
9. Open a PR.
10. Wait for human review before merge.

Codex must not push directly to `main` or `develop`.

If branch creation, pushing, or PR creation is unavailable in the local execution environment, Codex should update the repository-side workflow files and report that external GitHub/Codex connection setup is blocked outside the repo.

## Required Files

Each task PR should include a matching result file:

```text
agent/results/{task_id}_result.md
```

The result file must follow `agent/results/RESULT_CONTRACT.md`.

Use `agent/results/RESULT_TEMPLATE.md` when starting a new result file.

## Pull Request Template

The PR template requires:

- Task
- Branch
- Summary
- Files changed
- Result file
- Tests run
- Test result
- Runtime impact
- Database impact
- Risk notes
- Rollback notes
- Checklist

## CI Checks

GitHub Actions runs:

```bash
python agent/runner.py check
python scripts/check_agent_result.py "agent/results/*_result.md"
cd backend && python -m pytest -q
```

The result checker validates every `agent/results/*_result.md` file.

## Local Verification

Run from the repository root:

```bash
python agent/runner.py check
python scripts/check_agent_result.py "agent/results/*_result.md"
```

Run backend tests from `backend/`:

```bash
python -m pytest -q
```

If `make` is available, `make agent-test` runs the agent workflow checks.

## Safety Notes

- CI does not require secrets.
- CI uses repo-relative paths.
- CI does not mutate production data.
- CI does not run migrations against production systems.
- CI does not change ingestion, indexing, retrieval, embedding, or metadata validation behavior.
- Human review is required before merge.
