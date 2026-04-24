"""Background job for enriching references with PagerDuty data."""

import logging
from typing import Dict

from app.database import async_session
from app.models import JiraIssue, Agent, EntityLink, LinkType, LinkSourceType
from app.services.pagerduty_service import PagerDutyService
from app.services.entity_link import EntityLinkService
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def enrich_pagerduty_references() -> Dict:
    """Scan entities for PagerDuty references and enrich.

    Scans:
    - JIRA issue descriptions/comments
    - Agent chat messages (via description field)
    - Slack threads (future)

    Creates entity links between entities and PagerDuty incidents.
    Fetches incidents from PagerDuty if not in cache.

    Returns:
        Dictionary with enrichment statistics:
        {
            "jira_scanned": int,
            "agent_scanned": int,
            "references_found": int,
            "incidents_fetched": int,
            "links_created": int,
            "errors": [str]
        }
    """
    try:
        async with async_session() as db:
            pd_service = PagerDutyService(db)
            link_service = EntityLinkService(db)

            logger.info("Starting PagerDuty reference enrichment")

            stats = {
                "jira_scanned": 0,
                "agent_scanned": 0,
                "references_found": 0,
                "incidents_fetched": 0,
                "links_created": 0,
                "errors": []
            }

            # Scan JIRA issues
            result = await db.execute(
                select(JiraIssue)
                .order_by(JiraIssue.updated_at.desc())
                .limit(500)  # Most recent 500 issues
            )
            jira_issues = result.scalars().all()

            for issue in jira_issues:
                stats["jira_scanned"] += 1

                # Extract incident IDs from summary + description
                text = f"{issue.summary or ''} {issue.description or ''}"
                incident_ids = await pd_service.extract_incident_references(text)

                if incident_ids:
                    stats["references_found"] += len(incident_ids)

                    for incident_id in incident_ids:
                        try:
                            # Check if incident in cache
                            incident = await pd_service.get_incident_by_id(incident_id)
                            
                            # Fetch from PagerDuty if not cached
                            if not incident:
                                incident_data = await pd_service.fetch_incident_from_mcp(incident_id)
                                if incident_data:
                                    incident = await pd_service.sync_incident(incident_data)
                                    stats["incidents_fetched"] += 1

                            if incident:
                                # Create link: JIRA → escalated_to → PagerDuty
                                created = await link_service.create_link(
                                    from_type="jira_issue",
                                    from_id=str(issue.id),
                                    to_type="pagerduty_incident",
                                    to_id=str(incident.id),
                                    link_type=LinkType.ESCALATED_TO,
                                    source_type=LinkSourceType.INFERRED,
                                    confidence_score=0.95,  # High confidence for text match
                                )

                                if created:
                                    stats["links_created"] += 1
                                    logger.debug(
                                        f"Linked {issue.key} → PD#{incident.incident_number}"
                                    )

                        except Exception as e:
                            error_msg = f"Error enriching {issue.key} with PD {incident_id}: {e}"
                            logger.error(error_msg)
                            stats["errors"].append(error_msg)

            # Scan Agent chats
            result = await db.execute(select(Agent))
            agents = result.scalars().all()

            for agent in agents:
                stats["agent_scanned"] += 1

                # Extract from JIRA key + description
                text = f"{agent.jira_key or ''} {agent.description or ''}"
                incident_ids = await pd_service.extract_incident_references(text)

                if incident_ids:
                    stats["references_found"] += len(incident_ids)

                    for incident_id in incident_ids:
                        try:
                            # Get or fetch incident
                            incident = await pd_service.get_incident_by_id(incident_id)
                            if not incident:
                                incident_data = await pd_service.fetch_incident_from_mcp(incident_id)
                                if incident_data:
                                    incident = await pd_service.sync_incident(incident_data)
                                    stats["incidents_fetched"] += 1

                            if incident:
                                # Create link: Agent → discussed_in → PagerDuty
                                created = await link_service.create_link(
                                    from_type="agent",
                                    from_id=str(agent.id),
                                    to_type="pagerduty_incident",
                                    to_id=str(incident.id),
                                    link_type=LinkType.DISCUSSED_IN,
                                    source_type=LinkSourceType.INFERRED,
                                    confidence_score=0.90,
                                )

                                if created:
                                    stats["links_created"] += 1

                        except Exception as e:
                            error_msg = f"Error enriching agent {agent.id} with PD {incident_id}: {e}"
                            logger.error(error_msg)
                            stats["errors"].append(error_msg)

            await db.commit()

            logger.info(
                f"PagerDuty enrichment complete: {stats['jira_scanned']} JIRA + "
                f"{stats['agent_scanned']} agents scanned, {stats['references_found']} references found, "
                f"{stats['links_created']} links created, {stats['incidents_fetched']} incidents fetched"
            )

            return stats

    except Exception as e:
        logger.error(f"Error in PagerDuty enrichment: {e}", exc_info=True)
        return {
            "jira_scanned": 0,
            "agent_scanned": 0,
            "references_found": 0,
            "incidents_fetched": 0,
            "links_created": 0,
            "errors": [str(e)]
        }
