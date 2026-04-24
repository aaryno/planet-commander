"""
Warning Event Model - Proactive Incident Response

Tracks warnings from #compute-platform-warn Slack channel.
Enables prediction of which warnings will escalate to critical alerts.
"""

import datetime
import enum
import uuid

from sqlalchemy import Boolean, DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WarningSeverity(str, enum.Enum):
    """Severity level of warning."""
    WARNING = "warning"
    CRITICAL = "critical"
    INFO = "info"


class WarningEvent(Base):
    """
    Warning event from monitored Slack channels.

    Tracks warnings posted to #compute-platform-warn and similar channels.
    Used for escalation prediction and proactive incident response.
    """
    __tablename__ = "warning_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Alert identification
    alert_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    system: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    # Slack message reference
    channel_id: Mapped[str] = mapped_column(String(50), nullable=False)
    channel_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message_ts: Mapped[str] = mapped_column(String(50), nullable=False)
    thread_ts: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Severity
    severity: Mapped[WarningSeverity] = mapped_column(nullable=False, index=True)

    # Timing
    first_seen: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    last_seen: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Escalation tracking
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    escalated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Auto-clear tracking
    auto_cleared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cleared_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Escalation prediction
    escalation_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Work context references
    standby_context_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    incident_context_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Raw message data
    raw_message: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Metadata
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @property
    def is_active(self) -> bool:
        """Check if warning is still active (not escalated or cleared)."""
        return not self.escalated and not self.auto_cleared

    @property
    def age_minutes(self) -> int:
        """Calculate age of warning in minutes."""
        if self.first_seen:
            delta = datetime.datetime.now(datetime.timezone.utc) - self.first_seen
            return int(delta.total_seconds() / 60)
        return 0

    @property
    def escalation_risk_level(self) -> str:
        """Get human-readable escalation risk level."""
        if self.escalation_probability is None:
            return "unknown"
        elif self.escalation_probability >= 0.7:
            return "high"
        elif self.escalation_probability >= 0.4:
            return "medium"
        else:
            return "low"

    def __repr__(self) -> str:
        return (
            f"<WarningEvent(id={self.id}, "
            f"alert_name='{self.alert_name}', "
            f"severity={self.severity}, "
            f"escalation_prob={self.escalation_probability}, "
            f"escalated={self.escalated})>"
        )
