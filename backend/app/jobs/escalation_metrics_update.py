"""
Escalation Metrics Update Job

Calculates historical escalation rates from warning events.
Updates prediction model with real data.
"""

import logging

from app.database import async_session
from app.services.escalation_metrics import EscalationMetricsService

logger = logging.getLogger(__name__)


async def update_escalation_metrics() -> dict:
    """
    Update escalation metrics for all alerts.

    Calculates:
    - Total warnings per alert
    - Escalation rate (% that escalate vs. auto-clear)
    - Average time to escalation/clear
    - Last seen timestamp

    Returns:
        Statistics about metrics updated
    """
    try:
        async with async_session() as db:
            metrics_service = EscalationMetricsService(db)

            logger.info("Starting escalation metrics update")

            stats = await metrics_service.calculate_all_metrics()

            logger.info(
                f"Escalation metrics update complete: "
                f"{stats['alerts_processed']} alerts processed, "
                f"{stats['metrics_created']} created, "
                f"{stats['metrics_updated']} updated"
            )

            return stats

    except Exception as e:
        logger.error(f"Error updating escalation metrics: {e}", exc_info=True)
        return {
            "alerts_processed": 0,
            "metrics_created": 0,
            "metrics_updated": 0,
            "errors": [str(e)],
        }
