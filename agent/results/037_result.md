# Task 037 Result

## Summary

Added Maintenance Knowledge Curation Pack V1: persisted maintenance record drafts, persisted maintenance experience candidates, human accept/reject review, accepted maintenance knowledge entries, audit logging, and frontend save/review controls.

## Files Changed

- `agent/tasks/037_maintenance_knowledge_curation_pack_v1.md`
- `agent/results/037_result.md`
- `backend/alembic/versions/0021_maintenance_curation.py`
- `backend/app/api/routes/maintenance.py`
- `backend/app/db/base.py`
- `backend/app/main.py`
- `backend/app/models/maintenance.py`
- `backend/app/schemas/maintenance.py`
- `backend/app/services/maintenance_curation_service.py`
- `backend/app/tests/conftest.py`
- `backend/app/tests/test_maintenance_curation.py`
- `docs/MAINTENANCE_KNOWLEDGE.md`
- `frontend/src/api/client.ts`
- `frontend/src/pages/MaintenanceKnowledgePage.tsx`
- `frontend/src/styles.css`

## Behavior Added

- Users can save maintenance record drafts from the Maintenance Knowledge page.
- Users can save maintenance experience candidates from reviewed assistant answers and evidence.
- Pending candidates can be listed, accepted, or rejected from the Maintenance page.
- Accepting a candidate creates a controlled active maintenance knowledge entry.
- Rejecting a candidate keeps the candidate for audit/history and does not create a knowledge entry.
- Audit logs are recorded for draft creation, candidate creation, candidate acceptance, candidate rejection, and knowledge entry creation.
- The workflow does not modify source documents, `documents.metadata`, metadata suggestions, or indexing jobs.

## Tests Run

- `python -m pytest app/tests/test_maintenance_curation.py -q`
- `npm install`
- `npm run build`
- `python -m pytest -q`
- `python scripts/check_agent_result.py agent/results/037_result.md`
- `python scripts/check_agent_result.py "agent/results/*_result.md"`
- `python agent/runner.py check`

## Test Result

- Maintenance curation tests passed: 5 passed.
- Frontend build passed.
- Backend tests passed: 347 passed, 1 skipped, 15 warnings.
- Agent result checks passed.
- Agent runner check passed.

## Runtime Impact

Adds authenticated maintenance curation API endpoints and frontend controls for saving drafts, saving candidates, and reviewing pending candidates. No external system integration, source document mutation, metadata mutation, or automatic indexing is introduced.

## Database Impact

Adds a backward-compatible Alembic migration creating:

- `maintenance_record_drafts`
- `maintenance_experience_candidates`
- `maintenance_knowledge_entries`

No existing tables are modified.

## Risk Notes

- Accepted knowledge entries are persisted but not indexed in this first version.
- Candidate review permissions are limited to admin/editor roles; save actions are available to authenticated users.
- The UI is intentionally lightweight and not a full CMMS/work-order workflow.
- PR is stacked on Task 036 because Tasks 035 and 036 were still open when this work began.

## Rollback Notes

Revert this PR and downgrade migration `0021_maintenance_curation` to remove the maintenance curation tables and API/UI additions.

## Open Questions

- Should accepted maintenance knowledge entries later get their own single-entry indexing pipeline with explicit audit and retry support?
