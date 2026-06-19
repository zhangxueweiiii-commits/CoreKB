from __future__ import annotations

from typing import Any

from app.metadata.schemas import FieldSpec, MetadataSchema, ValidationIssue


DEFAULT_DOCUMENT_METADATA_SCHEMA = MetadataSchema(
    fields={
        "title": FieldSpec("title", str, required=True),
        "document_type": FieldSpec(
            "document_type",
            str,
            required=True,
            allowed_values=("manual", "policy", "report", "work_order", "invoice", "bom", "unknown"),
        ),
        "department": FieldSpec("department", str, required=True),
        "source": FieldSpec("source", str, required=True),
        "author": FieldSpec("author", str),
        "created_date": FieldSpec("created_date", str),
        "version": FieldSpec("version", str),
        "tags": FieldSpec("tags", list),
        "access_level": FieldSpec(
            "access_level",
            str,
            allowed_values=("public", "internal", "restricted", "confidential"),
        ),
    },
    allow_unknown_fields=False,
)


def validate_metadata(metadata: dict[str, Any], schema: MetadataSchema = DEFAULT_DOCUMENT_METADATA_SCHEMA) -> list[ValidationIssue]:
    """Validate metadata without mutating input or touching external systems."""

    issues: list[ValidationIssue] = []

    for field_name in schema.required_fields:
        if field_name not in metadata:
            issues.append(
                ValidationIssue(
                    field=field_name,
                    code="missing_required_field",
                    severity="error",
                    message=f"Required metadata field '{field_name}' is missing.",
                    current_value=None,
                    expected="required",
                )
            )

    if not schema.allow_unknown_fields:
        for field_name, value in metadata.items():
            if field_name not in schema.fields:
                issues.append(
                    ValidationIssue(
                        field=field_name,
                        code="unknown_field",
                        severity="warning",
                        message=f"Metadata field '{field_name}' is not defined in the schema.",
                        current_value=value,
                        expected=tuple(schema.fields.keys()),
                    )
                )

    for field_name, value in metadata.items():
        spec = schema.fields.get(field_name)
        if spec is None:
            continue
        issues.extend(_validate_field_value(spec, value))

    return issues


def _validate_field_value(spec: FieldSpec, value: Any) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if value is None or (isinstance(value, str) and value.strip() == ""):
        if spec.required or not spec.allow_empty:
            issues.append(
                ValidationIssue(
                    field=spec.name,
                    code="empty_value",
                    severity="error" if spec.required else "warning",
                    message=f"Metadata field '{spec.name}' must not be empty.",
                    current_value=value,
                    expected="non-empty value",
                )
            )
        return issues

    if not isinstance(value, spec.expected_type):
        issues.append(
            ValidationIssue(
                field=spec.name,
                code="invalid_type",
                severity="error",
                message=f"Metadata field '{spec.name}' has an invalid type.",
                current_value=value,
                expected=_format_expected_type(spec.expected_type),
            )
        )
        return issues

    if spec.allowed_values is not None and value not in spec.allowed_values:
        issues.append(
            ValidationIssue(
                field=spec.name,
                code="invalid_enum",
                severity="error",
                message=f"Metadata field '{spec.name}' is not an allowed value.",
                current_value=value,
                expected=spec.allowed_values,
            )
        )

    return issues


def _format_expected_type(expected_type: type | tuple[type, ...]) -> str | tuple[str, ...]:
    if isinstance(expected_type, tuple):
        return tuple(item.__name__ for item in expected_type)
    return expected_type.__name__
