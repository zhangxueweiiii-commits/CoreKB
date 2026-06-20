# Read-Only Metadata Validation

CoreKB includes a small metadata validation layer for checking metadata quality before later reporting or suggestion workflows are introduced.

The validator is read-only. It does not:

- Write validation reports to the database.
- Create metadata suggestions.
- Modify `documents.metadata`.
- Trigger indexing or reindexing.
- Change ingestion, embedding, retrieval, or chat behavior.
- Call an LLM.

## Default Schema

The first baseline schema is intentionally conservative.

Required fields:

- `title`
- `document_type`
- `department`
- `source`

Optional fields:

- `author`
- `created_date`
- `version`
- `tags`
- `access_level`

Allowed `document_type` values:

- `manual`
- `policy`
- `report`
- `work_order`
- `invoice`
- `bom`
- `unknown`

Allowed `access_level` values:

- `public`
- `internal`
- `restricted`
- `confidential`

## Validation Issues

The validator returns structured issues with:

- `field`
- `code`
- `severity`
- `message`
- `current_value`
- `expected`

Current issue codes:

- `missing_required_field`
- `invalid_type`
- `empty_value`
- `invalid_enum`
- `unknown_field`

Severity values:

- `info`
- `warning`
- `error`

## Usage

```python
from app.metadata import DEFAULT_DOCUMENT_METADATA_SCHEMA, validate_metadata

issues = validate_metadata(metadata, DEFAULT_DOCUMENT_METADATA_SCHEMA)
```

The function is deterministic and does not mutate the input dictionary.

## Future Direction

Later tasks can build database-backed validation reports, metadata suggestions, and review workflows on top of this module. Those future workflows must keep automatic suggestions advisory unless a scoped task explicitly adds a reviewed write path.

## Validation Reports

`validation_reports` is the first persistence layer for metadata validation output. It stores diagnostic records created from `ValidationIssue[]`.

Validation reports are read-only diagnostics. They do not:

- Modify `documents.metadata`.
- Create metadata suggestions.
- Accept, reject, or apply fixes.
- Trigger indexing or reindexing.
- Change ingestion, embedding, retrieval, or chat behavior.

Each report stores:

- The target `document_id`.
- The report type, currently `metadata`.
- The highest issue severity.
- The issue count.
- Structured `issues_json`.
- An optional summary.
- A review status: `open`, `resolved`, or `ignored`.

The table is intended for future review workflows and dashboards. It is not a suggestion engine and does not mutate source metadata.

## Read-Only Validation Report API

CoreKB exposes read-only validation report inspection endpoints:

```http
GET /api/validation-reports/{report_id}
GET /api/documents/{document_id}/validation-reports
```

These endpoints return persisted diagnostic reports for review and future admin UI usage. They include:

- `status`
- `severity`
- `issue_count`
- `issues_json`
- `summary`
- `created_at`
- `updated_at`

The API does not:

- Create validation reports.
- Modify `documents.metadata`.
- Create metadata suggestions.
- Accept, reject, or apply fixes.
- Trigger indexing or reindexing.
- Change ingestion, embedding, retrieval, or chat behavior.

Missing report ids return `404`. A document with no validation reports returns an empty list.

## Validation Report to Pending Suggestion Bridge

Validation reports can now be used as a source for pending metadata suggestions:

```http
POST /api/validation-reports/{report_id}/metadata-suggestions
```

This bridge is intentionally narrow:

- It reads persisted `issues_json` from an existing metadata validation report.
- It creates `document_metadata_suggestions` with `status=pending` only.
- It keeps the source validation report id in the suggestion evidence excerpt.
- It deduplicates against existing suggestions for the same document, field, and suggested value.
- It skips unsupported fields and issues without a safe current value.

The bridge does not:

- Modify `documents.metadata`.
- Accept or reject metadata suggestions.
- Trigger indexing or reindexing.
- Parse source files.
- Read Qdrant payloads.
- Call an LLM.
- Store full source document content in suggestions or audit metadata.

Administrators or editors must still review each pending suggestion and explicitly accept or reject it through the normal metadata suggestion review API. Only acceptance writes formal metadata and submits a reindex job.

Supported field mapping is conservative. The first bridge version supports the normal CoreKB metadata suggestion fields and maps generic validation `document_type` to CoreKB `doc_type`.
## Validation Report Review UI

The document detail view shows validation reports for the selected document. Reviewers can inspect:

- report type
- severity
- status
- summary
- issue count
- individual issue fields, codes, current values, expected values, and messages

Admins and editors can click `Create pending suggestions` on a report. This calls the validation-report bridge and displays how many pending suggestions were created, how many already existed, and how many issues were skipped.

The review UI does not:

- accept suggestions automatically
- modify `documents.metadata`
- trigger reindexing
- create validation reports
- parse files
- call an LLM

It is a human review surface for existing diagnostics and pending suggestion creation only. Formal metadata changes still require explicit acceptance through the metadata suggestion review controls.

## Closed-Loop Verification

CoreKB has backend tests that verify the metadata validation review loop end to end:

```text
validation report -> pending suggestion bridge -> explicit accept/reject
```

The verification checks that the advisory bridge remains non-mutating:

- creating pending suggestions from a validation report does not modify `documents.metadata`
- creating pending suggestions from a validation report does not create index jobs
- creating pending suggestions from a validation report does not enqueue reindexing
- accepting a suggestion explicitly writes only the reviewed metadata field
- accepting a suggestion creates and enqueues one single-document index job
- rejecting a suggestion preserves metadata and index state
- audit logs distinguish report bridge generation, acceptance, and rejection

These tests are intentionally separate from UI tests. They protect the production boundary between advisory diagnostics and reviewed metadata changes.

