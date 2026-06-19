import logging
from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.tracing import start_span
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.services.chunker import Chunker
from app.services.document_parser import DocumentParser
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore


logger = logging.getLogger(__name__)


class DocumentIngestionService:
    def __init__(self) -> None:
        settings = get_settings()
        self.parser = DocumentParser()
        self.chunker = Chunker(settings.default_chunk_size, settings.default_chunk_overlap)
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore()

    async def process(self, db: Session, document: Document) -> Document:
        try:
            with start_span("document.indexing", document_id=document.id, knowledge_base_id=document.knowledge_base_id):
                return await self._process(db, document)
        except Exception as exc:
            logger.exception("Failed to index document %s", document.id)
            db.rollback()
            document.status = DocumentStatus.failed
            document.error_message = str(exc)[:2000]
            db.add(document)
            db.commit()
            db.refresh(document)
            return document

    async def _process(self, db: Session, document: Document) -> Document:
        try:
            await self.clear_existing_index(db, document, raise_on_vector_error=True)
            document.status = DocumentStatus.parsing
            document.error_message = None
            document.indexed_at = None
            document.chunk_count = 0
            db.commit()

            sections = self.parser.parse(document.file_path)
            document.status = DocumentStatus.chunking
            db.commit()
            chunks = self.chunker.chunk(sections)

            chunk_models: list[DocumentChunk] = []
            for chunk in chunks:
                chunk_meta = {**(document.meta or {}), **(chunk.metadata or {})}
                model = DocumentChunk(
                    document_id=document.id,
                    knowledge_base_id=document.knowledge_base_id,
                    chunk_text=chunk.chunk_text,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    meta=chunk_meta,
                )
                db.add(model)
                chunk_models.append(model)
            document.chunk_count = len(chunk_models)
            db.commit()

            if not chunk_models:
                document.status = DocumentStatus.indexed
                document.indexed_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(document)
                return document

            document.status = DocumentStatus.embedding
            db.commit()
            embeddings = await self.embedding_service.embed_texts([chunk.chunk_text for chunk in chunks])
            points = []
            for chunk_model, vector in zip(chunk_models, embeddings, strict=True):
                payload = {
                    "chunk_id": str(chunk_model.id),
                    "document_id": str(document.id),
                    "knowledge_base_id": str(document.knowledge_base_id),
                    "filename": document.filename,
                    "document_title": chunk_model.meta.get("document_title"),
                    "category": chunk_model.meta.get("category"),
                    "doc_type": chunk_model.meta.get("doc_type"),
                    "equipment_model": chunk_model.meta.get("equipment_model"),
                    "fault_code": chunk_model.meta.get("fault_code"),
                    "material_code": chunk_model.meta.get("material_code"),
                    "product_model": chunk_model.meta.get("product_model"),
                    "process_name": chunk_model.meta.get("process_name"),
                    "sop_code": chunk_model.meta.get("sop_code"),
                    "version": chunk_model.meta.get("version"),
                    "page_number": chunk_model.page_number,
                    "section_title": chunk_model.section_title,
                    "source_type": chunk_model.meta.get("source_type"),
                    "sheet_name": chunk_model.meta.get("sheet_name"),
                    "row_start": chunk_model.meta.get("row_start"),
                    "row_end": chunk_model.meta.get("row_end"),
                    "column_names": chunk_model.meta.get("column_names"),
                    "table_index": chunk_model.meta.get("table_index"),
                }
                points.append((str(chunk_model.id), vector, payload))
            await self.vector_store.upsert_chunks(points)

            document.status = DocumentStatus.indexed
            document.error_message = None
            document.indexed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(document)
            return document
        except Exception as exc:
            logger.exception("Failed to index document %s", document.id)
            db.rollback()
            document.status = DocumentStatus.failed
            document.error_message = str(exc)[:2000]
            db.add(document)
            db.commit()
            db.refresh(document)
            return document

    async def clear_existing_index(
        self, db: Session, document: Document, raise_on_vector_error: bool = False
    ) -> None:
        try:
            await self.vector_store.delete_document(str(document.id))
        except Exception:
            logger.exception("Failed to delete old vectors for document %s", document.id)
            if raise_on_vector_error:
                raise
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        document.chunk_count = 0
        document.indexed_at = None
        db.flush()
