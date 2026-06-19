# CoreKB Codex Workflow

This file is the top-level operating guide for Codex agents working in the CoreKB repository.

## Primary Rule

Follow the task scope exactly. If a task restricts allowed paths, do not edit files outside those paths.

When task instructions conflict with general repository preferences, the task-specific constraints win.

## PR-Only Workflow

Every future Codex task must be completed through a branch and pull request. Codex must not push directly to `main` or `develop`.

Required sequence:

1. Read `AGENTS.md`.
2. Read the task file under `agent/tasks/`.
3. Create a branch named `agent/task-XXX-task-name`.
4. Make only scoped changes.
5. Create `agent/results/XXX_result.md`.
6. Run the canonical backend tests.
7. Run the agent result checker.
8. Commit changes to the task branch.
9. Open a pull request.
10. Wait for human review before merge.

If the local environment cannot create branches, commits, or pull requests, update the repository-side workflow files and clearly report that external GitHub or Codex connection setup is blocked outside the repo.

## Project Guardrails

- Do not modify application runtime logic unless the task explicitly allows it.
- Do not modify database models or create migrations unless the task explicitly allows it.
- Do not touch production configuration unless the task explicitly allows it.
- Do not add dependencies unless the task explicitly allows it.
- Do not weaken, skip, or narrow tests to hide failures.
- Do not call LLMs, mutate production data, or trigger indexing from advisory validation/evaluation workflows unless an approved task explicitly adds that write path.

## Controlled Self-Evolution

CoreKB supports advisory inspection workflows such as metadata validation, metadata precheck, evaluation reports, failed-case analysis, and improvement items.

These outputs are evidence for human review. They must not directly mutate production data.

Automatic suggestions cannot:

- Modify `documents.metadata`.
- Accept metadata suggestions.
- Rewrite prompts.
- Change chunking or rerank parameters.
- Trigger production reindexing.
- Update source documents.

Any production-impacting action must be explicit, reviewed, and traceable.

See:

- `agent/rules/AGENT_POLICY.md`
- `docs/corekb_self_evolution.md`

## Standard Work Loop

1. Read the user task carefully.
2. Identify allowed and forbidden paths.
3. Inspect existing project structure before editing.
4. Make the smallest safe change.
5. Run targeted tests for the changed area.
6. Run the canonical backend command when backend behavior or tests are affected.
7. Report changed files, tests run, results, risks, and rollback notes.

For structured agent tasks, use the lightweight runner documented in `docs/AGENT_TASK_RUNNER.md`. The runner validates task/result markdown structure and can create result stubs, but it does not execute arbitrary task commands or mutate production data.

## Backend Test Command

Run from `backend/`:

```bash
python -m pytest -q
```

This is the canonical backend verification command documented in `docs/TESTING.md`.

For a targeted metadata validation check:

```bash
python -m pytest app/tests/test_metadata_validation.py -q
```

If `make` is unavailable on the host, run the equivalent Python command directly and report that clearly.

## Frontend Verification

When frontend code changes, run from `frontend/`:

```bash
npm install
npm run build
```

After verification, remove generated local dependency/build artifacts when appropriate, such as `node_modules/` and `dist/`, unless the task asks to keep them.

## Documentation-Only Tasks

For documentation-only or workflow-only tasks:

- Do not edit backend runtime code.
- Do not edit frontend runtime code.
- Do not create migrations.
- Do not modify tests unless the task explicitly asks for test workflow changes.
- Run the most relevant lightweight validation available, such as checking required files exist.

## Result Reporting

Final responses should be concise and include:

- Summary
- Files changed
- Tests run
- Test result
- Database impact
- Runtime impact
- Risk notes
- Rollback notes
- Open questions, if any

Use the exact result format requested by the task when one is provided.
