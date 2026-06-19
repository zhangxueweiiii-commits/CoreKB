from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Severity = Literal["info", "warning", "error"]
IssueCode = Literal[
    "missing_required_field",
    "invalid_type",
    "empty_value",
    "invalid_enum",
    "unknown_field",
]


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    code: IssueCode
    severity: Severity
    message: str
    current_value: Any = None
    expected: Any = None


@dataclass(frozen=True)
class FieldSpec:
    name: str
    expected_type: type | tuple[type, ...]
    required: bool = False
    allowed_values: tuple[Any, ...] | None = None
    allow_empty: bool = False


@dataclass(frozen=True)
class MetadataSchema:
    fields: dict[str, FieldSpec] = field(default_factory=dict)
    allow_unknown_fields: bool = False

    @property
    def required_fields(self) -> tuple[str, ...]:
        return tuple(name for name, spec in self.fields.items() if spec.required)
