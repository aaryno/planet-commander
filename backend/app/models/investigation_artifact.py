"""Investigation Artifact model for Commander enrichment."""
import datetime
import uuid
from typing import Any, List

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InvestigationArtifact(Base):
    """
    Investigation artifacts and documentation from ~/claude/projects/.

    Indexes markdown artifacts created during investigations, incidents,
    planning, and analysis work to enable "similar investigations" search
    and historical context lookup.
    """

    __tablename__ = "investigation_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )

    # File information
    file_path: Mapped[str] = mapped_column(
        Text, unique=True, nullable=False
    )  # Absolute path
    filename: Mapped[str] = mapped_column(
        String(500), nullable=False
    )  # Just filename
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Bytes

    # Metadata from filename (YYYYMMDD-HHMM-description.md)
    project: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # wx, g4, jobs, temporal, prodissue
    artifact_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # investigation, plan, handoff, analysis, complete
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )  # Parsed from filename

    # Content
    title: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # First markdown heading
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # From filename
    content: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Full markdown content

    # Extracted entities (JSONB arrays)
    jira_keys: Mapped[List[str] | None] = mapped_column(
        JSONB, nullable=True
    )  # ["COMPUTE-1234", "WX-567"]
    keywords: Mapped[List[str] | None] = mapped_column(
        JSONB, nullable=True
    )  # ["task", "lease", "expiration"]
    entities: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )  # {"systems": [...], "alerts": [...]}

    # Timestamps
    file_modified_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    indexed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Soft delete
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def content_preview(self) -> str:
        """Return first 200 characters of content for preview."""
        if not self.content:
            return ""
        # Remove markdown headings from preview
        lines = [line for line in self.content.split("\n") if not line.startswith("#")]
        text = " ".join(lines).strip()
        return text[:200] + "..." if len(text) > 200 else text

    @property
    def age_days(self) -> int:
        """Age of artifact in days (from created_at to now)."""
        now = datetime.datetime.now(datetime.timezone.utc)
        delta = now - self.created_at
        return delta.days

    @property
    def is_recent(self) -> bool:
        """Check if artifact was created in last 90 days."""
        return self.age_days <= 90

    @property
    def has_jira_keys(self) -> bool:
        """Check if artifact has associated JIRA keys."""
        return bool(self.jira_keys and len(self.jira_keys) > 0)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<InvestigationArtifact(filename='{self.filename}', "
            f"project='{self.project}', "
            f"type='{self.artifact_type}')>"
        )
