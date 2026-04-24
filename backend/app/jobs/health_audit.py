"""Health audit background job"""
import logging
from datetime import datetime

from app.database import async_session
from app.services.health_audit import HealthAuditService

logger = logging.getLogger(__name__)


async def run_health_audit():
    """
    Run health audit across all work contexts.

    Returns:
        dict: Results with records_processed count
    """
    start_time = datetime.utcnow()
    logger.info("Starting health audit")

    async with async_session() as db:
        try:
            health_service = HealthAuditService(db)

            # Audit all contexts
            results = await health_service.audit_all_contexts()

            # Mark very stale contexts as orphaned (60+ days)
            orphaned_count = await health_service.mark_stale_as_orphaned(days_threshold=60)

            await db.commit()

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Health audit complete: {results['audited']} contexts audited, "
                f"{orphaned_count} marked as orphaned in {duration:.1f}s"
            )

            return {
                "records_processed": results['audited'],
                "green": results['health_distribution']['green'],
                "yellow": results['health_distribution']['yellow'],
                "red": results['health_distribution']['red'],
                "orphaned": orphaned_count
            }

        except Exception as e:
            logger.error(f"Health audit failed: {e}", exc_info=True)
            await db.rollback()
            raise
