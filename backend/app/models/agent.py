import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    claude_session_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    claude_project_path: Mapped[str | None] = mapped_column(String(500))
    project: Mapped[str | None] = mapped_column(String(50))
    pid: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="dead")
    managed_by: Mapped[str] = mapped_column(String(20), nullable=False, default="vscode")
    title: Mapped[str | None] = mapped_column(Text)
    first_prompt: Mapped[str | None] = mapped_column(Text)
    working_directory: Mapped[str | None] = mapped_column(String(500))
    git_branch: Mapped[str | None] = mapped_column(String(200))
    worktree_path: Mapped[str | None] = mapped_column(String(500))
    jira_key: Mapped[str | None] = mapped_column(String(50))
    dev_env_url: Mapped[str | None] = mapped_column(String(500))
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_active_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    exit_code: Mapped[int | None] = mapped_column(Integer)
    hidden_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    resumed_from_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id")
    )

    # NEW: Chat-specific fields (Phase 1)
    external_chat_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    workspace_or_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_message_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    token_count_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contains_code: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    contains_ticket_reference: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    contains_worktree_reference: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    generation_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_chat_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    merged_into_summary_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # FK to summaries (Phase 2)
    context_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_contexts.id", ondelete="SET NULL"), nullable=True
    )
    origin_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    files_changed: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    mr_references: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    labels = relationship("AgentLabel", back_populates="agent", cascade="all, delete-orphan")
    artifacts = relationship("AgentArtifact", back_populates="agent", cascade="all, delete-orphan")


class AgentLabel(Base):
    __tablename__ = "agent_labels"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )
    label_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True
    )
    applied_by: Mapped[str] = mapped_column(String(20), default="user")
    applied_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    agent = relationship("Agent", back_populates="labels")
    label = relationship("Label")


class AgentArtifact(Base):
    __tablename__ = "agent_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE")
    )
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    path: Mapped[str | None] = mapped_column(String(1000))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    agent = relationship("Agent", back_populates="artifacts")


class AgentSearchIndex(Base):
    __tablename__ = "agent_search_index"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE")
    )
    content_type: Mapped[str | None] = mapped_column(String(20))
    content: Mapped[str | None] = mapped_column(Text)
