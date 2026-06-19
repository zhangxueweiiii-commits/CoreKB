from app.models.document import Document


RECOMMENDED_FIELDS_BY_CATEGORY = {
    "maintenance": [{"equipment_model"}, {"fault_code", "process_name"}],
    "quality": [{"doc_type"}, {"version"}, {"effective_date"}],
    "sop": [{"sop_code"}, {"process_name"}, {"version"}],
    "material": [{"material_code", "product_model"}, {"version"}],
}


class DocumentMetadataCompletenessService:
    def evaluate(self, document: Document) -> dict:
        meta = document.meta or {}
        category = str(meta.get("category") or "").strip()
        doc_type = str(meta.get("doc_type") or "").strip()
        inferred_category = category or self._category_from_doc_type(doc_type)
        requirements = RECOMMENDED_FIELDS_BY_CATEGORY.get(inferred_category, [])
        if not requirements:
            return {
                "completeness_status": "missing",
                "missing_recommended_fields": ["category", "doc_type"],
            }
        missing: list[str] = []
        satisfied_count = 0
        for group in requirements:
            if any(str(meta.get(field) or "").strip() for field in group):
                satisfied_count += 1
                continue
            missing.append(" or ".join(sorted(group)))
        if not missing:
            status = "complete"
        elif satisfied_count > 0:
            status = "partial"
        else:
            status = "missing"
        return {
            "completeness_status": status,
            "missing_recommended_fields": missing,
        }

    @staticmethod
    def _category_from_doc_type(doc_type: str) -> str:
        if any(keyword in doc_type for keyword in ["维修", "故障"]):
            return "maintenance"
        if any(keyword in doc_type for keyword in ["检验", "质量"]):
            return "quality"
        if any(keyword in doc_type for keyword in ["作业指导", "SOP", "操作规程"]):
            return "sop"
        if any(keyword in doc_type for keyword in ["物料", "参数", "规格", "备件"]):
            return "material"
        return ""
