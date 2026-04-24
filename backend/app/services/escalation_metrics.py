"""
Escalation Metrics Service

Calculates historical escalation rates from warning events.
Used for improving escalation probability predictions over time.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.warning_event import WarningEvent
from app.models.warning_escalation_metrics import WarningEscalationMetrics

logger = logging.getLogger(__name__)


class EscalationMetricsService:
    """
    Calculate and update escalation metrics from historical warning events.

    Tracks:
    - How often each alert escalates vs. auto-clears
    - Average time to escalation/clear
    - Escalation rate for prediction
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize escalation metrics service.

        Args:
            db: Database session
        """
        self.db = db

    async def calculate_all_metrics(self) -> dict:
        """
        Calculate metrics for all alerts.

        Queries warning_events table and updates warning_escalation_metrics.

        Returns:
            Statistics about metrics calculated
        """
        logger.info("Calculating escalation metrics for all alerts")

        stats = {
            "alerts_processed": 0,
            "metrics_created": 0,
            "metrics_updated": 0,
            "errors": [],
        }

        # Get all distinct alert names from warning_events
        result = await self.db.execute(
            select(WarningEvent.alert_name, WarningEvent.system)
            .distinct()
            .where(WarningEvent.alert_name.isnot(None))
        )

        alert_systems = result.all()

        for alert_name, system in alert_systems:
            try:
                metrics = await self.calculate_metrics_for_alert(alert_name, system)

                if metrics:
                    stats["alerts_processed"] += 1

                    # Check if metrics already exist
                    existing = await self.db.execute(
                        select(WarningEscalationMetrics).where(
                            WarningEscalationMetrics.alert_name == alert_name
                        )
                    )
                    existing_metrics = existing.scalar_one_or_none()

                    if existing_metrics:
                        # Update existing
                        existing_metrics.system = system
                        existing_metrics.total_warnings = metrics["total_warnings"]
                        existing_metrics.escalated_count = metrics["escalated_count"]
                        existing_metrics.auto_cleared_count = metrics[
                            "auto_cleared_count"
                        ]
                        existing_metrics.escalation_rate = metrics["escalation_rate"]
                        existing_metrics.avg_time_to_escalation_seconds = metrics[
                            "avg_time_to_escalation_seconds"
                        ]
                        existing_metrics.avg_time_to_clear_seconds = metrics[
                            "avg_time_to_clear_seconds"
                        ]
                        existing_metrics.last_seen = metrics["last_seen"]
                        existing_metrics.last_escalated = metrics["last_escalated"]
                        existing_metrics.last_calculated_at = datetime.now(timezone.utc)

                        stats["metrics_updated"] += 1
                    else:
                        # Create new
                        new_metrics = WarningEscalationMetrics(
                            alert_name=alert_name,
                            system=system,
                            total_warnings=metrics["total_warnings"],
                            escalated_count=metrics["escalated_count"],
                            auto_cleared_count=metrics["auto_cleared_count"],
                            escalation_rate=metrics["escalation_rate"],
                            avg_time_to_escalation_seconds=metrics[
                                "avg_time_to_escalation_seconds"
                            ],
                            avg_time_to_clear_seconds=metrics[
                                "avg_time_to_clear_seconds"
                            ],
                            last_seen=metrics["last_seen"],
                            last_escalated=metrics["last_escalated"],
                            last_calculated_at=datetime.now(timezone.utc),
                        )

                        self.db.add(new_metrics)
                        stats["metrics_created"] += 1

                    logger.debug(
                        f"Metrics for {alert_name}: "
                        f"total={metrics['total_warnings']}, "
                        f"escalated={metrics['escalated_count']}, "
                        f"rate={metrics['escalation_rate']:.1%}"
                    )

            except Exception as e:
                error_msg = f"Error calculating metrics for {alert_name}: {e}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)

        await self.db.commit()

        logger.info(
            f"Escalation metrics calculation complete: "
            f"{stats['alerts_processed']} alerts, "
            f"{stats['metrics_created']} created, "
            f"{stats['metrics_updated']} updated"
        )

        return stats

    async def calculate_metrics_for_alert(
        self, alert_name: str, system: Optional[str] = None
    ) -> Optional[dict]:
        """
        Calculate metrics for a specific alert.

        Args:
            alert_name: Alert name to calculate for
            system: Optional system filter

        Returns:
            Dict with metrics or None if no data
        """
        # Get all warnings for this alert
        query = select(WarningEvent).where(WarningEvent.alert_name == alert_name)

        if system:
            query = query.where(WarningEvent.system == system)

        result = await self.db.execute(query)
        warnings = list(result.scalars().all())

        if not warnings:
            return None

        # Count warnings by status
        total_warnings = len(warnings)
        escalated_count = sum(1 for w in warnings if w.escalated)
        auto_cleared_count = sum(1 for w in warnings if w.auto_cleared)

        # Calculate escalation rate
        # Only count warnings that have resolved (escalated or cleared)
        resolved_count = escalated_count + auto_cleared_count

        if resolved_count > 0:
            escalation_rate = escalated_count / resolved_count
        else:
            # No resolved warnings yet - use baseline
            escalation_rate = None

        # Calculate average time to escalation
        escalated_warnings = [w for w in warnings if w.escalated and w.escalated_at]
        if escalated_warnings:
            escalation_times = [
                (w.escalated_at - w.first_seen).total_seconds()
                for w in escalated_warnings
            ]
            avg_time_to_escalation_seconds = int(sum(escalation_times) / len(escalation_times))
        else:
            avg_time_to_escalation_seconds = None

        # Calculate average time to clear
        cleared_warnings = [w for w in warnings if w.auto_cleared and w.cleared_at]
        if cleared_warnings:
            clear_times = [
                (w.cleared_at - w.first_seen).total_seconds() for w in cleared_warnings
            ]
            avg_time_to_clear_seconds = int(sum(clear_times) / len(clear_times))
        else:
            avg_time_to_clear_seconds = None

        # Find last seen and last escalated
        last_seen = max((w.last_seen for w in warnings), default=None)
        last_escalated_warnings = [w for w in warnings if w.escalated and w.escalated_at]
        last_escalated = (
            max((w.escalated_at for w in last_escalated_warnings), default=None)
            if last_escalated_warnings
            else None
        )

        return {
            "total_warnings": total_warnings,
            "escalated_count": escalated_count,
            "auto_cleared_count": auto_cleared_count,
            "escalation_rate": escalation_rate,
            "avg_time_to_escalation_seconds": avg_time_to_escalation_seconds,
            "avg_time_to_clear_seconds": avg_time_to_clear_seconds,
            "last_seen": last_seen,
            "last_escalated": last_escalated,
        }

    async def get_metrics(self, alert_name: str) -> Optional[WarningEscalationMetrics]:
        """
        Get metrics for a specific alert.

        Args:
            alert_name: Alert name

        Returns:
            WarningEscalationMetrics or None
        """
        result = await self.db.execute(
            select(WarningEscalationMetrics).where(
                WarningEscalationMetrics.alert_name == alert_name
            )
        )

        return result.scalar_one_or_none()

    async def get_predicted_escalation_probability(
        self, alert_name: str, pattern_probability: float
    ) -> float:
        """
        Get improved escalation probability using historical data.

        Combines pattern-based probability with historical escalation rate.

        Args:
            alert_name: Alert name
            pattern_probability: Probability from pattern matching (0-1)

        Returns:
            Adjusted probability (0-1)
        """
        metrics = await self.get_metrics(alert_name)

        if not metrics or metrics.escalation_rate is None:
            # No historical data - use pattern probability
            return pattern_probability

        # Weighted average:
        # - If we have lots of data (total_warnings > 10), trust historical rate more
        # - If we have little data (total_warnings < 5), trust pattern more

        if metrics.total_warnings >= 10:
            # High confidence in historical data (80% weight)
            return 0.2 * pattern_probability + 0.8 * metrics.escalation_rate
        elif metrics.total_warnings >= 5:
            # Medium confidence (50% weight)
            return 0.5 * pattern_probability + 0.5 * metrics.escalation_rate
        else:
            # Low confidence (20% weight)
            return 0.8 * pattern_probability + 0.2 * metrics.escalation_rate
