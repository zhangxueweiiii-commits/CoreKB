# CoreKB Indexing Operations

## Single-Document Reprocess / Reindex UX

The knowledge base document UI exposes a single-document reprocess action for documents that the existing backend retry endpoint accepts:

- `failed`
- `uploaded`
- `parsed`

The action uses:

```http
POST /api/documents/{document_id}/retry-indexing
```

Before submission, the UI shows a confirmation prompt. After submission, it displays the created index job id and lets the user open the job detail page when the current page has an index-job navigation callback.

For non-eligible states, the UI explains why the action is disabled:

- actively processing documents are already in the indexing pipeline
- indexed documents should use knowledge-base reindex if a full rebuild is needed
- other states are not accepted by the retry endpoint

This UX does not change backend indexing behavior. It does not add endpoints, change worker logic, modify chunks or vectors directly, or alter metadata suggestion review behavior.

## Current Limits

- The action is cooperative with the existing backend job system.
- It cannot force-kill an active worker task.
- It does not reprocess already indexed documents through the retry endpoint.
- It does not provide batch selection; knowledge-base reindex remains the batch operation.
