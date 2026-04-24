"""JIRA Issue model for Planet Commander Phase 1."""
import datetime
import uuid
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class JiraIssue(Base):
    """
    Cached JIRA issue metadata.

    Stores locally-cached copies of JIRA issues to enable context resolution
    without constant API calls.
    """
    __tablename__ = "jira_issues"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Core JIRA fields
    external_key: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )  # e.g., COMPUTE-2059
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(200), nullable=True)
    labels: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    fix_versions: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    source_last_synced_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Planet Commander fields
    agent_ready: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    context_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_contexts.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_context_audit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # FK to audits (Phase 3)
    last_acceptance_audit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # FK to audits (Phase 3)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships will be added when we have WorkContext fully set up
    # context: Mapped["WorkContext"] = relationship(back_populates="jira_issues")
