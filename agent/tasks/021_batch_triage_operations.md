# Task 021: Batch Triage Operations

## Goal

Add lightweight batch operations to the Evaluation Failure Triage workflow so admins can update triage status and notes for multiple failed evaluation case results at once.

## Scope

Allowed changes:

- backend evaluation triage note schemas, service, route, and tests
- frontend evaluation failure triage API/page/styles
- docs
- agent result file

Do not modify ingestion, embedding, indexing, retrieval, metadata mutation paths, database models, migrations, production config, or unrelated application behavior.

## Requirements

1. Add an admin-only batch triage note endpoint.
2. Support selecting multiple case results in the failure triage page.
3. Support batch status changes.
4. Support batch note modes: replace, append, keep.
5. Keep triage notes advisory only.
6. Do not create annotations, improvement items, suggestions, evaluation runs, or indexing jobs.
7. Add tests for batch behavior and safety boundaries.
8. Update docs and create `agent/results/021_result.md`.
