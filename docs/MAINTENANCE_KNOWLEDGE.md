# Maintenance Knowledge Curation

## Purpose

The Maintenance Knowledge workspace supports equipment fault lookup, evidence review, controlled record drafting, and human-reviewed maintenance knowledge curation. It wraps the existing CoreKB maintenance assistant and keeps the workflow explicit and auditable.

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
- maintenance record draft save/copy workflow
- maintenance experience candidate save/review workflow
- pending candidate review and accept/reject actions
- accepted maintenance knowledge retrieval

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

## Maintenance Record Draft

The Maintenance page can generate a local repair record draft after the assistant returns an answer.

The draft includes:

- equipment model and fault code entered by the user
- reported symptom and site notes
- assistant guidance
- no-answer state
- used metadata filter
- rerank status
- citations
- top retrieved evidence summaries
- an operator confirmation checklist

The draft is intended for review in an existing maintenance process. It can be saved in CoreKB as a `maintenance_record_drafts` record, but it is not a work order and is not sent to ERP, MES, OA, CMMS, or ticket systems.

Saving a draft records an audit event:

```text
maintenance.record_draft.create
```

## Maintenance Experience Candidate

The Maintenance page can also generate a local experience candidate from the current answer and evidence.

The candidate includes:

- candidate title
- maintenance category
- equipment model and fault code
- observed symptom
- candidate experience summary
- applicability guardrails
- source citations
- supporting evidence
- curation checks

This is a drafting aid for future knowledge curation. It is explicitly marked as pending and not approved knowledge. A maintenance owner or reviewer must review the source citations, applicability, and safety constraints before accepting it.

Saving a candidate creates a pending `maintenance_experience_candidates` record and records an audit event:

```text
maintenance.experience_candidate.create
```

## Candidate Review

Pending candidates can be explicitly accepted or rejected.

Rejecting a candidate:

- keeps the candidate stored for audit/history
- records reviewer note, reviewer, and review time
- does not create a knowledge entry

Accepting a candidate:

- records reviewer note, reviewer, and review time
- creates a controlled `maintenance_knowledge_entries` record
- sets the knowledge entry status to `active`
- links the entry to the source candidate

Review actions record audit events:

```text
maintenance.experience_candidate.accept
maintenance.experience_candidate.reject
maintenance.knowledge_entry.create
```

Accepted entries do not overwrite manuals, SOPs, source documents, or document metadata. This first version does not automatically index accepted entries; indexing can be added later as a normal single-entry indexing path with its own audit and tests.

## Accepted Knowledge Retrieval

Accepted maintenance knowledge entries can be searched from the Maintenance page.

The retrieval pack searches controlled `maintenance_knowledge_entries` records with status `active`. It supports:

- free-text query
- equipment model filter
- fault code filter
- lightweight relevance scoring
- matched field display

The first retrieval version is SQL-backed and read-only. It does not query Qdrant, create embeddings, modify accepted entries, modify source documents, modify metadata, or trigger indexing. Pending and rejected candidates are not returned by accepted knowledge retrieval.

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
- create work orders or repair tickets
- update source documents or formal knowledge entries
- automatically accept candidates
- batch process candidates
- batch reindex
- vector-index accepted knowledge entries automatically

It is a focused UI wrapper around existing RAG, metadata filter, rerank, and citation behavior.

## Current Limits

- The assistant relies on existing indexed maintenance documents.
- It cannot guarantee an answer when no reliable maintenance evidence is retrieved.
- Structured fields are limited to equipment model and fault code in this first page.
- Follow-up tasks can add richer maintenance dashboards, repair history views, or evaluation shortcuts without changing this MVP contract.
