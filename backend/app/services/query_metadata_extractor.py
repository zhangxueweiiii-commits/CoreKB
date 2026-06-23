import re


STRING_METADATA_FILTER_FIELDS = {
    "category",
    "doc_type",
    "equipment_model",
    "fault_code",
    "material_code",
    "product_model",
    "process_name",
    "sop_code",
    "version",
    "source_type",
    "sheet_name",
}


INTEGER_METADATA_FILTER_FIELDS = {
    "table_index",
    "row_start",
    "row_end",
}

ALLOWED_METADATA_FILTER_FIELDS = STRING_METADATA_FILTER_FIELDS | INTEGER_METADATA_FILTER_FIELDS


def sanitize_metadata_filter(metadata_filter: dict | None) -> dict[str, str | int]:
    if not metadata_filter:
        return {}
    sanitized: dict[str, str | int] = {}
    for key, value in metadata_filter.items():
        if key not in ALLOWED_METADATA_FILTER_FIELDS:
            continue
        if value is None:
            continue
        normalized = str(value).strip()
        if not normalized:
            continue
        if key in INTEGER_METADATA_FILTER_FIELDS:
            try:
                sanitized[key] = int(normalized)
            except ValueError:
                continue
            continue
        sanitized[key] = normalized
    return sanitized


def extract_metadata_from_query(query: str) -> dict[str, str]:
    text = query.upper()
    metadata: dict[str, str] = {}

    material_match = re.search(r"(?:物料\s*)?\b(?:MAT-\d{3,}|M\d{3,}|WL-\d{3,})\b", text)
    if material_match:
        metadata["material_code"] = material_match.group(0).replace("物料", "").strip()

    sop_match = re.search(r"(?:作业指导书\s*)?\bSOP-?\d{3,}\b", text)
    if sop_match:
        metadata["sop_code"] = re.search(r"SOP-?\d{3,}", sop_match.group(0)).group(0)

    fault_match = re.search(r"(?:故障码\s*)?\b(?:ERR-?\d{2,}|ERROR\s+\d{2,}|E-?\d{2,}|F-?\d{2,})\b", text)
    if fault_match:
        raw_fault = fault_match.group(0).replace("故障码", "").strip()
        digits = re.search(r"\d{2,}", raw_fault)
        if raw_fault.startswith(("ERR", "ERROR", "E")) and digits:
            metadata["fault_code"] = f"E{digits.group(0)}"
        elif raw_fault.startswith("F") and digits:
            metadata["fault_code"] = f"F{digits.group(0)}"

    equipment_match = re.search(r"\b(?:EQ-[ABC]\d{3,}|[ABC]-?\d{3,})\b", text)
    if equipment_match:
        candidate = equipment_match.group(0)
        metadata["equipment_model"] = candidate if candidate.startswith("EQ-") else candidate.replace("-", "")

    product_match = re.search(r"\b(?:P\d{3,}|PX-\d{3,})\b", text)
    if product_match:
        metadata["product_model"] = product_match.group(0)

    return metadata
