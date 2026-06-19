# CoreKB Agent Policy

This policy defines how Codex-driven changes should be planned, executed, reviewed, and verified for CoreKB.

## Scope Control

- Agent tasks must declare their scope before editing files.
- Changes must stay inside the allowed paths for the task.
- Application runtime code, database models, migrations, production configuration, and tests must not be modified unless the task explicitly permits it.
- When a task is documentation-only or workflow-only, the agent must not touch backend or frontend runtime logic.

## Production Data Safety

- Automatic suggestions, evaluations, prechecks, metadata recommendations, and improvement items are advisory only.
- Automatic suggestions must never directly mutate production data.
- Any operation that changes production data must require an explicit user or administrator action.
- Bulk repair, auto-accept, auto-reindex, or automatic metadata overwrite must be treated as separate tasks with explicit review and rollback planning.

## Change Workflow

1. Read the task and identify allowed paths.
2. Inspect existing files before editing.
3. Make the smallest scoped change that satisfies the acceptance criteria.
4. Run the most relevant verification command available in the workspace.
5. Record changed files, test results, and risk notes in the final response.

## Review Expectations

- Prefer small, reviewable patches.
- Document placeholders clearly when a target is intentionally stubbed.
- Do not hide uncertainty. If a target cannot be fully verified locally, state what was and was not tested.
- Do not introduce new dependencies without explicit approval.

## Evaluation Discipline

- Evaluation results are evidence, not automatic deployment gates.
- Failed cases, precheck findings, and improvement items should guide human review.
- A future automated evaluation target may run retrieval and assistant evaluation suites, but it must remain read-only unless explicitly changed by a reviewed task.
