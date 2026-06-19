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
