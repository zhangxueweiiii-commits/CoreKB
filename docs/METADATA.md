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
- `raw_value`
- `normalized_value`
- `normalization_source`
- `dictionary_entry_id`
- `suggested_value`
- `confidence`: `high`, `medium`, `low`
- `source`: `filename`, `title`, `parsed_text`
- `evidence_excerpt`
- `rule_name`
- `status`: `pending`, `accepted`, `rejected`
- `reviewed_by`
- `reviewed_at`
- `created_at`
- `current_value`
- `review_guardrails`

The uniqueness rule is:

```text
document_id + field + suggested_value
```

Repeated generation does not create duplicate suggestions.

## Review Guardrails

Metadata suggestions are advisory until an admin or editor explicitly accepts one. The API returns a `review_guardrails` object for each suggestion so review UIs can show the same safety context consistently.

Current guardrail fields:

- `requires_evidence_review`: reviewers should inspect `evidence_excerpt` before accepting.
- `requires_current_value_review`: the target field already has a formal value in `documents.metadata`.
- `requires_custom_value_flag`: the value came from fallback normalization, so non-standard manual overrides must use `custom_value=true`.
- `reindex_required_on_accept`: accepting writes document metadata and submits a single-document reindex.
- `warnings`: human-readable review warnings.
- `checklist`: stable review checklist items.

Accepting a manual override that cannot be matched by dictionary or rule normalization now requires:

```json
{"value": "Plant custom value", "custom_value": true}
```

This keeps custom values explicit and prevents accidental fallback values from being treated as standard metadata. Generated fallback suggestions can still be accepted as-is, but reviewer UIs should display the fallback warning.

## Rule-Based Extraction

Current extraction is conservative and does not call an LLM.

Supported examples:

- Equipment model: `A200`, `A-200`, `EQ-A200`
- Fault code: `E12`, `E-12`, `ERR12`, `Error 12`, `故障�?E12`
- Material code: `MAT-001`, `M001`, `WL-1001`
- SOP code: `SOP-001`, `SOP001`, `作业指导�?SOP-001`
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

Keep a custom non-standard value:

```http
POST /api/documents/{document_id}/metadata-suggestions/{suggestion_id}/accept
Content-Type: application/json

{"value": "Plant custom A200", "custom_value": true}
```

Reject:

```http
POST /api/documents/{document_id}/metadata-suggestions/{suggestion_id}/reject
```

Global suggestion list:

```http
GET /api/documents/metadata-suggestions?status=pending&field=equipment_model&knowledge_base_id={kb_id}
```

Create pending suggestions from a validation report:

```http
POST /api/validation-reports/{report_id}/metadata-suggestions
```

This bridge reads persisted validation report issues and creates pending metadata suggestions for supported fields only. It does not accept suggestions, does not modify `documents.metadata`, and does not trigger reindexing. Reviewers must still inspect and accept or reject each suggestion explicitly.

## Why Reindex After Accept

CoreKB copies document metadata into chunk metadata during indexing and then writes the same metadata into Qdrant payloads. If a metadata value is accepted but the document is not reindexed, metadata filters would still search stale Qdrant payloads.

## Metadata Suggestion Audit Logs

CoreKB records audit logs for metadata suggestion generation, acceptance, and rejection.

Generation audit metadata stores only:

- `suggestion_count`

The target document is recorded through the audit log `document_id` field, so it is not duplicated in metadata.

Acceptance audit metadata stores traceability fields:

- `field`
- `value`
- `suggestion_id`
- `index_job_id`
- `reindex_triggered`
- `custom_value`

Reject audit metadata stores:

- `field`
- `suggestion_id`
- `rejected_status`

Audit metadata must not store full source document content, parsed text, file content, evidence excerpts, API keys, passwords, tokens, or secrets. Sensitive metadata keys are redacted before audit records are persisted.

## Current Limits

- No LLM extraction.
- No automatic acceptance.
- No automatic overwrite of human metadata.
- Single-document, single-suggestion review only.
- No batch review.
- No metadata approval workflow.
- No complex metadata versioning.
- Batch review and LLM-assisted suggestions can be considered later.

## Excel / CSV Deep Parsing V1

CoreKB supports first-version deep parsing for table documents through `DocumentParser` and `TableParser`.

Supported formats:

- `.csv`
- `.xlsx`
- `.xls` when the installed pandas engine can read it

Table parsing produces `ParsedSection` records with readable row-oriented text. Each section repeats table context so retrieval chunks remain understandable without the original file open:

```text
File: products.csv
Sheet: CSV
Rows: 2-3
Columns: model, voltage, power

Row 2:
model: A100
voltage: 220V
power: 500W

Row 3:
model: A200
voltage: 380V
power: 1200W
```

Each table section includes metadata:

- `source_type = table`
- `sheet_name`
- `row_start`
- `row_end`
- `column_names`
- `table_index`
- `source_range`

Chunking behavior:

- table sections are kept as table-aware chunks
- the normal character-overlap chunker does not split table sections again
- long tables are split by row groups before chunking
- every row-group section repeats file, sheet, row range, and column headers

Header handling:

- blank headers become `Column N`
- duplicate headers become stable suffixed names such as `model_2`
- empty data rows are skipped
- empty Excel sheets are skipped

Current limits:

- V1 does not infer merged-cell table structure.
- V1 does not detect multiple independent tables inside one sheet.
- V1 does not evaluate formulas; it reads values as exposed by pandas/openpyxl.
- V1 does not create metadata suggestions or modify `documents.metadata`.
- V1 does not change indexing or retrieval behavior beyond producing cleaner parsed table sections for the existing pipeline.

## Table Document Preview & Row Citation

CoreKB exposes a read-only table preview for uploaded `.csv`, `.xlsx`, and `.xls` documents:

```text
GET /api/documents/{document_id}/table-preview?max_rows=50
```

The preview reads the stored source file and returns:

- document id, filename, and file type
- sheet name and table index
- headers
- row count and column count
- source row range
- row numbers and row values
- whether the response was truncated by `max_rows`

This endpoint is for review only. It does not modify `documents.metadata`, does not create metadata suggestions, does not create chunks, does not write to Qdrant, and does not trigger indexing.

Search and chat citations for table chunks use table metadata generated during parsing:

- `sheet_name`
- `row_start`
- `row_end`
- `chunk_id`

Frontends should display table citations as:

```text
filename / Sheet: sheet_name / Rows row_start-row_end
```

Current limits:

- Preview is capped by `max_rows` per table to keep responses small.
- Preview does not infer merged-cell table structure.
- Preview does not repair metadata or create suggestions.
- Row citations point to chunk row ranges, not individual cell coordinates.