# Task 038 Result

## Summary

Added Maintenance Knowledge Retrieval Pack V1 so accepted maintenance knowledge entries can be searched from the Maintenance Knowledge page with query, equipment model, and fault code filters.

## Files Changed

- `agent/tasks/038_maintenance_knowledge_retrieval_pack_v1.md`
- `agent/results/038_result.md`
- `backend/app/api/routes/maintenance.py`
- `backend/app/schemas/maintenance.py`
- `backend/app/services/maintenance_curation_service.py`
- `backend/app/tests/test_maintenance_curation.py`
- `docs/MAINTENANCE_KNOWLEDGE.md`
- `frontend/src/api/client.ts`
- `frontend/src/pages/MaintenanceKnowledgePage.tsx`
- `frontend/src/styles.css`

## Behavior Added

- Added read-only accepted maintenance knowledge entry listing/search support.
- Added SQL-backed retrieval over active `maintenance_knowledge_entries`.
- Supports free-text query, equipment model filter, fault code filter, limit, lightweight score, and matched field explanations.
- Added Maintenance page retrieval panel for accepted knowledge results.
- Pending and rejected candidates are not returned by accepted knowledge retrieval.

## Tests Run

- `python -m pytest app/tests/test_maintenance_curation.py -q`
- `npm install`
- `npm run build`
- `python -m pytest -q`
- `python scripts/check_agent_result.py agent/results/038_result.md`
- `python scripts/check_agent_result.py "agent/results/*_result.md"`
- `python agent/runner.py check`

## Test Result

- Maintenance curation tests passed: 8 passed.
- Frontend build passed.
- Backend tests passed: 350 passed, 1 skipped, 16 warnings.
- Agent result checks passed.
- Agent runner check passed.

## Runtime Impact

Adds read-only maintenance knowledge retrieval endpoints and frontend search UI. It does not write accepted entries, source documents, metadata, vector indexes, or indexing jobs.

## Database Impact

None. No new migration or database schema change was added in this task.

## Risk Notes

- Retrieval is SQL-backed and lightweight; it is not semantic vector retrieval.
- Scoring is explainable but simple, intended as V1 behavior over controlled accepted entries.
- PR is stacked on Task 037 because Tasks 035, 036, and 037 were still open when this work began.

## Rollback Notes

Revert this PR to remove the read-only accepted maintenance knowledge search API/UI while keeping the Task 037 curation data model intact.

## Open Questions

- Should a later task add explicit single-entry vector indexing for accepted maintenance knowledge entries?
