# CoreKB Current State Audit

This document records the current CoreKB state before continuing controlled self-evolution features. It is an audit of existing repository behavior, not a design for new runtime behavior.

## 1. Codex PR Workflow Status

CoreKB has a PR-only Codex workflow in place.

### Source of Truth

- `AGENTS.md` is the top-level operating guide for Codex agents.
- `agent/rules/AGENT_POLICY.md` defines agent safety policy.
- `docs/corekb_self_evolution.md` describes the controlled self-evolution loop.
- `docs/TESTING.md` documents the canonical backend test command.

### PR-Only Rule

`AGENTS.md` requires every future Codex task to:

1. Read `AGENTS.md`.
2. Read the task file under `agent/tasks/`.
3. Create a branch named `agent/task-XXX-task-name`.
4. Make only scoped changes.
5. Create `agent/results/XXX_result.md`.
6. Run canonical backend tests when required.
7. Run the agent result checker.
8. Commit changes to the task branch.
9. Open a pull request.
10. Wait for human review before merge.

Codex must not push directly to `main` or `develop`.

### PR Template

`.github/pull_request_template.md` exists and requires:

- task description
- summary
- files changed
- result file
- tests run
- test result
- runtime impact
- database impact
- risk notes
- rollback notes
- checklist confirming scoped work, result file, tests, result checker, no production data changes, and no unauthorized schema or runtime pipeline changes

### GitHub Actions

`.github/workflows/agent-ci.yml` exists and runs on pull requests. It currently:

- checks out the repository
- sets up Python 3.11
- runs `python agent/runner.py check`
- runs `python scripts/check_agent_result.py "agent/results/*_result.md"`
- installs backend dependencies from `backend/`
- runs the canonical backend tests from `backend/` with `python -m pytest -q`

The workflow sets `OTEL_SDK_DISABLED=true` for the backend test step so unit tests remain deterministic when OpenTelemetry packages are installed in CI.

### Result Checker

`scripts/check_agent_result.py` validates agent result markdown files. It requires each result file to:

- exist
- end with `_result.md`
- include the required result sections:
  - `Summary`
  - `Files Changed`
  - `Behavior Added`
  - `Tests Run`
  - `Test Result`
  - `Runtime Impact`
  - `Database Impact`
  - `Risk Notes`
  - `Rollback Notes`
  - `Open Questions`

`agent/results/RESULT_TEMPLATE.md` provides the standard result shape.

## 2. Metadata Validation Status

The read-only metadata validator lives under `backend/app/metadata/`.

### Models

`backend/app/metadata/schemas.py` defines:

- `ValidationIssue`
- `FieldSpec`
- `MetadataSchema`

`ValidationIssue` includes:

- `field`
- `code`
- `severity`
- `message`
- `current_value`
- `expected`

Current issue codes are:

- `missing_required_field`
- `invalid_type`
- `empty_value`
- `invalid_enum`
- `unknown_field`

Current severity values are:

- `info`
- `warning`
- `error`

`FieldSpec` defines field-level expectations:

- field name
- expected Python type or tuple of types
- required flag
- allowed enum values
- whether empty values are allowed

`MetadataSchema` defines the allowed field set and whether unknown fields are permitted.

### Validator

`backend/app/metadata/validation.py` defines:

- `DEFAULT_DOCUMENT_METADATA_SCHEMA`
- `validate_metadata(metadata, schema)`

The default schema is conservative. Required fields are:

- `title`
- `document_type`
- `department`
- `source`

Optional fields include:

- `author`
- `created_date`
- `version`
- `tags`
- `access_level`

The validator checks:

- required fields
- allowed field types
- allowed enum values
- empty strings
- unknown fields when configured

### Read-Only Behavior

`validate_metadata()` is deterministic and read-only. It returns `ValidationIssue[]`.

It does not:

- write database rows
- create metadata suggestions
- modify `documents.metadata`
- trigger indexing or reindexing
- call an LLM
- mutate the input metadata dictionary

## 3. Validation Reports Status

`validation_reports` is the persistence layer for read-only validation diagnostics.

### Migration and Table

`backend/alembic/versions/0019_validation_reports.py` creates the `validation_reports` table.

The table stores:

