"""Git Branch model for Planet Commander Phase 1."""
import datetime
import enum
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class BranchStatus(str, enum.Enum):
    """Status of a git branch."""
    ACTIVE = "active"
    MERGED = "merged"
    STALE = "stale"
    ABANDONED = "abandoned"


class GitBranch(Base):
    """
    Git branch tracking.

    Tracks branches across repositories to enable context resolution and
    worktree management.
    """
    __tablename__ = "git_branches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    repo: Mapped[str] = mapped_column(String(200), nullable=False)
    branch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    head_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(200), nullable=False)

    status: Mapped[BranchStatus] = mapped_column(
        nullable=False, default=BranchStatus.ACTIVE
    )

    ahead_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    behind_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    has_open_pr: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pr_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # FK to pull_requests (future)

    # Planet Commander fields
    context_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_contexts.id", ondelete="SET NULL"),
        nullable=True,
    )
    linked_ticket_key_guess: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # Extracted from branch name
    is_inferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    worktrees: Mapped[list["Worktree"]] = relationship(
        "Worktree", back_populates="branch", cascade="all, delete-orphan"
    )
