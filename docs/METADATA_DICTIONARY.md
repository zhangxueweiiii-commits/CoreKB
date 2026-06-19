# Metadata Dictionary

CoreKB metadata filters rely on stable field values. A dictionary keeps different readable forms of the same business object mapped to one canonical value before metadata is written into document metadata, chunk metadata, and Qdrant payloads.

## Canonical Values And Aliases

A dictionary entry contains:

- `field_name`
- `canonical_value`
- `aliases`
- `status`
- `description`
- `created_by`
- `created_at`
- `updated_at`

Examples:

- `equipment_model`: canonical `A200`, aliases `A-200`, `EQ-A200`
- `fault_code`: canonical `E12`, aliases `E-12`, `ERR12`, `Error 12`
- `sop_code`: canonical `SOP-001`, aliases `SOP001`, `SOP 001`
- `material_code`: canonical `MAT-001`, aliases `MAT001`, `MAT 001`

## Supported Fields

The first version supports:

- `equipment_model`
- `fault_code`
- `material_code`
- `product_model`
- `sop_code`
- `process_name`
- `doc_type`
- `category`

## Normalization Priority

Metadata values are normalized in this order:

1. Active dictionary `canonical_value` exact match.
2. Active dictionary `alias` exact match.
3. Rule-based normalization from the metadata suggester.
4. Fallback to the trimmed raw value.

The normalization response includes:

- `raw_value`
- `normalized_value`
- `matched_by`: `canonical`, `alias`, `rule`, or `fallback`
- `dictionary_entry_id` when a dictionary entry is matched

## Alias Conflict Rules

For one `field_name`, the same active alias or canonical value cannot belong to multiple active canonical values.

This prevents cases like:

```text
equipment_model / A200 aliases ["A-200"]
equipment_model / AX200 aliases ["A-200"]
```

The service rejects conflicting entries or alias updates.

## API

List:

```http
GET /api/metadata-dictionary?field_name=equipment_model&status=active&keyword=A200
```

Create:

```http
POST /api/metadata-dictionary
Content-Type: application/json

{
  "field_name": "equipment_model",
  "canonical_value": "A200",
  "aliases": ["A-200", "EQ-A200"],
  "description": "A200 equipment family"
}
```

Update:

```http
PATCH /api/metadata-dictionary/{entry_id}
```

Add alias:

```http
POST /api/metadata-dictionary/{entry_id}/aliases
Content-Type: application/json

{"alias": "A 200"}
```

Delete alias:

```http
DELETE /api/metadata-dictionary/{entry_id}/aliases/{alias}
```

All dictionary management APIs are admin-only.

## Custom Values

When accepting a metadata suggestion, reviewers can choose:

- Accept the standard value: writes `normalized_value`.
- Keep a custom value: writes the supplied custom value and marks `custom_value=true`.

Custom values are not automatically added to the dictionary. This avoids polluting the canonical dictionary with one-off plant wording, temporary names, or values that still need business confirmation.

## Current Limits

- No LLM extraction.
- No automatic dictionary creation.
- No automatic acceptance.
- No automatic overwrite of existing metadata.
- No batch review.
- No batch repair of historical document metadata.
- No approval workflow.
- No complex dictionary versioning.

Future work can add batch review, historical metadata normalization, and LLM-assisted suggestions after the dictionary governance rules are validated with real enterprise documents.
