"""Background job for syncing PagerDuty incidents."""

import logging
from typing import Dict
from datetime import datetime, timedelta

from app.database import async_session
from app.services.pagerduty_service import PagerDutyService

logger = logging.getLogger(__name__)


async def sync_pagerduty_incidents() -> Dict:
    """Sync recent PagerDuty incidents from Compute team.

    Fetches incidents from last 7 days via MCP and syncs to database.
    Runs every 30 minutes as background job.

    Returns:
        Dictionary with sync statistics:
        {
            "total_fetched": int,
            "synced": int,
            "errors": [str]
        }
    """
    try:
        async with async_session() as db:
            service = PagerDutyService(db)
            logger.info("Starting PagerDuty incident sync")

            # Fetch incidents from last 7 days
            since = datetime.utcnow() - timedelta(days=7)
            incidents_data = await service.fetch_recent_incidents(
                statuses=["triggered", "acknowledged", "resolved"],
                team_ids=[PagerDutyService.COMPUTE_TEAM_ESCALATION_POLICY_ID],
                since=since,
                limit=100,
            )

            # Sync all
            stats = {
                "total_fetched": len(incidents_data),
                "synced": 0,
                "errors": []
            }

            for incident_data in incidents_data:
                try:
                    await service.sync_incident(incident_data)
                    stats["synced"] += 1
                except Exception as e:
                    error_msg = f"Error syncing incident {incident_data.get('id')}: {e}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)

            await db.commit()

            logger.info(
                f"PagerDuty sync complete: {stats['synced']}/{stats['total_fetched']} synced, "
                f"{len(stats['errors'])} errors"
            )

            return stats

    except Exception as e:
        logger.error(f"Error in PagerDuty sync: {e}", exc_info=True)
        return {
            "total_fetched": 0,
            "synced": 0,
            "errors": [str(e)]
        }
