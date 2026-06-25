# Task 036: Maintenance Experience Candidate

## Goal

Add a local Maintenance Experience Candidate panel that helps users turn a reviewed maintenance answer and evidence into a draft candidate for future knowledge curation.

## Scope

Allowed paths:

- `frontend/src/pages/MaintenanceKnowledgePage.tsx`
- `frontend/src/styles.css`
- `docs/`
- `agent/tasks/`
- `agent/results/`

Do not modify:

- backend runtime APIs
- database models
- migrations
- ingestion/indexing/retrieval/embedding logic
- production config
- metadata suggestion review behavior
- assistant prompt or evaluation logic

## Requirements

1. Add a local Maintenance Experience Candidate panel after an assistant answer is returned.
2. Build the candidate from the current equipment model, fault code, symptom, assistant answer, citations, used metadata filter, and top evidence.
3. The candidate must be local UI state only.
4. Provide copy-to-clipboard support for the candidate.
5. Clearly mark the candidate as unreviewed and not yet approved knowledge.
6. Do not persist candidates, update source documents, create metadata suggestions, or trigger reindexing.

## Acceptance Criteria

- Frontend build passes.
- Canonical backend tests pass.
- Agent result checks pass.
- No backend runtime, database, migration, or indexing changes are introduced.

## Verification

Run from `frontend/`:

```bash
npm install
npm run build
```

Run from `backend/`:

```bash
python -m pytest -q
```

Run from repo root:

```bash
python scripts/check_agent_result.py agent/results/036_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
