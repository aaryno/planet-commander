"""
JIRA Ticket Enrichment Background Job

Scans JIRA ticket descriptions and comments for references to external entities
(Slack threads, PagerDuty incidents) and creates EntityLinks.

This enables bidirectional linking:
- External entities → JIRA (already handled by existing jobs)
- JIRA → external entities (handled by this job)
"""

import logging
import uuid
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import (
    JiraIssue,
    EntityLink,
    PagerDutyIncident,
    LinkType,
    LinkSourceType,
)
from app.services.jira_reference_detector import JiraReferenceDetector
from app.services.entity_link import EntityLinkService

logger = logging.getLogger(__name__)


async def enrich_jira_tickets() -> Dict:
    """
    Scan JIRA tickets for references and create EntityLinks.

    Scans:
    - Active JIRA tickets (status not Done/Closed)
    - Ticket description (comments in future phases)

    Detects:
    - Slack thread URLs
    - PagerDuty incident IDs and URLs

    Creates EntityLinks:
    - jira_issue → slack_thread (REFERENCES_THREAD)
    - jira_issue → pagerduty_incident (REFERENCES_INCIDENT)

    Returns:
        Statistics: {
            "tickets_processed": int,
            "references_detected": int,
            "links_created": int,
            "links_skipped": int,  # Already exist
            "errors": [str]
        }
    """
    try:
        async with async_session() as db:
            detector = JiraReferenceDetector()
            link_service = EntityLinkService(db)

            logger.info("Starting JIRA ticket enrichment")

            stats = {
                "tickets_processed": 0,
                "references_detected": 0,
                "links_created": 0,
                "links_skipped": 0,
                "errors": [],
            }

            # Get active JIRA tickets (not Done/Closed)
            # Limit to recent 500 to avoid overwhelming the system
            result = await db.execute(
                select(JiraIssue)
                .where(JiraIssue.status.notin_(["Done", "Closed"]))
                .order_by(JiraIssue.updated_at.desc())
                .limit(500)
            )
            tickets = result.scalars().all()

            logger.info(f"Scanning {len(tickets)} active JIRA tickets")

            for ticket in tickets:
                stats["tickets_processed"] += 1

                # Combine summary + description for scanning
                # (In future: also scan comments)
                text = f"{ticket.summary or ''}\n{ticket.description or ''}"

                # Detect all references
                references = detector.detect_all(text)
                stats["references_detected"] += len(references)

                if not references:
                    continue

                logger.debug(
                    f"Found {len(references)} references in {ticket.key}"
                )

                # Create EntityLinks for each reference
                for ref in references:
                    try:
                        # Resolve entity ID (lookup in DB or use reference ID)
                        entity_id = await _resolve_entity_id(
                            db, ref.entity_type, ref.entity_id
                        )

                        if not entity_id:
                            logger.debug(
                                f"Skipping {ref.entity_type} {ref.entity_id} - not in DB"
                            )
                            continue

                        # Create link: JIRA → entity
                        created = await link_service.create_link(
                            from_type="jira_issue",
                            from_id=str(ticket.id),
                            to_type=ref.entity_type,
                            to_id=entity_id,
                            link_type=ref.link_type.value,
                            source_type=LinkSourceType.INFERRED,
                            confidence_score=ref.confidence,
                        )

                        if created:
                            stats["links_created"] += 1
                            logger.debug(
                                f"Linked {ticket.key} → {ref.entity_type} {ref.entity_id}"
                            )
                        else:
                            stats["links_skipped"] += 1

                    except Exception as e:
                        error_msg = (
                            f"Error linking {ticket.key} → {ref.entity_type} "
                            f"{ref.entity_id}: {e}"
                        )
                        logger.error(error_msg)
                        stats["errors"].append(error_msg)

            await db.commit()

            logger.info(
                f"JIRA enrichment complete: {stats['tickets_processed']} tickets, "
                f"{stats['references_detected']} references, "
                f"{stats['links_created']} links created, "
                f"{stats['links_skipped']} skipped"
            )

            return stats

    except Exception as e:
        logger.error(f"Error in JIRA enrichment: {e}", exc_info=True)
        return {
            "tickets_processed": 0,
            "references_detected": 0,
            "links_created": 0,
            "links_skipped": 0,
            "errors": [str(e)],
        }


async def _resolve_entity_id(
    db: AsyncSession, entity_type: str, entity_ref: str
) -> str | None:
    """
    Resolve entity reference to database ID.

    For entities in our DB (PagerDuty), look up by external ID.
    For entities not yet in DB (Slack threads), store reference directly.

    Args:
        db: Database session
        entity_type: Type of entity ("slack_thread", "pagerduty_incident")
        entity_ref: Reference ID from detector

    Returns:
        Entity ID to use in EntityLink.to_id, or None if entity not found
    """
    if entity_type == "pagerduty_incident":
        # Look up PagerDuty incident by external_incident_id
        # Reference can be: PD-ABC123 or just ABC123 (from URL)

        # Normalize to PD-XXX format
        if not entity_ref.startswith("PD-"):
            entity_ref = f"PD-{entity_ref}"

        # Query by external_incident_id
        result = await db.execute(
            select(PagerDutyIncident).where(
                PagerDutyIncident.external_incident_id == entity_ref
            )
        )
        incident = result.scalar_one_or_none()

        if incident:
            return str(incident.id)
        else:
            logger.debug(
                f"PagerDuty incident {entity_ref} not in database - skipping"
            )
            return None

    elif entity_type == "slack_thread":
        # For now, store Slack thread reference directly in to_id
        # Format: "channel_id:timestamp"
        # Future: Create SlackThread model and look up by channel+timestamp
        return entity_ref

    else:
        logger.warning(f"Unknown entity type: {entity_type}")
        return None
