"""JIRA cache synchronization background job"""
import logging
from datetime import datetime

from app.database import async_session
from app.services.jira_cache import JiraCacheService
from app.services.jira_service import search_tickets
from app.services.config_service import config

logger = logging.getLogger(__name__)


async def sync_jira_cache():
    """Sync JIRA cache with recent issues from configured queries

    Returns:
        dict: Results with records_processed count
    """
    start_time = datetime.utcnow()
    logger.info("Starting JIRA cache sync")

    total_issues = 0
    queries_processed = 0
    queries = config.get_jira_queries()

    async with async_session() as db:
        try:
            jira_cache = JiraCacheService(db)

            for query_config in queries:
                query_name = query_config["name"]
                jql = query_config["jql"]
                max_results = query_config.get("max_results", 100)

                logger.info(f"Running JIRA query: {query_name}")

                try:
                    # Fetch from JIRA API
                    tickets = search_tickets(jql, max_results=max_results)

                    if not tickets:
                        logger.debug(f"  No tickets found for {query_name}")
                        continue

                    # Extract JIRA keys
                    jira_keys = [t['key'] for t in tickets]

                    # Batch sync to cache
                    synced = await jira_cache.batch_sync_issues(jira_keys)
                    total_issues += len(synced)
                    queries_processed += 1

                    logger.debug(f"  Synced {len(synced)} issues from {query_name}")

                except Exception as e:
                    logger.error(f"Failed to sync query {query_name}: {e}", exc_info=True)
                    continue

            # Commit all changes
            await db.commit()

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"JIRA sync complete: {queries_processed} queries, {total_issues} issues "
                f"in {duration:.1f}s"
            )

            return {
                "records_processed": total_issues,
                "queries_processed": queries_processed
            }

        except Exception as e:
            logger.error(f"JIRA sync failed: {e}", exc_info=True)
            await db.rollback()
            raise
