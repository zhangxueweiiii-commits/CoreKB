# Task 037: Maintenance Knowledge Curation Pack V1

## Goal

Move the Maintenance Knowledge MVP from local copy-only drafting into a controlled, auditable maintenance knowledge curation workflow.

## Scope

Implement a coherent maintenance curation pack:

- persisted maintenance record drafts
- persisted maintenance experience candidates
- pending candidate review
- candidate accept/reject actions
- accepted maintenance knowledge entries
- audit logs for production-impacting curation actions

## Boundaries

Do not implement:

- ERP integration
- MES integration
- OA integration
- CMMS integration
- automatic work order submission
- automatic candidate acceptance
- automatic metadata mutation
- automatic source document edits
- batch candidate processing
- batch reindexing
- LLM-based automatic ingestion into knowledge base

## Verification

Run from `backend/`:

```bash
python -m pytest -q
```

Run from `frontend/`:

```bash
npm install
npm run build
```

Run from repo root:

```bash
python scripts/check_agent_result.py agent/results/037_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
