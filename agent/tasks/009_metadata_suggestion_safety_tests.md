# Task 009: Metadata Suggestion Safety Tests

## Goal

Add safety-focused tests around the existing metadata suggestion workflow.

## Scope

Testing and agent workflow documentation only.

Allowed paths:

- `backend/app/tests/`
- `agent/tasks/`
- `agent/results/`

Do not modify:

- backend runtime code
- frontend runtime code
- database models
- migrations
- ingestion, indexing, retrieval, or embedding
- production config

## Requirements

Add tests proving the existing metadata suggestion workflow keeps clear boundaries:

- generating suggestions does not modify `documents.metadata`
- generating suggestions does not create index jobs or enqueue reindexing
- rejecting a suggestion does not modify metadata, create index jobs, or enqueue reindexing
- accepting a suggestion writes only the accepted metadata field and preserves unrelated metadata
- accepting a suggestion creates one document index job and enqueues that job
- accepting or generating suggestions records audit entries without storing full source content
- unsupported suggestion fields cannot be accepted and do not mutate metadata or indexing state
- viewer users cannot generate suggestions

## Non-Goals

- Do not change metadata suggestion behavior.
- Do not add new metadata suggestion features.
- Do not add migrations.
- Do not change production configuration.
- Do not add frontend UI.

## Verification

Run:

```bash
python -m pytest app/tests/test_metadata_suggestion_safety.py -q
python -m pytest app/tests/test_document_metadata_suggestions.py app/tests/test_metadata_suggestion_safety.py -q
python -m pytest -q
python scripts/check_agent_result.py agent/results/009_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```

