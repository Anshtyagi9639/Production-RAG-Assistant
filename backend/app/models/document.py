import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import DocumentStatus, in_check, string_enum


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        in_check("status", DocumentStatus),
        CheckConstraint("size_bytes > 0", name="size_bytes_positive"),
        # List filtered by status, newest first.
        Index(
            "ix_documents_workspace_id_status_created_at", "workspace_id", "status", "created_at"
        ),
        # List without a status filter, newest first.
        Index("ix_documents_workspace_id_created_at", "workspace_id", "created_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[DocumentStatus] = mapped_column(
        string_enum(DocumentStatus), server_default=DocumentStatus.UPLOADED.value
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None]
    chunk_count: Mapped[int | None]
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A chunk of document text. Its id is also the Qdrant point id."""

    __tablename__ = "document_chunks"
    # The unique constraint's leading column also serves as the index on document_id.
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        CheckConstraint("chunk_index >= 0", name="chunk_index_non_negative"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    # Denormalized from the document so tenant filters don't need a join.
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int]
    # PDFs have pages; DOCX, TXT and MD do not.
    page: Mapped[int | None]
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int]
