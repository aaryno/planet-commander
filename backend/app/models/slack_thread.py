"""Slack Thread model."""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, String, Integer, Text, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SlackThread(Base):
    """Slack thread cache with cross-reference intelligence."""

    __tablename__ = "slack_threads"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Source information
    channel_id: Mapped[str] = mapped_column(String(50), nullable=False)
    channel_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    thread_ts: Mapped[str] = mapped_column(String(50), nullable=False)  # "1234567890.123456"
    permalink: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata
    participant_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    message_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Summary
    summary_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey('summaries.id', ondelete='SET NULL'),
        nullable=True
    )
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Context flags
    is_incident: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    severity: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # SEV1, SEV2, etc.
    incident_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    surrounding_context_fetched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Cross-references (extracted from messages)
    jira_keys = Column(JSONB)  # ["COMPUTE-1234", "WX-456"]
    pagerduty_incident_ids = Column(JSONB)  # ["PD-ABC123", "PD-DEF456"]
    gitlab_mr_refs = Column(JSONB)  # ["wx/wx!123", "jobs/jobs!456"]
    cross_channel_refs = Column(JSONB)  # ["#compute-platform", "#wx-dev"]

    # Raw data
    messages = Column(JSONB)  # Full message list
    participants = Column(JSONB)  # User list with profiles
    reactions = Column(JSONB)  # Reaction summary

    # Tracking
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Computed properties

    @property
    def is_active(self) -> bool:
        """Check if thread is recent (last 7 days)."""
        if not self.start_time:
            return False
        cutoff = datetime.utcnow() - timedelta(days=7)
        return self.start_time.replace(tzinfo=None) > cutoff

    @property
    def has_cross_references(self) -> bool:
        """Check if thread contains cross-references."""
        return any([
            self.jira_keys and len(self.jira_keys) > 0,
            self.pagerduty_incident_ids and len(self.pagerduty_incident_ids) > 0,
            self.gitlab_mr_refs and len(self.gitlab_mr_refs) > 0,
            self.cross_channel_refs and len(self.cross_channel_refs) > 0,
        ])

    @property
    def duration_display(self) -> Optional[str]:
        """Human-readable duration (2h 34m, 3d 2h, etc.)."""
        if self.duration_hours is None:
            return None

        total_minutes = int(self.duration_hours * 60)
        
        if total_minutes < 60:
            return f"{total_minutes}m"
        
        hours = total_minutes // 60
        minutes = total_minutes % 60
        
        if hours < 24:
            return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
        
        days = hours // 24
        remaining_hours = hours % 24
        
        if remaining_hours > 0:
            return f"{days}d {remaining_hours}h"
        return f"{days}d"

    @property
    def reference_count(self) -> int:
        """Total count of all cross-references."""
        count = 0
        if self.jira_keys:
            count += len(self.jira_keys)
        if self.pagerduty_incident_ids:
            count += len(self.pagerduty_incident_ids)
        if self.gitlab_mr_refs:
            count += len(self.gitlab_mr_refs)
        if self.cross_channel_refs:
            count += len(self.cross_channel_refs)
        return count

    @property
    def age_hours(self) -> Optional[float]:
        """Get thread age in hours since start."""
        if not self.start_time:
            return None
        delta = datetime.utcnow() - self.start_time.replace(tzinfo=None)
        return delta.total_seconds() / 3600

    @property
    def has_summary(self) -> bool:
        """Check if thread has a generated summary."""
        return self.summary_id is not None or self.summary_text is not None

    @property
    def jira_key_list(self) -> List[str]:
        """Get list of JIRA keys (empty if none)."""
        return self.jira_keys or []

    @property
    def pagerduty_incident_list(self) -> List[str]:
        """Get list of PagerDuty incident IDs (empty if none)."""
        return self.pagerduty_incident_ids or []

    @property
    def gitlab_mr_list(self) -> List[str]:
        """Get list of GitLab MR refs (empty if none)."""
        return self.gitlab_mr_refs or []

    @property
    def channel_ref_list(self) -> List[str]:
        """Get list of cross-channel references (empty if none)."""
        return self.cross_channel_refs or []

    def __repr__(self) -> str:
        """String representation."""
        return f"<SlackThread #{self.channel_name or self.channel_id}/{self.thread_ts} ({self.message_count or 0} msgs)>"
