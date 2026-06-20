# Task 019: Evaluation Failure Triage

## Goal

Add a lightweight, read-only failure triage view for the latest retrieval and assistant evaluation results.

The view should help reviewers quickly see which failed cases are likely related to retrieval, metadata, rerank, chunking, citations, or no-answer behavior before they open the full evaluation workbench.

## Scope

Allowed paths:

- `frontend/src/`
- `docs/`
- `agent/tasks/`
- `agent/results/`

Do not modify:

- backend runtime code
- database models
- migrations
- ingestion, indexing, retrieval, or embedding pipelines
- production configuration
- tests, unless only workflow documentation requires it

## Requirements

1. Add an admin-only frontend page for evaluation failure triage.
2. Use existing read-only evaluation APIs.
3. Show failed retrieval and assistant cases from the latest runs.
4. Provide simple filters for source, assistant type, failure reason, suggested fix type, and keyword.
5. Show summary counts by likely failure category.
6. Link back to the existing Evaluation workbench and annotation search where useful.
7. Document that the triage page is advisory and does not mutate production data.

## Hard Constraints

- Do not add backend endpoints.
- Do not create database migrations.
- Do not write evaluation data.
- Do not create or update annotations.
- Do not create improvement items.
- Do not run Search, Chat, Rerank, or LLM calls from the triage page.
- Do not modify production metadata, prompts, chunking, rerank configuration, or indexing behavior.

## Acceptance Criteria

- The page appears in the admin navigation.
- The page loads latest retrieval and assistant evaluation failures.
- The page handles loading, error, empty, and filtered-empty states.
- Frontend build passes.
- Canonical backend tests still pass.
- Agent result checker passes.
