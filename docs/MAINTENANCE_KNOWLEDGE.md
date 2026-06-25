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
- evidence panel when retrieved evidence is returned by the API

## Evidence Panel

The evidence panel is a read-only inspection area for the retrieval context already returned by the existing assistant chat API.

It displays:

- retrieved evidence rank
- source document or citation label
- whether the chunk was cited in the answer
- final, vector, and rerank scores when available
- chunk metadata such as category, equipment model, fault code, sheet, and row range
- answer citation quote when the retrieved chunk was cited
- retrieved chunk excerpt

Users can enable a cited-only view to focus on evidence that was actually referenced by the assistant answer.

The evidence panel does not rerun search, rerank, or chat. It does not persist evidence inspection state. It only renders response data returned by the existing assistant endpoint.

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
- persist evidence inspection state

It is a focused UI wrapper around existing RAG, metadata filter, rerank, and citation behavior.

## Current Limits

- The assistant relies on existing indexed maintenance documents.
- It cannot guarantee an answer when no reliable maintenance evidence is retrieved.
- Structured fields are limited to equipment model and fault code in this first page.
- Follow-up tasks can add richer maintenance dashboards, repair history views, or evaluation shortcuts without changing this MVP contract.
