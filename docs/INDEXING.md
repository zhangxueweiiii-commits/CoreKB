# CoreKB Indexing Operations

## Single-Document Reprocess / Reindex UX

The knowledge base document UI exposes a single-document reprocess action for documents that the existing backend retry endpoint accepts:

- `failed`
- `uploaded`
- `parsed`
- `indexed` when the request explicitly sets `force=true`

The action uses:

```http
POST /api/documents/{document_id}/retry-indexing
```

For failed/uploaded/parsed documents, the request can be sent without a body or with:

```json
{"force": false}
```

For already indexed documents, the request must explicitly set:

```json
{"force": true}
```

Before submission, the UI shows a confirmation prompt. Indexed documents get a stronger force confirmation because the document is reset to the normal indexing flow and existing chunks/vectors are replaced by the worker. After submission, the UI displays the created index job id and lets the user open the job detail page when the current page has an index-job navigation callback.

For non-eligible states, the UI explains why the action is disabled:

- actively processing documents are already in the indexing pipeline
- indexed documents require explicit force reprocess
- other states are not accepted by the retry endpoint

This UX reuses the existing retry-indexing endpoint. It does not add endpoints, change worker logic, modify chunks or vectors directly, or alter metadata suggestion review behavior.

## Current Limits

- The action is cooperative with the existing backend job system.
- It cannot force-kill an active worker task.
- It can reprocess indexed documents only with `force=true`.
- It does not provide batch selection; knowledge-base reindex remains the batch operation.
