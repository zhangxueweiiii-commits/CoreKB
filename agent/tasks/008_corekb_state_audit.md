# Task 008: CoreKB State Audit

## Goal

Create a clear current-state audit document for CoreKB before continuing self-evolution features.

## Scope

Documentation only.

Allowed paths:

- `agent/tasks/`
- `agent/results/`
- `docs/`

Do not modify:

- backend runtime code
- frontend runtime code
- database models
- migrations
- ingestion, indexing, retrieval, or embedding
- production config
- tests

## Required Files

- `agent/tasks/008_corekb_state_audit.md`
- `docs/COREKB_STATE.md`
- `agent/results/008_result.md`

## Audit Coverage

The audit document must cover:

1. Current Codex PR workflow status
   - `AGENTS.md`
   - PR template
   - GitHub Actions
   - result checker
   - required PR-only workflow
2. Current metadata validation status
   - `ValidationIssue`
   - `FieldSpec`
   - `MetadataSchema`
   - `validate_metadata()`
   - read-only behavior
3. Current `validation_reports` status
   - migration/table
   - model/schema/service
   - read-only API
   - what it does not do
4. Current metadata suggestion status
   - existing `DocumentMetadataSuggestion` model
   - existing generate/list/accept/reject APIs
   - existing accept behavior writes `documents.metadata`
   - existing accept behavior triggers reindex
   - existing audit behavior
   - risks and boundaries
5. Current controlled self-evolution status
   - what is safe now
   - what is not safe yet
   - what must not be automated
6. Recommended next phases
   - safety tests around existing metadata suggestion logic
   - suggestion review guardrails
   - audit log hardening
   - validation-report-to-suggestion bridge
   - eval runner

## Verification

Run:

```bash
python scripts/check_agent_result.py agent/results/008_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```

For this documentation-only task, do not run full backend tests unless the repository workflow requires it.

