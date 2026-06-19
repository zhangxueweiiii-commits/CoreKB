from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from uuid import UUID

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models.document import Document, DocumentStatus
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase, KnowledgeBaseVisibility
from app.models.user import User, UserRole
from app.services.index_job_service import IndexJobService
from app.services.vector_store import VectorStore
from app.tasks.document_tasks import enqueue_reindex_job


EVALUATION_FIXTURE_METADATA: dict[str, dict] = {
    "maintenance_A200.txt": {
        "document_title": "A200维修手册",
        "category": "maintenance",
        "doc_type": "maintenance_manual",
        "equipment_model": "A200",
        "fault_code": "E12",
        "version": "v1.0",
    },
    "quality_standard.csv": {
        "document_title": "质量检验标准",
        "category": "quality",
        "doc_type": "quality_standard",
        "quality_item": "外观划伤",
        "version": "v1.0",
    },
    "sop_assembly_line.txt": {
        "document_title": "装配SOP",
        "category": "sop",
        "doc_type": "sop",
        "process_name": "A200 控制板装配",
        "sop_code": "SOP-A200-ASM",
        "version": "v1.0",
    },
    "sop_checklist.docx": {
        "document_title": "装配SOP",
        "category": "sop",
        "doc_type": "sop_checklist",
        "process_name": "A200 控制板装配",
        "sop_code": "SOP-A200-ASM",
        "version": "v1.0",
    },
    "material_parameters.xlsx": {
        "document_title": "物料参数表",
        "category": "material",
        "doc_type": "material_parameters",
        "material_code": "P-A200-H",
        "product_model": "A200-H",
        "version": "v1.0",
    },
}


@dataclass
class EvaluationFixtureImportResult:
    imported_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    kb_id: UUID | None = None
    document_ids: list[UUID] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)


def scan_fixture_documents(fixtures_dir: Path) -> list[Path]:
    if not fixtures_dir.exists():
        raise FileNotFoundError(f"Evaluation fixtures directory not found: {fixtures_dir}")
    allowed = {".pdf", ".docx", ".md", ".txt", ".xlsx", ".xls", ".csv"}
    return sorted(path for path in fixtures_dir.iterdir() if path.is_file() and path.suffix.lower() in allowed)


class EvaluationFixtureImporter:
    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
        enqueue_job=enqueue_reindex_job,
        delete_vectors: bool = True,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.enqueue_job = enqueue_job
        self.delete_vectors = delete_vectors

    def import_fixtures(self, force: bool = False, reset: bool = False) -> EvaluationFixtureImportResult:
        actor = self._get_admin_actor()
        kb = self._get_or_create_evaluation_kb(actor)
        if reset:
            self._reset_kb(kb)
        result = EvaluationFixtureImportResult(kb_id=kb.id)
        for fixture_path in scan_fixture_documents(Path(self.settings.evaluation_fixtures_dir)):
            try:
                existing = self.db.scalar(
                    select(Document).where(
                        Document.knowledge_base_id == kb.id,
                        Document.filename == fixture_path.name,
                    )
                )
                if existing and not force:
                    result.skipped_count += 1
                    result.document_ids.append(existing.id)
                    continue

                document = self._upsert_document(kb, fixture_path, existing)
                job = IndexJobService(self.db).create_document_job(document, actor)
                self.enqueue_job(job.id)
                result.imported_count += 1
                result.document_ids.append(document.id)
            except Exception as exc:
                self.db.rollback()
                result.failed_count += 1
                result.failures.append({"filename": fixture_path.name, "error": str(exc)})
        return result

    def _get_admin_actor(self) -> User:
        actor = self.db.scalar(
            select(User)
            .where(User.role == UserRole.admin, User.is_active.is_(True))
            .order_by(User.created_at.asc())
        )
        if not actor:
            raise RuntimeError("No active admin user found. Create an admin before importing evaluation fixtures.")
        return actor

    def _get_or_create_evaluation_kb(self, actor: User) -> KnowledgeBase:
        kb = self.db.scalar(select(KnowledgeBase).where(KnowledgeBase.name == self.settings.evaluation_kb_name))
        if kb:
            return kb
        kb = KnowledgeBase(
            name=self.settings.evaluation_kb_name,
            description="Synthetic production-like fixtures for CoreKB retrieval evaluation.",
            owner_id=actor.id,
            visibility=KnowledgeBaseVisibility.private,
        )
        self.db.add(kb)
        self.db.flush()
        self.db.add(
            KBPermission(
                knowledge_base_id=kb.id,
                user_id=actor.id,
                role=KBPermissionRole.owner,
                created_by=actor.id,
            )
        )
        self.db.commit()
        self.db.refresh(kb)
        return kb

    def _reset_kb(self, kb: KnowledgeBase) -> None:
        documents = list(self.db.scalars(select(Document).where(Document.knowledge_base_id == kb.id)).all())
        for document in documents:
            if self.delete_vectors:
                try:
                    asyncio.run(VectorStore().delete_document(str(document.id)))
                except Exception:
                    pass
            self.db.delete(document)
        self.db.commit()

    def _upsert_document(self, kb: KnowledgeBase, fixture_path: Path, existing: Document | None) -> Document:
        target_dir = Path(self.settings.upload_dir) / str(kb.id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / fixture_path.name
        shutil.copy2(fixture_path, target_path)
        metadata = EVALUATION_FIXTURE_METADATA.get(
            fixture_path.name,
            {
                "document_title": fixture_path.stem,
                "category": "unknown",
                "doc_type": fixture_path.suffix.lower().lstrip("."),
                "version": "v1.0",
            },
        )
        if existing:
            document = existing
            document.file_path = str(target_path)
            document.file_type = fixture_path.suffix.lower().lstrip(".")
            document.file_size = target_path.stat().st_size
            document.status = DocumentStatus.uploaded
            document.error_message = None
            document.indexed_at = None
            document.chunk_count = 0
            document.meta = dict(metadata)
        else:
            document = Document(
                knowledge_base_id=kb.id,
                filename=fixture_path.name,
                file_path=str(target_path),
                file_type=fixture_path.suffix.lower().lstrip("."),
                file_size=target_path.stat().st_size,
                status=DocumentStatus.uploaded,
                meta=dict(metadata),
            )
            self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CoreKB evaluation fixture documents.")
    parser.add_argument("--force", action="store_true", help="Re-import existing fixture documents and rebuild indexes.")
    parser.add_argument("--reset", action="store_true", help="Clear the Evaluation KB before importing fixtures.")
    args = parser.parse_args()

    with SessionLocal() as db:
        result = EvaluationFixtureImporter(db).import_fixtures(force=args.force, reset=args.reset)
        print(json.dumps(asdict(result), ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
