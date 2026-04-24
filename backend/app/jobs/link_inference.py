"""Entity link inference background job"""
import logging
from datetime import datetime

from app.database import async_session
from app.services.link_inference import LinkInferenceService

logger = logging.getLogger(__name__)


async def infer_entity_links():
    """Run link inference across all entity types

    Infers relationships between entities based on:
    - Branch names containing JIRA keys
    - Chat jira_key fields
    - (Future) Commit messages, PR descriptions, etc.

    Returns:
        dict: Results with records_processed count
    """
    start_time = datetime.utcnow()
    logger.info("Starting link inference")

    async with async_session() as db:
        try:
            inference = LinkInferenceService(db)

            # Run all inference heuristics
            results = await inference.infer_all_links()

            # Commit all suggested links
            await db.commit()

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Link inference complete: {results['total']} suggested links created "
                f"(branch→JIRA: {results['branch_jira']}, chat→JIRA: {results['chat_jira']}) "
                f"in {duration:.1f}s"
            )

            return {
                "records_processed": results['total'],
                "branch_jira_links": results['branch_jira'],
                "chat_jira_links": results['chat_jira']
            }

        except Exception as e:
            logger.error(f"Link inference failed: {e}", exc_info=True)
            await db.rollback()
            raise
