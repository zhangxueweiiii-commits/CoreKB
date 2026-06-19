import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class DocumentStatus(str, enum.Enum):
    uploaded = "uploaded"
    parsing = "parsing"
    chunking = "chunking"
    parsed = "parsed"
    embedding = "embedding"
    indexed = "indexed"
    failed = "failed"


class DocumentMetadataSuggestionStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class DocumentMetadataSuggestionConfidence(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


class DocumentMetadataSuggestionSource(str, enum.Enum):
    filename = "filename"
    title = "title"
    parsed_text = "parsed_text"


class Document(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "documents"

    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.uploaded, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentMetadataSuggestion(Base, UUIDMixin):
    __tablename__ = "document_metadata_suggestions"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "field",
            "suggested_value",
            name="uq_document_metadata_suggestion_value",
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalization_source: Mapped[str] = mapped_column(String(64), nullable=False, default="rule")
    dictionary_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("metadata_dictionary_entries.id", ondelete="SET NULL"), nullable=True
    )
    custom_value: Mapped[bool] = mapped_column(default=False, nullable=False)
    suggested_value: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[DocumentMetadataSuggestionConfidence] = mapped_column(
        Enum(DocumentMetadataSuggestionConfidence), nullable=False, index=True
    )
    source: Mapped[DocumentMetadataSuggestionSource] = mapped_column(
        Enum(DocumentMetadataSuggestionSource), nullable=False, index=True
    )
    evidence_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    rule_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[DocumentMetadataSuggestionStatus] = mapped_column(
        Enum(DocumentMetadataSuggestionStatus),
        default=DocumentMetadataSuggestionStatus.pending,
        nullable=False,
        index=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DocumentChunk(Base, UUIDMixin):
    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(255))
    meta: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document = relationship("Document", back_populates="chunks")
