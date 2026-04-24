"""Work Context model for Planet Commander Phase 1."""
import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class OriginType(str, enum.Enum):
    """Origin type of work context."""
    JIRA = "jira"
    CHAT = "chat"
    BRANCH = "branch"
    WORKTREE = "worktree"
    MANUAL = "manual"
    MERGED = "merged"


class ContextStatus(str, enum.Enum):
    """Status of work context."""
    ACTIVE = "active"
    BLOCKED = "blocked"
    STALLED = "stalled"
    READY = "ready"
    DONE = "done"
    ORPHANED = "orphaned"
    ARCHIVED = "archived"


class HealthStatus(str, enum.Enum):
    """Health status of work context."""
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    UNKNOWN = "unknown"


class WorkContext(Base):
    """
    Primary work abstraction for Planet Commander.

    Represents a coherent unit of work that may include JIRA issues, chats,
    branches, worktrees, summaries, audits, and agent runs.
    """
    __tablename__ = "work_contexts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)

    origin_type: Mapped[OriginType] = mapped_column(
        SQLEnum(OriginType, native_enum=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False
    )
    primary_jira_issue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jira_issues.id", ondelete="SET NULL"), nullable=True
    )
    primary_chat_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[ContextStatus] = mapped_column(
        SQLEnum(ContextStatus, native_enum=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=ContextStatus.ACTIVE
    )
    health_status: Mapped[HealthStatus] = mapped_column(
        SQLEnum(HealthStatus, native_enum=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=HealthStatus.UNKNOWN
    )

    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_overview_summary_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # FK to summaries (Phase 2)
    last_agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # FK to agent_runs (Phase 4)

    owner: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    archived_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships (will be populated as we add other models)
    # primary_jira_issue: Mapped["JiraIssue"] = relationship(back_populates="primary_contexts")
    # primary_chat: Mapped["Agent"] = relationship(back_populates="primary_contexts")
