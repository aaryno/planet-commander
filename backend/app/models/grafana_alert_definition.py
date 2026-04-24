"""Grafana Alert Definition model."""
import datetime
import uuid
from typing import Optional

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GrafanaAlertDefinition(Base):
    """
    Grafana alert definition from planet-grafana-cloud-users repo.

    Stores parsed alert definitions including queries, thresholds, runbooks.
    """
    __tablename__ = "grafana_alert_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )

    # Alert identity
    alert_name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)

    # Ownership
    team: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    project: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Alert configuration
    alert_expr: Mapped[str] = mapped_column(Text, nullable=False)
    alert_for: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Metadata (JSONB)
    labels: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    annotations: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Parsed fields (for quick access without JSONB queries)
    severity: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    runbook_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Sync metadata
    file_modified_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_synced_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Soft delete
    deleted_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def is_active(self) -> bool:
        """Check if alert is active (not deleted)."""
        return self.deleted_at is None

    @property
    def is_critical(self) -> bool:
        """Check if alert has critical severity."""
        return self.severity == "critical"

    @property
    def is_warning(self) -> bool:
        """Check if alert has warning severity."""
        return self.severity == "warning"

    @property
    def has_runbook(self) -> bool:
        """Check if alert has runbook URL."""
        return bool(self.runbook_url)

    def __repr__(self) -> str:
        return f"<GrafanaAlertDefinition {self.alert_name} ({self.team}/{self.project})>"
