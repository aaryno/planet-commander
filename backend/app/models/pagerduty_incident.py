"""PagerDuty Incident model."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, String, Integer, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PagerDutyIncident(Base):
    """PagerDuty incident cache."""

    __tablename__ = "pagerduty_incidents"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Core fields
    external_incident_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    incident_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # triggered, acknowledged, resolved
    urgency: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)  # high, low

    # Service and escalation
    priority = Column(JSONB)  # {id, summary, description}
    service_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    service_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    escalation_policy_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    escalation_policy_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Assignment and teams
    assigned_to = Column(JSONB)  # [{id, email, name}]
    teams = Column(JSONB)  # [{id, name}]

    # Timestamps
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status_change_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # URLs and keys
    incident_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    html_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    incident_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Additional data
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acknowledgements = Column(JSONB)  # [{at, by}]
    assignments = Column(JSONB)  # Full assignment history
    log_entries = Column(JSONB)  # Timeline events
    alerts = Column(JSONB)  # Alert details

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_pd_incidents_external', 'external_incident_id'),
        Index('idx_pd_incidents_number', 'incident_number'),
        Index('idx_pd_incidents_status', 'status'),
        Index('idx_pd_incidents_urgency', 'urgency'),
        Index('idx_pd_incidents_service', 'service_id'),
        Index('idx_pd_incidents_triggered', 'triggered_at', postgresql_ops={'triggered_at': 'DESC'}),
        Index('idx_pd_incidents_resolved', 'resolved_at', postgresql_where=Column('resolved_at').isnot(None)),
        Index('idx_pd_incidents_team', 'teams', postgresql_using='gin'),
    )

    # Computed properties

    @property
    def is_active(self) -> bool:
        """Check if incident is active (triggered or acknowledged)."""
        return self.status in ["triggered", "acknowledged"]

    @property
    def is_resolved(self) -> bool:
        """Check if incident is resolved."""
        return self.status == "resolved"

    @property
    def is_high_urgency(self) -> bool:
        """Check if incident is high urgency."""
        return self.urgency == "high"

    @property
    def duration_minutes(self) -> Optional[int]:
        """Calculate incident duration in minutes.

        For resolved incidents: triggered → resolved
        For active incidents: None
        """
        if not self.resolved_at:
            return None
        delta = self.resolved_at - self.triggered_at
        return int(delta.total_seconds() / 60)

    @property
    def time_to_ack_minutes(self) -> Optional[int]:
        """Calculate time to acknowledgement in minutes.

        Returns None if not yet acknowledged.
        """
        if not self.acknowledged_at:
            return None
        delta = self.acknowledged_at - self.triggered_at
        return int(delta.total_seconds() / 60)

    @property
    def assigned_user_names(self) -> List[str]:
        """Get list of assigned user names."""
        if not self.assigned_to:
            return []
        return [user.get("name", "Unknown") for user in self.assigned_to]

    @property
    def team_names(self) -> List[str]:
        """Get list of team names."""
        if not self.teams:
            return []
        return [team.get("name", "Unknown") for team in self.teams]

    @property
    def is_compute_team(self) -> bool:
        """Check if incident belongs to Compute team."""
        team_names_lower = [t.lower() for t in self.team_names]
        return any("compute" in t for t in team_names_lower)

    @property
    def age_minutes(self) -> int:
        """Get incident age in minutes since triggered."""
        delta = datetime.utcnow() - self.triggered_at.replace(tzinfo=None)
        return int(delta.total_seconds() / 60)

    def __repr__(self) -> str:
        """String representation."""
        return f"<PagerDutyIncident #{self.incident_number}: {self.title[:50]}... ({self.status})>"
