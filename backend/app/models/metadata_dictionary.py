import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class MetadataDictionaryEntryStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class MetadataDictionaryEntry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "metadata_dictionary_entries"
    __table_args__ = (
        UniqueConstraint("field_name", "canonical_value", name="uq_metadata_dictionary_field_canonical"),
    )

    field_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    canonical_value: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[MetadataDictionaryEntryStatus] = mapped_column(
        Enum(MetadataDictionaryEntryStatus),
        default=MetadataDictionaryEntryStatus.active,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
