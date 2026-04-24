"""Coach Session model for guided human audit walkthrough."""
import datetime
import enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CoachItemStatus(str, enum.Enum):
    """Status of a single item within a coach session."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    ANSWERED = "answered"
    RESOLVED = "resolved"
    DEFERRED = "deferred"
    BLOCKED = "blocked"


class CoachSession(Base):
    """
    Persistent guided human audit session.

    Tracks a walkthrough session where a human reviews audit findings
    for a target entity (typically a JIRA issue). Items are stored as
    JSONB and track individual review items with their status.
    """
    __tablename__ = "coach_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )

    # What this session is for
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(200), nullable=False)

    # Session state
    readiness: Mapped[str] = mapped_column(String(50), nullable=False)
    active_item_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # Items stored as JSONB array (HumanAuditItem objects)
    items: Mapped[list] = mapped_column(JSONB, nullable=False)

    # Audit run reference
    audit_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audit_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<CoachSession(target='{self.target_type}:{self.target_id}', readiness='{self.readiness}', {self.completed_count}/{self.total_count})>"
