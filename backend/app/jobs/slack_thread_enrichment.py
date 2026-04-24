"""Background job for enriching Slack threads with entity links."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy import select

from app.database import async_session
from app.models import (
    SlackThread,
    JiraIssue,
    PagerDutyIncident,
    GitLabMergeRequest,
    EntityLink,
    LinkType,
    LinkSourceType,
    LinkStatus,
)
from app.services.entity_link import EntityLinkService

logger = logging.getLogger(__name__)


async def enrich_slack_thread_links() -> Dict:
    """Create entity links for Slack threads.

    For each recent Slack thread:
    - Link to referenced JIRA tickets (DISCUSSED_IN_SLACK)
    - Link to referenced PagerDuty incidents (DISCUSSED_IN_SLACK)
    - Link to referenced GitLab MRs (DISCUSSED_IN_SLACK)

    Returns:
        Dictionary with enrichment statistics:
        {
            "threads_processed": int,
            "jira_links_created": int,
            "pagerduty_links_created": int,
            "gitlab_links_created": int,
            "total_links_created": int,
            "errors": [str]
        }
    """
    start_time = datetime.utcnow()
    logger.info("Starting Slack thread enrichment")

    try:
        async with async_session() as db:
            link_service = EntityLinkService(db)

            stats = {
                "threads_processed": 0,
                "jira_links_created": 0,
                "pagerduty_links_created": 0,
                "gitlab_links_created": 0,
                "total_links_created": 0,
                "errors": []
            }

            # Fetch recent Slack threads (last 30 days)
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            result = await db.execute(
                select(SlackThread)
                .where(SlackThread.fetched_at >= cutoff)
                .order_by(SlackThread.fetched_at.desc())
                .limit(1000)  # Process up to 1000 threads
            )
            threads = result.scalars().all()

            logger.info(f"Processing {len(threads)} Slack threads for entity linking")

            for thread in threads:
                stats["threads_processed"] += 1

                # Link to JIRA tickets
                if thread.jira_keys:
                    for jira_key in thread.jira_key_list:
                        try:
                            jira_result = await db.execute(
                                select(JiraIssue).where(
                                    JiraIssue.external_key == jira_key.upper()
                                )
                            )
                            jira_issue = jira_result.scalar_one_or_none()

                            if jira_issue:
                                link = await link_service.create_link(
                                    from_type="jira_issue",
                                    from_id=str(jira_issue.id),
                                    to_type="slack_thread",
                                    to_id=str(thread.id),
                                    link_type=LinkType.DISCUSSED_IN_SLACK,
                                    source_type=LinkSourceType.INFERRED,
                                    confidence_score=0.95,
                                    status=LinkStatus.CONFIRMED,
                                )
                                if link:
                                    stats["jira_links_created"] += 1
                                    stats["total_links_created"] += 1
                        except Exception as e:
                            logger.debug(f"JIRA link failed for {jira_key} on thread {thread.id}: {e}")

                # Link to PagerDuty incidents
                if thread.pagerduty_incident_ids:
                    for incident_id in thread.pagerduty_incident_list:
                        try:
                            pd_result = await db.execute(
                                select(PagerDutyIncident).where(
                                    PagerDutyIncident.external_incident_id == incident_id
                                )
                            )
                            pd_incident = pd_result.scalar_one_or_none()

                            if pd_incident:
                                link = await link_service.create_link(
                                    from_type="pagerduty_incident",
                                    from_id=str(pd_incident.id),
                                    to_type="slack_thread",
                                    to_id=str(thread.id),
                                    link_type=LinkType.DISCUSSED_IN_SLACK,
                                    source_type=LinkSourceType.INFERRED,
                                    confidence_score=0.90,
                                    status=LinkStatus.CONFIRMED,
                                )
                                if link:
                                    stats["pagerduty_links_created"] += 1
                                    stats["total_links_created"] += 1
                        except Exception as e:
                            logger.debug(f"PD link failed for {incident_id} on thread {thread.id}: {e}")

                # Link to GitLab MRs
                if thread.gitlab_mr_refs:
                    for mr_ref in thread.gitlab_mr_list:
                        try:
                            mr_number = int(mr_ref.lstrip("!"))
                        except ValueError:
                            continue

                        try:
                            gitlab_result = await db.execute(
                                select(GitLabMergeRequest).where(
                                    GitLabMergeRequest.external_mr_id == mr_number
                                )
                            )
                            gitlab_mr = gitlab_result.scalar_one_or_none()

                            if gitlab_mr:
                                link = await link_service.create_link(
                                    from_type="gitlab_merge_request",
                                    from_id=str(gitlab_mr.id),
                                    to_type="slack_thread",
                                    to_id=str(thread.id),
                                    link_type=LinkType.DISCUSSED_IN_SLACK,
                                    source_type=LinkSourceType.INFERRED,
                                    confidence_score=0.85,
                                    status=LinkStatus.CONFIRMED,
                                )
                                if link:
                                    stats["gitlab_links_created"] += 1
                                    stats["total_links_created"] += 1
                        except Exception as e:
                            logger.debug(f"MR link failed for {mr_ref} on thread {thread.id}: {e}")

            # Commit all changes
            await db.commit()

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Slack thread enrichment complete: {stats['threads_processed']} threads, "
                f"{stats['total_links_created']} links created "
                f"(JIRA: {stats['jira_links_created']}, "
                f"PD: {stats['pagerduty_links_created']}, "
                f"GitLab: {stats['gitlab_links_created']}) "
                f"in {duration:.1f}s"
            )

            return {
                "records_processed": stats["total_links_created"],
                **stats
            }

    except Exception as e:
        logger.error(f"Slack thread enrichment failed: {e}", exc_info=True)
        raise
