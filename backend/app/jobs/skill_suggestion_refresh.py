"""Background job to refresh skill suggestions for active work contexts."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy import select

from app.database import async_session
from app.models import WorkContext
from app.services.skill_suggestion import SkillSuggestionService

logger = logging.getLogger(__name__)


async def refresh_skill_suggestions() -> Dict:
    """Refresh skill suggestions for active work contexts.

    Scans recent/active work contexts and regenerates skill suggestions.

    Returns:
        Dictionary with refresh statistics:
        {
            "records_processed": int,  # For job tracking
            "contexts_processed": int,
            "suggestions_created": int,
            "errors": [str]
        }
    """
    start_time = datetime.utcnow()
    logger.info("Starting skill suggestion refresh")

    try:
        async with async_session() as db:
            suggestion_service = SkillSuggestionService(db)

            stats = {
                "contexts_processed": 0,
                "suggestions_created": 0,
                "errors": []
            }

            # Fetch active contexts (last 7 days)
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            result = await db.execute(
                select(WorkContext)
                .where(WorkContext.created_at >= cutoff)
                .where(WorkContext.status.in_(["active", "blocked", "stalled"]))
                .order_by(WorkContext.created_at.desc())
                .limit(500)  # Process up to 500 contexts
            )
            contexts = result.scalars().all()

            logger.info(f"Processing {len(contexts)} active work contexts")

            for context in contexts:
                stats["contexts_processed"] += 1

                try:
                    # Generate suggestions
                    suggestions = await suggestion_service.suggest_skills_for_context(
                        context.id,
                        min_confidence=0.3
                    )

                    stats["suggestions_created"] += len(suggestions)

                    logger.debug(
                        f"Generated {len(suggestions)} suggestions for context {context.id}"
                    )

                except Exception as e:
                    error_msg = f"Failed to generate suggestions for context {context.id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    stats["errors"].append(error_msg)

            # Commit happens automatically via store_suggestions in suggest_skills_for_context

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Skill suggestion refresh complete: {stats['contexts_processed']} contexts, "
                f"{stats['suggestions_created']} suggestions created in {duration:.1f}s"
            )

            return {
                "records_processed": stats["contexts_processed"],
                **stats
            }

    except Exception as e:
        logger.error(f"Skill suggestion refresh failed: {e}", exc_info=True)
        raise
