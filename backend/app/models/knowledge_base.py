import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class KnowledgeBaseVisibility(str, enum.Enum):
    private = "private"
    company = "company"


class KBPermissionRole(str, enum.Enum):
    owner = "owner"
    editor = "editor"
    viewer = "viewer"


class KnowledgeBase(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_bases"

    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    visibility: Mapped[KnowledgeBaseVisibility] = mapped_column(
        Enum(KnowledgeBaseVisibility), default=KnowledgeBaseVisibility.private, nullable=False
    )

    owner = relationship("User", back_populates="owned_knowledge_bases")
    permissions = relationship(
        "KBPermission", back_populates="knowledge_base", cascade="all, delete-orphan"
    )
    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete")


class KBPermission(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "kb_permissions"
    __table_args__ = (UniqueConstraint("knowledge_base_id", "user_id", name="uq_kb_user_permission"),)

    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    role: Mapped[KBPermissionRole] = mapped_column(Enum(KBPermissionRole), nullable=False)

    knowledge_base = relationship("KnowledgeBase", back_populates="permissions")
    user = relationship("User", foreign_keys=[user_id])
    creator = relationship("User", foreign_keys=[created_by])
