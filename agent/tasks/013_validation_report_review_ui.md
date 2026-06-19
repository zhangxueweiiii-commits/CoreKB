# Task 013: Validation Report Review UI

## Goal

Add a small frontend review surface for validation reports so admins/editors can inspect report issues on a document and create pending metadata suggestions from a report.

## Scope

Allowed paths:

- `frontend/src/api/client.ts`
- `frontend/src/pages/KnowledgeBaseDetail.tsx`
- `frontend/src/styles.css`
- `docs/`
- `agent/tasks/`
- `agent/results/`

## Requirements

1. Show validation reports on the document detail area.
2. Show report severity, status, summary, issue count, and issue details.
3. Allow admins/editors to call the existing bridge API to create pending metadata suggestions from a report.
4. Display bridge result counts and skipped issue reasons.
5. Keep the UI explicit that reports are diagnostics and bridge output is pending review only.

## Hard Constraints

- Do not modify backend runtime code.
- Do not modify database models or migrations.
- Do not modify ingestion, indexing, retrieval, or embedding pipelines.
- Do not add frontend dependencies.
- Do not auto-accept suggestions.
- Do not modify `documents.metadata` directly.
- Do not trigger reindexing from the review UI.

## Verification

Run from `frontend/`:

```bash
npm ci
npm run build
```

Run from `backend/`:

```bash
python -m pytest -q
```

Run from repo root:

```bash
python scripts/check_agent_result.py agent/results/013_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
