# CoreKB Metadata

CoreKB uses document metadata to improve retrieval precision, metadata filters, rerank evaluation, and role assistant quality. Metadata is stored on `documents.metadata`, merged into chunk metadata during indexing, and written into Qdrant payloads.

## Supported Fields

The first metadata review stage supports only these fields:

- `category`
- `doc_type`
- `equipment_model`
- `fault_code`
- `material_code`
- `product_model`
- `process_name`
- `sop_code`
- `version`
- `effective_date`

## Suggestion Flow

1. Admin or editor opens a document detail page.
2. Click `Generate metadata suggestions`.
3. CoreKB reads filename, detected document title, and parsed text.
4. Rule-based candidates are stored in `document_metadata_suggestions`.
5. Admin or editor accepts or rejects one suggestion at a time.
6. Accepted values are written to `documents.metadata`.
7. CoreKB submits a single-document indexing job so new metadata reaches chunks and Qdrant payloads.

Suggestions never overwrite formal document metadata automatically. Existing formal values are displayed beside candidate values so reviewers can decide whether to accept, reject, or override the accepted value.

## Suggestion Data

Each suggestion contains:

- `field`
- `suggested_value`
- `confidence`: `high`, `medium`, `low`
- `source`: `filename`, `title`, `parsed_text`
- `evidence_excerpt`
- `rule_name`
- `status`: `pending`, `accepted`, `rejected`
- `reviewed_by`
- `reviewed_at`
- `created_at`

The uniqueness rule is:

```text
document_id + field + suggested_value
```

Repeated generation does not create duplicate suggestions.

## Rule-Based Extraction

Current extraction is conservative and does not call an LLM.

Supported examples:

- Equipment model: `A200`, `A-200`, `EQ-A200`
- Fault code: `E12`, `E-12`, `ERR12`, `Error 12`, `故障码 E12`
- Material code: `MAT-001`, `M001`, `WL-1001`
- SOP code: `SOP-001`, `SOP001`, `作业指导书 SOP-001`
- Version: `V1.0`, `Rev.A`, `版本 2.1`
- Document type keywords: `维修手册`, `作业指导书`, `检验规范`, `物料规格书`, `产品参数表`

## Normalization

Examples:

- `A-200` -> `A200`
- `ERR12`, `Error 12`, `E-12` -> `E12`
- `SOP001` -> `SOP-001`
- Material and product codes are uppercased.
- Version values are trimmed and uppercased where appropriate.

## Completeness Hints

Metadata completeness is a non-blocking hint.

Recommended fields:

- `maintenance`: `equipment_model`, plus `fault_code` or `process_name`
- `quality`: `doc_type`, `version`, `effective_date`
- `sop`: `sop_code`, `process_name`, `version`
- `material`: `material_code` or `product_model`, plus `version`

Status values:

- `complete`: all recommended groups are present.
- `partial`: some recommended fields are present.
- `missing`: no recommended category-specific fields are present, or category/doc type is unknown.

## API

Generate suggestions:

```http
POST /api/documents/{document_id}/metadata-suggestions/generate
```

List document suggestions:

```http
GET /api/documents/{document_id}/metadata-suggestions
```

Accept:

```http
POST /api/documents/{document_id}/metadata-suggestions/{suggestion_id}/accept
Content-Type: application/json

{"value": "A200"}
```

Reject:

```http
POST /api/documents/{document_id}/metadata-suggestions/{suggestion_id}/reject
```

Global suggestion list:

```http
GET /api/documents/metadata-suggestions?status=pending&field=equipment_model&knowledge_base_id={kb_id}
```

## Why Reindex After Accept

CoreKB copies document metadata into chunk metadata during indexing and then writes the same metadata into Qdrant payloads. If a metadata value is accepted but the document is not reindexed, metadata filters would still search stale Qdrant payloads.

## Current Limits

- No LLM extraction.
- No automatic acceptance.
- No automatic overwrite of human metadata.
- Single-document, single-suggestion review only.
- No batch review.
- No metadata approval workflow.
- No complex metadata versioning.
- Batch review and LLM-assisted suggestions can be considered later.
