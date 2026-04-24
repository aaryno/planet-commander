"""Worktree model for Planet Commander Phase 1."""
import datetime
import enum
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WorktreeStatus(str, enum.Enum):
    """Status of a git worktree."""
    ACTIVE = "active"
    DIRTY = "dirty"
    CLEAN = "clean"
    STALE = "stale"
    MERGED = "merged"
    ABANDONED = "abandoned"
    ORPHANED = "orphaned"


class Worktree(Base):
    """
    Git worktree state tracking.

    Tracks worktrees across repositories to enable execution context visibility
    and worktree health monitoring.
    """
    __tablename__ = "worktrees"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    repo: Mapped[str] = mapped_column(String(200), nullable=False)
    path: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("git_branches.id", ondelete="CASCADE"), nullable=False
    )

    status: Mapped[WorktreeStatus] = mapped_column(
        nullable=False, default=WorktreeStatus.ACTIVE
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
    last_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    has_uncommitted_changes: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_untracked_files: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_rebasing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_out_of_date: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    branch: Mapped["GitBranch"] = relationship("GitBranch", back_populates="worktrees")
