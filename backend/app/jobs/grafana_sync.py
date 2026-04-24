"""Background job for syncing Grafana alert definitions."""

import logging
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.grafana_alert_definition import GrafanaAlertDefinition
from app.models.entity_link import EntityLink, LinkType, LinkSourceType
from app.models.jira_issue import JiraIssue
from app.services.grafana_alert_service import GrafanaAlertService
from app.services.entity_link import EntityLinkService

logger = logging.getLogger(__name__)


async def sync_alert_definitions() -> Dict:
    """Sync Grafana alert definitions from repository.

    Scans ~/code/build-deploy/planet-grafana-cloud-users/modules/
    for alert directory structure and updates database.

    Returns:
        Dict with sync statistics
    """
    logger.info("Starting Grafana alert definitions sync")

    async with async_session() as db:
        service = GrafanaAlertService(db)

        try:
            stats = await service.scan_alert_repo()

            logger.info(
                f"Alert sync complete: {stats['total_scanned']} scanned, "
                f"{stats['new_alerts']} new, {stats['updated_alerts']} updated, "
                f"{len(stats.get('errors', []))} errors"
            )

            return stats

        except Exception as e:
            logger.error(f"Alert sync failed: {e}", exc_info=True)
            return {
                "total_scanned": 0,
                "new_alerts": 0,
                "updated_alerts": 0,
                "errors": [str(e)],
            }


async def link_alerts_to_jira() -> Dict:
    """Auto-link alert definitions to JIRA issues.

    Creates entity links when:
    1. Alert name contains JIRA ticket key (e.g., "jobs-COMPUTE-1234-alert")
    2. JIRA issue summary/description mentions alert name

    Returns:
        Dict with linking statistics
    """
    logger.info("Starting alert → JIRA auto-linking")

    async with async_session() as db:
        try:
            # Get all alerts and JIRA issues
            alerts_result = await db.execute(
                select(GrafanaAlertDefinition)
            )
            alerts = alerts_result.scalars().all()

            jira_result = await db.execute(
                select(JiraIssue)
            )
            jira_issues = jira_result.scalars().all()

            links_created = 0

            # Link alerts to JIRA by ticket key in alert name
            for alert in alerts:
                alert_name = alert.alert_name

                # Check if alert name contains JIRA key pattern
                for issue in jira_issues:
                    jira_key = issue.jira_key

                    # Check if alert name contains this JIRA key
                    if jira_key.upper() in alert_name.upper():
                        # Check if link already exists
                        existing_link = await db.execute(
                            select(EntityLink).where(
                                EntityLink.from_type == "grafana_alert",
                                EntityLink.from_id == str(alert.id),
                                EntityLink.to_type == "jira_issue",
                                EntityLink.to_id == str(issue.id),
                            )
                        )

                        if not existing_link.scalar_one_or_none():
                            # Create link: Grafana alert → JIRA issue
                            link_service = EntityLinkService(db)

                            await link_service.create_link(
                                from_type="grafana_alert",
                                from_id=str(alert.id),
                                to_type="jira_issue",
                                to_id=str(issue.id),
                                link_type=LinkType.REFERENCES_ALERT,
                                source_type="inferred",
                                confidence_score=0.95,
                            )
                            links_created += 1
                            logger.debug(f"Linked alert {alert_name} → JIRA {jira_key}")

                    # Check if JIRA summary/description mentions alert name
                    issue_text = f"{issue.summary or ''} {issue.description or ''}".lower()
                    if alert_name.lower() in issue_text:
                        # Check if link already exists
                        existing_link = await db.execute(
                            select(EntityLink).where(
                                EntityLink.from_type == "grafana_alert",
                                EntityLink.from_id == str(alert.id),
                                EntityLink.to_type == "jira_issue",
                                EntityLink.to_id == str(issue.id),
                            )
                        )

                        if not existing_link.scalar_one_or_none():
                            # Create link: Grafana alert → JIRA issue
                            link_service = EntityLinkService(db)

                            await link_service.create_link(
                                from_type="grafana_alert",
                                from_id=str(alert.id),
                                to_type="jira_issue",
                                to_id=str(issue.id),
                                link_type=LinkType.DISCUSSED_ALERT,
                                source_type="inferred",
                                confidence_score=0.90,
                            )
                            links_created += 1
                            logger.debug(f"Linked alert {alert_name} → JIRA {issue.jira_key} (text match)")

            await db.commit()

            logger.info(f"Alert → JIRA linking complete: {links_created} links created")

            return {
                "alerts_processed": len(alerts),
                "jira_issues_processed": len(jira_issues),
                "links_created": links_created,
            }

        except Exception as e:
            logger.error(f"Alert → JIRA linking failed: {e}", exc_info=True)
            return {
                "alerts_processed": 0,
                "jira_issues_processed": 0,
                "links_created": 0,
                "error": str(e),
            }
