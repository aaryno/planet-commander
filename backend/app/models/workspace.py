import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str | None] = mapped_column(Text)
    project: Mapped[str] = mapped_column(String(50), nullable=False)
    created_from_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_from_id: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_active_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    archived_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    # Relationships
    jira_tickets = relationship(
        "WorkspaceJiraTicket", back_populates="workspace", cascade="all, delete-orphan"
    )
    agents = relationship(
        "WorkspaceAgent", back_populates="workspace", cascade="all, delete-orphan"
    )
    branches = relationship(
        "WorkspaceBranch", back_populates="workspace", cascade="all, delete-orphan"
    )
    merge_requests = relationship(
        "WorkspaceMR", back_populates="workspace", cascade="all, delete-orphan"
    )
    deployments = relationship(
        "WorkspaceDeployment", back_populates="workspace", cascade="all, delete-orphan"
    )


class WorkspaceJiraTicket(Base):
    __tablename__ = "workspace_jira_tickets"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    jira_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    description_expanded: Mapped[bool] = mapped_column(Boolean, default=False)
    comments_expanded: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    workspace = relationship("Workspace", back_populates="jira_tickets")


class WorkspaceAgent(Base):
    __tablename__ = "workspace_agents"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=True)
    added_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    workspace = relationship("Workspace", back_populates="agents")
    agent = relationship("Agent")


class WorkspaceAgentJira(Base):
    __tablename__ = "workspace_agent_jira"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    jira_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    linked_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["workspace_agents.workspace_id", "workspace_agents.agent_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "jira_key"],
            ["workspace_jira_tickets.workspace_id", "workspace_jira_tickets.jira_key"],
            ondelete="CASCADE",
        ),
    )


class WorkspaceBranch(Base):
    __tablename__ = "workspace_branches"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    branch_name: Mapped[str] = mapped_column(String(200), primary_key=True)
    worktree_path: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    added_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    workspace = relationship("Workspace", back_populates="branches")


class WorkspaceBranchJira(Base):
    __tablename__ = "workspace_branch_jira"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    branch_name: Mapped[str] = mapped_column(String(200), primary_key=True)
    jira_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    linked_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "branch_name"],
            ["workspace_branches.workspace_id", "workspace_branches.branch_name"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "jira_key"],
            ["workspace_jira_tickets.workspace_id", "workspace_jira_tickets.jira_key"],
            ondelete="CASCADE",
        ),
    )


class WorkspaceMR(Base):
    __tablename__ = "workspace_mrs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    mr_project: Mapped[str] = mapped_column(String(100), primary_key=True)
    mr_iid: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str | None] = mapped_column(String(20))
    url: Mapped[str | None] = mapped_column(String(500))
    added_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    workspace = relationship("Workspace", back_populates="merge_requests")


class WorkspaceDeployment(Base):
    __tablename__ = "workspace_deployments"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    environment: Mapped[str] = mapped_column(String(100), primary_key=True)
    namespace: Mapped[str] = mapped_column(String(100), primary_key=True, default="")
    version: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str | None] = mapped_column(String(20))
    url: Mapped[str | None] = mapped_column(String(500))
    added_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    workspace = relationship("Workspace", back_populates="deployments")
