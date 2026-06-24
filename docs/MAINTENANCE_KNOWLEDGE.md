# Maintenance Knowledge MVP

## Purpose

The Maintenance Knowledge MVP is a lightweight workspace for equipment fault lookup and repair guidance. It wraps the existing CoreKB maintenance assistant and does not introduce a new backend workflow engine.

## Behavior

The page collects:

- equipment model
- fault code
- symptom
- optional notes

It calls the existing assistant chat API with assistant type:

```text
maintenance
```

The default metadata filter includes:

```json
{"category": "maintenance"}
```

When equipment model or fault code is provided, the page also sends:

```json
{
  "equipment_model": "...",
  "fault_code": "..."
}
```

Rerank is enabled by default with `rerank_top_n=20` and `top_k=5`.

## Output

The UI displays:

- answer
- citations
- used metadata filter
- rerank status
- no-answer state
- top retrieved evidence when returned by the API

## Boundaries

This MVP does not:

- create an Agent
- create a Workflow
- call external tools
- connect to ERP, MES, OA, or work-order systems
- modify source documents
- modify `documents.metadata`
- create metadata suggestions
- trigger reindexing
- change prompts or rerank configuration dynamically

It is a focused UI wrapper around existing RAG, metadata filter, rerank, and citation behavior.

## Current Limits

- The assistant relies on existing indexed maintenance documents.
- It cannot guarantee an answer when no reliable maintenance evidence is retrieved.
- Structured fields are limited to equipment model and fault code in this first page.
- Follow-up tasks can add richer maintenance dashboards, repair history views, or evaluation shortcuts without changing this MVP contract.
