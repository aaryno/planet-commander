"""Google Drive document model."""

import datetime
import uuid
from typing import List, Optional

from sqlalchemy import DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GoogleDriveDocument(Base):
    """Google Drive document from Compute Team shared drive."""

    __tablename__ = "google_drive_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))

    # Google Drive identity
    external_doc_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)  # document, spreadsheet, presentation
    url: Mapped[str] = mapped_column(Text, nullable=False)

    # File information
    title: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Location
    shared_drive: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    folder_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Classification
    project: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    document_kind: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Metadata
    last_modified_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    owner: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Extracted content
    jira_keys: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    keywords: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    tags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Timestamps
    last_indexed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    @property
    def is_stale(self) -> bool:
        """Check if document is stale (>180 days since last modification)."""
        if not self.last_modified_at:
            return False
        days_ago = (datetime.datetime.now(datetime.timezone.utc) - self.last_modified_at).days
        return days_ago > 180

    @property
    def is_postmortem(self) -> bool:
        """Check if document is a postmortem."""
        return self.document_kind == "postmortem"

    @property
    def is_rfd(self) -> bool:
        """Check if document is an RFD/RFC."""
        return self.document_kind in ("rfd", "rfc")

    @property
    def has_jira_keys(self) -> bool:
        """Check if document has JIRA keys."""
        return bool(self.jira_keys)

    @property
    def age_days(self) -> int:
        """Days since last modification."""
        if not self.last_modified_at:
            return -1
        return (datetime.datetime.now(datetime.timezone.utc) - self.last_modified_at).days

    def __repr__(self) -> str:
        return f"<GoogleDriveDocument(title='{self.title}', kind='{self.document_kind}', jira_keys={self.jira_keys})>"
