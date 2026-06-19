from __future__ import annotations

from copy import deepcopy

from app.metadata import DEFAULT_DOCUMENT_METADATA_SCHEMA, validate_metadata


def valid_metadata() -> dict[str, object]:
    return {
        "title": "A200 Maintenance Manual",
        "document_type": "manual",
        "department": "maintenance",
        "source": "internal",
        "author": "CoreKB",
        "created_date": "2026-06-19",
        "version": "1.0",
        "tags": ["A200", "maintenance"],
        "access_level": "internal",
    }


def issue_codes(metadata: dict[str, object]) -> list[str]:
    return [issue.code for issue in validate_metadata(metadata)]


def test_valid_metadata_returns_no_issues() -> None:
    assert validate_metadata(valid_metadata()) == []


def test_missing_required_field() -> None:
    metadata = valid_metadata()
    del metadata["title"]

    issues = validate_metadata(metadata)

    assert issues[0].field == "title"
    assert issues[0].code == "missing_required_field"
    assert issues[0].severity == "error"


def test_invalid_type() -> None:
    metadata = valid_metadata()
    metadata["tags"] = "A200"

    issues = validate_metadata(metadata)

    assert issues[0].field == "tags"
    assert issues[0].code == "invalid_type"
    assert issues[0].expected == "list"


def test_invalid_enum() -> None:
    metadata = valid_metadata()
    metadata["document_type"] = "spreadsheet"

    issues = validate_metadata(metadata)

    assert issues[0].field == "document_type"
    assert issues[0].code == "invalid_enum"


def test_empty_required_value() -> None:
    metadata = valid_metadata()
    metadata["source"] = "   "

    issues = validate_metadata(metadata)

    assert issues[0].field == "source"
    assert issues[0].code == "empty_value"
    assert issues[0].severity == "error"


def test_unknown_field() -> None:
    metadata = valid_metadata()
    metadata["plant_specific_note"] = "legacy"

    issues = validate_metadata(metadata)

    assert issues[0].field == "plant_specific_note"
    assert issues[0].code == "unknown_field"
    assert issues[0].severity == "warning"


def test_multiple_issues_in_one_metadata_object() -> None:
    metadata = valid_metadata()
    del metadata["department"]
    metadata["document_type"] = "spreadsheet"
    metadata["tags"] = "not-a-list"
    metadata["extra"] = True

    codes = issue_codes(metadata)

    assert "missing_required_field" in codes
    assert "invalid_enum" in codes
    assert "invalid_type" in codes
    assert "unknown_field" in codes


def test_validator_does_not_mutate_input_metadata() -> None:
    metadata = valid_metadata()
    before = deepcopy(metadata)

    validate_metadata(metadata, DEFAULT_DOCUMENT_METADATA_SCHEMA)

    assert metadata == before
