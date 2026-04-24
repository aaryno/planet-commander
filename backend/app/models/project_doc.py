"""Project documentation model."""

import datetime
import uuid
from typing import List, Optional

from sqlalchemy import DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ProjectDoc(Base):
    """Project documentation from ~/claude/projects/{project}-notes/{project}-claude.md"""

    __tablename__ = "project_docs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))

    # Project identity
    project_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Metadata
    sections: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    keywords: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    links: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Ownership
    team: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    primary_contact: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Repository info
    repositories: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)

    # Slack channels
    slack_channels: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)

    # Timestamps
    file_modified_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # Relationships
    doc_sections: Mapped[List["ProjectDocSection"]] = relationship("ProjectDocSection", back_populates="project_doc", cascade="all, delete-orphan")

    @property
    def is_stale(self) -> bool:
        """Check if documentation is stale (>30 days since last modification)."""
        if not self.file_modified_at:
            return False
        days_ago = (datetime.datetime.now(datetime.timezone.utc) - self.file_modified_at).days
        return days_ago > 30

    @property
    def word_count(self) -> int:
        """Approximate word count of documentation."""
        return len(self.content.split())

    @property
    def last_updated_days_ago(self) -> int:
        """Days since last file modification."""
        if not self.file_modified_at:
            return -1
        return (datetime.datetime.now(datetime.timezone.utc) - self.file_modified_at).days

    def __repr__(self) -> str:
        return f"<ProjectDoc(project_name='{self.project_name}', team='{self.team}', word_count={self.word_count})>"