- `id`
- `document_id`
- `report_type`
- `severity`
- `issue_count`
- `issues_json`
- `summary`
- `status`
- `created_at`
- `updated_at`

Current report type:

- `metadata`

Current statuses:

- `open`
- `resolved`
- `ignored`

Current severities:

- `info`
- `warning`
- `error`

### Model, Schema, and Service

`backend/app/models/validation_report.py` defines the SQLAlchemy model and enums.

`backend/app/schemas/validation_report.py` defines read schemas for validation issues and reports.

`backend/app/services/validation_report_service.py` supports:

- creating a validation report from `ValidationIssue[]`
- computing `issue_count`
- computing highest severity
- serializing issues into `issues_json`
- getting a report by id
- listing reports by `document_id`

### Read-Only API

The current API surface is read-only:

- `GET /api/validation-reports/{report_id}`
- `GET /api/documents/{document_id}/validation-reports`

The API returns persisted diagnostics for inspection. Missing report ids return `404`; a document with no validation reports returns an empty list.

### What Validation Reports Do Not Do

Validation reports do not:

- modify `documents.metadata`
- create metadata suggestions
- accept or reject metadata suggestions
- apply fixes
- trigger indexing or reindexing
- change ingestion, embedding, retrieval, or chat behavior
- call an LLM

Creation is currently internal/service-level, not a public write API.

## 4. Metadata Suggestion Status

Metadata suggestions are an existing reviewed write path and must be treated differently from validation reports.

### Model

`backend/app/models/document.py` defines `DocumentMetadataSuggestion`.

The model stores:

- `document_id`
- `field`
- `raw_value`
- `normalized_value`
- `normalization_source`
- `dictionary_entry_id`
- `custom_value`
- `suggested_value`
- `confidence`
- `source`
- `evidence_excerpt`
- `rule_name`
- `status`
- `reviewed_by`
- `reviewed_at`
- `created_at`

Statuses:

- `pending`
- `accepted`
- `rejected`

Confidence values:

- `high`
- `medium`
- `low`

Sources:

- `filename`
- `title`
- `parsed_text`

### Generation and List APIs

Existing APIs include:

- `POST /api/documents/{document_id}/metadata-suggestions/generate`
- `GET /api/documents/{document_id}/metadata-suggestions`
- `GET /api/documents/metadata-suggestions`

Generation uses `DocumentMetadataSuggester` and rule-based extraction from:

- filename
- document title
- parsed text

Generation requires the document to be parsed or indexed. It creates pending suggestions but does not automatically write accepted values into `documents.metadata`.

### Accept and Reject APIs

Existing APIs include:

- `POST /api/documents/{document_id}/metadata-suggestions/{suggestion_id}/accept`
- `POST /api/documents/{document_id}/metadata-suggestions/{suggestion_id}/reject`

Accept behavior:

- requires edit permission on the document knowledge base
- normalizes the accepted value unless `custom_value=true`
- writes the accepted value into `documents.metadata` through the SQLAlchemy `Document.meta` attribute
- marks the suggestion as `accepted`
- records reviewer fields
- resets document indexing state to `uploaded`
- clears document error and indexed timestamp
- creates a document index job
- enqueues reindexing
- records an audit log action `document.metadata_suggestion.accept`

Reject behavior:

- requires edit permission
- marks the suggestion as `rejected`
- records reviewer fields
- records an audit log action `document.metadata_suggestion.reject`
- does not modify `documents.metadata`
- does not trigger reindexing

### Audit Behavior

The metadata suggestion routes record audit events for:

- suggestion generation
- suggestion acceptance
- suggestion rejection

Acceptance audit metadata includes the accepted field, accepted safe value, suggestion id, index job id, whether reindexing was triggered, and whether a custom value was used. Reject audit metadata includes the field, suggestion id, and rejected suggestion status. Generate audit metadata stores suggestion count only; the target document id is recorded on the audit log record itself.

### Risks and Boundaries

Metadata suggestions are not purely advisory once accepted. Acceptance is an explicit production-impacting operation because it writes document metadata and triggers reindexing.

Current boundaries:

