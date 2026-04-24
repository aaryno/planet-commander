"""
Warning Escalation Metrics Model

Tracks historical escalation rates per alert for learning and prediction.
"""

import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WarningEscalationMetrics(Base):
    """
    Historical escalation metrics per alert name.

    Tracks:
    - How many times this alert appeared as a warning
    - How many times it escalated to critical
    - How many times it auto-cleared without escalating
    - Average time to escalation/clear
    - Escalation rate (for prediction)
    """
    __tablename__ = "warning_escalation_metrics"

    # Primary key
    alert_name: Mapped[str] = mapped_column(
        String(200), primary_key=True, nullable=False
    )

    # Optional system classification
    system: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    # Counts
    total_warnings: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    escalated_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    auto_cleared_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Calculated metrics
    escalation_rate: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    avg_time_to_escalation_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    avg_time_to_clear_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    # Timestamps
    last_seen: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_escalated: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_calculated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
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

    @property
    def escalation_rate_percent(self) -> float:
        """Get escalation rate as percentage (0-100)."""
        if self.escalation_rate is not None:
            return self.escalation_rate * 100
        return 0.0

    @property
    def avg_time_to_escalation_minutes(self) -> int | None:
        """Get average time to escalation in minutes."""
        if self.avg_time_to_escalation_seconds:
            return self.avg_time_to_escalation_seconds // 60
        return None

    @property
    def avg_time_to_clear_minutes(self) -> int | None:
        """Get average time to clear in minutes."""
        if self.avg_time_to_clear_seconds:
            return self.avg_time_to_clear_seconds // 60
        return None

    def __repr__(self) -> str:
        return (
            f"<WarningEscalationMetrics("
            f"alert_name='{self.alert_name}', "
            f"total={self.total_warnings}, "
            f"escalated={self.escalated_count}, "
            f"rate={self.escalation_rate:.1%} if self.escalation_rate else 0)>"
        )
