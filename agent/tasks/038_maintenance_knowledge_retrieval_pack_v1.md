# Task 038: Maintenance Knowledge Retrieval Pack V1

## Goal

Make accepted maintenance knowledge entries retrievable from the Maintenance Knowledge workspace without adding vector indexing or external integrations.

## Scope

Implement a lightweight retrieval pack for controlled maintenance knowledge entries:

- active accepted knowledge entry list/search backend support
- query, equipment model, and fault code filters
- simple explainable relevance scoring
- frontend accepted knowledge retrieval panel
- tests and documentation

## Boundaries

Do not implement:

- automatic vector indexing
- Qdrant writes
- embeddings for accepted knowledge entries
- ERP/MES/OA/CMMS integration
- automatic candidate acceptance
- source document edits
- metadata mutation
- batch reindexing

## Verification

Run from `backend/`:

```bash
python -m pytest app/tests/test_maintenance_curation.py -q
python -m pytest -q
```

Run from `frontend/`:

```bash
npm install
npm run build
```

Run from repo root:

```bash
python scripts/check_agent_result.py agent/results/038_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