- suggestion generation is advisory
- acceptance must remain explicit and permission-checked
- rejection remains non-mutating for document metadata
- automatic suggestion creation must not imply automatic acceptance
- bulk acceptance is not safe until stronger guardrails and tests exist
- validation reports must not silently become accepted suggestions

Known risk areas to protect:

- accidental acceptance of low-confidence or stale suggestions
- custom values bypassing dictionary normalization
- reindexing on metadata acceptance affecting retrieval behavior
- audit payloads needing to remain free of secrets and full document contents
- ensuring accepted values are traceable to a reviewer and source evidence

## 5. Controlled Self-Evolution Status

CoreKB has several advisory and reviewed components that can support controlled self-evolution.

### Safe Now

The following are safe as advisory or reviewed operations:

- run `validate_metadata()` and inspect `ValidationIssue[]`
- persist validation reports as diagnostics
- read validation reports through the API
- generate metadata suggestions for human review
- list pending or historical metadata suggestions
- manually accept or reject a single metadata suggestion with permissions and audit logging
- run metadata precheck as a read-only scan
- use evaluation, failed-case analysis, drill-down, annotations, improvement items, regressions, and trends as evidence
- use agent PR workflow for reviewable repository changes

### Not Safe Yet

The following are not safe without additional scoped work:

- automatic conversion of validation reports into accepted suggestions
- automatic acceptance of metadata suggestions
- bulk metadata repair
- automated prompt rewrites
- automated chunking or rerank parameter changes
- automatic reindexing from advisory reports
- LLM-generated metadata writes without human review
- unsupervised mutation of production document metadata
- direct Codex pushes to protected branches

### Must Not Be Automated

The following must remain human-reviewed:

- production writes to `documents.metadata`
- accepting metadata suggestions
- source document changes
- dictionary changes that affect canonical metadata values
- prompt changes that affect answer behavior
- chunking and rerank configuration changes
- migration or schema changes
- production reindexing from metadata changes
- deletion or mutation of audit evidence

Automatic suggestions are evidence, not authority.

## 6. Recommended Next Phases

### Phase 1: Safety Tests Around Existing Metadata Suggestion Logic

Add focused tests that prove:

- generation does not write `documents.metadata`
- generation does not enqueue reindexing
- accept writes exactly one expected field
- accept creates exactly one reindex job
- reject does not write metadata or enqueue reindexing
- low-confidence suggestions cannot be bulk-applied because no bulk apply path exists
- audit records are created without secrets or full document contents

### Phase 2: Suggestion Review Guardrails

Add review constraints before any broader suggestion workflow:

- require visible evidence excerpt
- show current formal metadata value beside suggested value
- distinguish dictionary match, rule normalization, and fallback
- require explicit `custom_value=true` for non-standard values
- prevent unsupported fields from being accepted
- warn when accepting a value will trigger reindexing

### Phase 3: Audit Log Hardening

Strengthen audit guarantees for production-impacting actions:

- keep metadata accept/reject/generate actions covered by tests for request traceability and safe metadata boundaries
- ensure audit payloads contain field names, suggestion ids, index job ids, reindex markers, custom value markers, and redacted values only where needed
- ensure no API keys, passwords, tokens, secrets, evidence excerpts, parsed text, file content, or full source document text enter audit metadata
- keep tests for audit record creation and redaction boundaries current as metadata review evolves

### Phase 4: Validation-Report-to-Suggestion Bridge

Build a bridge only after guardrails are in place:

- read validation reports
- generate candidate suggestions from report issues
- persist suggestions as pending only
- never auto-accept suggestions
- keep source report ids for traceability
- require reviewer action before any metadata write

### Phase 5: Eval Runner

Connect the agent `eval` placeholder to a stable read-only evaluation command:

- run fixtures-based retrieval and assistant evaluation
- write evaluation output without mutating production data
- compare metrics across runs
- surface regressions for human review
- keep evaluation separate from automatic production changes

## Summary

CoreKB has a functioning PR-only agent workflow, a read-only metadata validator, persisted read-only validation reports, and a separate reviewed metadata suggestion path that can write metadata only after explicit acceptance. The next self-evolution steps should focus on safety tests, guardrails, audit hardening, and traceable advisory-to-review bridges before adding any automation that affects production behavior.

