"""Agent Context Queue model — durable per-agent queue for Slack and other context updates."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String, Text, DateTime, Index, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AgentContextQueueItem(Base):
    """A queued context update waiting to be delivered to an agent.

    Items are enqueued when relevant Slack activity is detected for an agent's
    JIRA key, branch, or MR. They are drained and injected when:
    1. The user sends the next message
    2. The agent finishes processing (idle hook)
    3. High-priority items may be escalated immediately
    """

    __tablename__ = "agent_context_queue"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)
    jira_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="slack")
    source_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # dedup key
    channel_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    permalink: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal")  # normal | high
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    ttl_expiry: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=24),
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_acq_agent_pending", "agent_id", "delivered_at", postgresql_where=delivered_at.is_(None)),
        Index("ix_acq_ttl", "ttl_expiry"),
        Index("ix_acq_source_id", "agent_id", "source_id"),
    )
