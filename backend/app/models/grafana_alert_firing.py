"""Grafana Alert Firing model."""
import datetime
import uuid
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GrafanaAlertFiring(Base):
    """
    Historical firing of a Grafana alert.

    Tracks when alerts fired, resolved, and their values.
    Fetched from Grafana API or parsed from Slack messages.
    """
    __tablename__ = "grafana_alert_firings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )

    # Link to definition
    alert_definition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grafana_alert_definitions.id"),
        nullable=True
    )
    alert_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Firing details
    fired_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Instance metadata
    labels: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    annotations: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    fingerprint: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Alert value
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # External reference
    external_alert_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )

    # Metadata
    fetched_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    @property
    def duration_seconds(self) -> Optional[int]:
        """Calculate firing duration in seconds."""
        if not self.resolved_at:
            return None
        delta = self.resolved_at - self.fired_at
        return int(delta.total_seconds())

    @property
    def is_resolved(self) -> bool:
        """Check if alert firing is resolved."""
        return self.resolved_at is not None

    @property
    def is_firing(self) -> bool:
        """Check if alert is currently firing."""
        return self.state == "firing"

    def __repr__(self) -> str:
        status = "resolved" if self.is_resolved else "firing"
        return f"<GrafanaAlertFiring {self.alert_name} @ {self.fired_at} ({status})>"
