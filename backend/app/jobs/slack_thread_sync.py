"""Background job for syncing Slack threads from JIRA tickets."""

import logging
import re
from datetime import datetime
from typing import Dict, List

from sqlalchemy import or_, select

from app.database import async_session
from app.models import JiraIssue
from app.models.slack_thread import SlackThread
from app.services.slack_thread_service import SlackThreadService
from app.services.agent_context_queue import AgentContextQueueService

logger = logging.getLogger(__name__)

# Keywords that indicate high-priority context
_HIGH_PRIORITY_KEYWORDS = re.compile(
    r"\b(?:sev|incident|@here|@channel|rollback|outage|critical|urgent|emergency|pagerduty)\b",
    re.IGNORECASE,
)


async def sync_slack_threads() -> Dict:
    """Scan recent JIRA issues for Slack URLs and sync threads.

    Scans:
    - 500 most recent JIRA issues
    - Extracts Slack thread URLs from descriptions
    - Fetches and caches threads from Slack API

    Returns:
        Dictionary with sync statistics:
        {
            "jira_scanned": int,
            "threads_found": int,
            "threads_synced": int,
            "threads_updated": int,
            "errors": [str]
        }
    """
    start_time = datetime.utcnow()
    logger.info("Starting Slack thread sync")

    try:
        async with async_session() as db:
            slack_service = SlackThreadService(db)

            stats = {
                "jira_scanned": 0,
                "threads_found": 0,
                "threads_synced": 0,
                "threads_updated": 0,
                "errors": []
            }

            # Fetch recent JIRA issues (500 most recent)
            result = await db.execute(
                select(JiraIssue)
                .order_by(JiraIssue.updated_at.desc())
                .limit(500)
            )
            jira_issues = result.scalars().all()

            logger.info(f"Scanning {len(jira_issues)} JIRA issues for Slack URLs")

            for issue in jira_issues:
                stats["jira_scanned"] += 1

                # Combine description and other text fields
                text = f"{issue.description or ''}"
                # TODO: In future, also scan JIRA comments if available

                # Extract Slack URLs
                slack_links = slack_service.extract_slack_links(text)

                if not slack_links:
                    continue

                stats["threads_found"] += len(slack_links)
                logger.debug(f"Found {len(slack_links)} Slack URLs in {issue.external_key}")

                # Sync each thread
                for link in slack_links:
                    try:
                        # Check if thread already cached
                        existing = await slack_service.get_thread_by_url(link["permalink"])

                        # Fetch thread from Slack API
                        thread_data = await slack_service.fetch_thread(
                            link["channel_id"],
                            link["thread_ts"],
                            include_surrounding=False  # Don't fetch context in background job
                        )

                        # Sync to database
                        thread = await slack_service.sync_thread(thread_data)

                        if existing:
                            stats["threads_updated"] += 1
                            logger.debug(f"Updated Slack thread {thread.id}")
                        else:
                            stats["threads_synced"] += 1
                            logger.debug(f"Synced new Slack thread {thread.id}")

                    except Exception as e:
                        error_msg = f"Failed to sync thread from {issue.external_key}: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        stats["errors"].append(error_msg)

            # Commit all changes
            await db.commit()

            # Enqueue context updates for active agents
            enqueued = await _enqueue_for_agents(db)
            stats["context_items_enqueued"] = enqueued

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Slack thread sync complete: {stats['jira_scanned']} JIRA scanned, "
                f"{stats['threads_found']} URLs found, "
                f"{stats['threads_synced']} new, {stats['threads_updated']} updated, "
                f"{enqueued} context items enqueued "
                f"in {duration:.1f}s"
            )

            return {
                "records_processed": stats["threads_synced"] + stats["threads_updated"],
                **stats
            }

    except Exception as e:
        logger.error(f"Slack thread sync failed: {e}", exc_info=True)
        raise


async def _enqueue_for_agents(db) -> int:
    """Enqueue context for active agents from recently-synced threads.

    Uses unified matching (JIRA + MR + branch) and thread-level enqueue
    (last 5 messages per matching thread, not just messages with the key).
    """
    queue_service = AgentContextQueueService(db)
    enqueued = 0

    # Fetch threads that have any cross-references
    result = await db.execute(
        select(SlackThread).where(
            or_(
                SlackThread.jira_keys.isnot(None),
                SlackThread.gitlab_mr_refs.isnot(None),
            )
        )
    )
    threads = result.scalars().all()

    for thread in threads:
        # Unified matching: JIRA + MR + branch
        agent_ids = await queue_service.find_agents_for_thread(thread)
        if not agent_ids:
            continue

        messages = thread.messages or []
        if not messages:
            continue

        # Thread-level: enqueue last 5 messages
        recent_messages = messages[-5:]

        for msg in recent_messages:
            msg_text = msg.get("text", "")
            if not msg_text:
                continue

            msg_ts = msg.get("ts", "")
            source_id = f"{thread.channel_id}:{msg_ts}"
            author = msg.get("user_name") or msg.get("user", "unknown")

            priority = "high" if _HIGH_PRIORITY_KEYWORDS.search(msg_text) else "normal"

            msg_ts_p = msg_ts.replace(".", "")
            permalink = (
                f"https://planet-labs.slack.com/archives/"
                f"{thread.channel_id}/p{msg_ts_p}"
                f"?thread_ts={thread.thread_ts}"
            )

            # Determine which JIRA key triggered the match (use first available)
            jira_key = (thread.jira_keys or [None])[0] if thread.jira_keys else None

            for agent_id in agent_ids:
                item = await queue_service.enqueue(
                    agent_id=agent_id,
                    content=msg_text[:500],
                    jira_key=jira_key,
                    source="slack",
                    source_id=source_id,
                    channel_name=thread.channel_name,
                    author=author,
                    permalink=permalink,
                    priority=priority,
                )
                if item is not None:
                    enqueued += 1
                    if priority == "high":
                        try:
                            delivered = await queue_service.escalate_if_possible(agent_id, item)
                            if delivered:
                                logger.info(f"Escalated urgent Slack message to agent {agent_id}")
                        except Exception as e:
                            logger.debug(f"Escalation attempt failed: {e}")

    if enqueued > 0:
        await db.commit()
        logger.info(f"Enqueued {enqueued} context items for active agents")

    return enqueued
