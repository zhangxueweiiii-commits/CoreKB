import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class RetrievalLog(Base, UUIDMixin):
    __tablename__ = "retrieval_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    knowledge_base_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    retrieved_chunk_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    scores: Mapped[list[float]] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
