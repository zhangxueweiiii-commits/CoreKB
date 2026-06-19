# Metadata Normalization Precheck

Metadata normalization precheck scans existing `documents.metadata` and compares values with the metadata dictionary and rule-based normalization. It produces a read-only report of values that may need review.

The precheck does not:

- Parse source files again.
- Read Qdrant payloads.
- Call an LLM.
- Create metadata suggestions.
- Modify `documents.metadata`.
- Trigger indexing or reindexing.
- Apply batch fixes.

## Supported Fields

The first version checks only:

- `equipment_model`
- `fault_code`
- `material_code`
- `product_model`
- `sop_code`
- `process_name`
- `doc_type`
- `category`

Unsupported metadata fields are reported as `unsupported`.

## Status Definitions

- `canonical`: the current value is already an active dictionary canonical value.
- `alias_match`: the current value matches an active dictionary alias and can be normalized to the canonical value.
- `rule_normalizable`: the value does not match the dictionary, but existing rules can normalize it.
- `dictionary_missing`: the value is present but missing from the active dictionary.
- `invalid_or_empty`: the value is empty or a known placeholder such as `N/A`, `未知`, or `-`.
- `unsupported`: the field is outside the first-version supported field list.

## Recommended Actions

- `no_action`: no action needed.
- `review_and_normalize`: review the value and normalize through the existing single-document metadata review flow.
- `add_dictionary_entry`: add a canonical dictionary entry or alias before reviewing affected documents.
- `review_invalid_value`: confirm whether the metadata should be removed, replaced, or ignored.
- `ignore`: no current action recommended.

## API

Run precheck:

```http
GET /api/metadata/precheck
```

Supported filters:

- `knowledge_base_id`
- `document_id`
- `field_name`
- `status`
- `page`
- `page_size`
- `order_by`
- `order_direction`

Summary:

```http
GET /api/metadata/precheck/summary?knowledge_base_id={kb_id}
```

The summary includes:

- Counts by status.
- Counts by field.
- Top dictionary-missing values.
- Top alias-match values.
- Fixable counts by knowledge base.

## How To Use The Report

For `alias_match`, the dictionary already knows the standard value. Open the document metadata suggestions panel or manually review the document metadata before normalizing.

For `dictionary_missing`, decide whether the value is a real business object. If yes, add a metadata dictionary entry or alias. If not, mark or clean it through the normal document metadata review process.

For `rule_normalizable`, review whether the rule result is acceptable. If the value appears repeatedly, consider adding a dictionary entry so future suggestions match by dictionary rather than rule.

## Why Precheck Is Read-Only

Historical metadata may contain plant-specific wording, temporary codes, or values that need business confirmation. Automatically rewriting them could silently change retrieval behavior. CoreKB therefore reports possible fixes but leaves review and reindexing to the existing manual metadata workflow.

## Jump To Single-Document Review

Each precheck item can be opened with `Review in document`. The frontend navigates to the document detail route and opens the metadata review area:

```text
/documents/{document_id}?tab=metadata&focus_field=equipment_model&current_value=A-200&suggested_value=A200&precheck_status=alias_match&from=metadata_precheck
```

Parameter meanings:

- `tab=metadata`: open and scroll to the metadata review area.
- `focus_field`: highlight suggestions for the field reported by precheck.
- `current_value`: the current value from `documents.metadata`.
- `suggested_value`: the standard value suggested by dictionary or rule normalization.
- `precheck_status`: the precheck classification, such as `alias_match` or `rule_normalizable`.
- `from=metadata_precheck`: enables the `Back to Metadata precheck` action.

The document page only uses these parameters for positioning and context. It does not generate suggestions, accept suggestions, modify `documents.metadata`, or trigger reindexing automatically.

If the focused field has a pending metadata suggestion, the row is highlighted and marked as related to the precheck item. If no suggestion exists yet, the page shows a hint and keeps the normal `Generate metadata suggestions` button available for manual use.

## Current Limits

- Only scans `documents.metadata`.
- Does not inspect chunks or Qdrant payloads.
- Does not call LLMs.
- Does not create or accept suggestions.
- Does not change metadata.
- Does not trigger reindexing.
- Does not provide batch repair.
- Precheck-to-document navigation is positioning only; it does not apply fixes.
