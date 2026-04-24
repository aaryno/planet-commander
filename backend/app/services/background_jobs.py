"""Background job service with APScheduler integration"""
from datetime import datetime
from typing import Callable, Any
import logging
from functools import wraps

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import JobRun

logger = logging.getLogger(__name__)


class BackgroundJobService:
    """Service for managing background jobs with APScheduler"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._running = False

    def start(self):
        """Start the background job scheduler"""
        if not self._running:
            self.scheduler.start()
            self._running = True
            logger.info("Background job scheduler started")

    def stop(self):
        """Stop the background job scheduler"""
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Background job scheduler stopped")

    def add_interval_job(
        self,
        func: Callable,
        job_id: str,
        minutes: int = None,
        hours: int = None,
        seconds: int = None,
        **kwargs
    ):
        """Add a job that runs at regular intervals

        Args:
            func: Async function to execute
            job_id: Unique identifier for the job
            minutes: Run every N minutes
            hours: Run every N hours
            seconds: Run every N seconds
            **kwargs: Additional APScheduler job arguments
        """
        # Build trigger kwargs only with non-None values
        trigger_kwargs = {}
        if minutes is not None:
            trigger_kwargs['minutes'] = minutes
        if hours is not None:
            trigger_kwargs['hours'] = hours
        if seconds is not None:
            trigger_kwargs['seconds'] = seconds

        trigger = IntervalTrigger(**trigger_kwargs)

        # Wrap function to track execution
        tracked_func = self._track_execution(func, job_id)

        self.scheduler.add_job(
            tracked_func,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            **kwargs
        )
        logger.info(f"Added interval job: {job_id} (interval: {minutes}m {hours}h {seconds}s)")

    def add_cron_job(
        self,
        func: Callable,
        job_id: str,
        hour: str = None,
        minute: str = None,
        day: str = None,
        **kwargs
    ):
        """Add a job that runs on a cron schedule

        Args:
            func: Async function to execute
            job_id: Unique identifier for the job
            hour: Cron hour expression
            minute: Cron minute expression
            day: Cron day expression
            **kwargs: Additional APScheduler job arguments
        """
        trigger = CronTrigger(hour=hour, minute=minute, day=day)

        # Wrap function to track execution
        tracked_func = self._track_execution(func, job_id)

        self.scheduler.add_job(
            tracked_func,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            **kwargs
        )
        logger.info(f"Added cron job: {job_id} (schedule: {hour}:{minute})")

    def remove_job(self, job_id: str):
        """Remove a scheduled job

        Args:
            job_id: Job identifier to remove
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job: {job_id}")
        except Exception as e:
            logger.warning(f"Failed to remove job {job_id}: {e}")

    def get_jobs(self):
        """Get list of all scheduled jobs"""
        return self.scheduler.get_jobs()

    def _track_execution(self, func: Callable, job_name: str) -> Callable:
        """Wrap a job function to track execution in database

        Args:
            func: Async function to wrap
            job_name: Name of the job for tracking

        Returns:
            Wrapped function that records execution
        """
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            records_processed = 0
            error_message = None
            status = "running"

            # Create job run record
            async with async_session() as db:
                try:
                    job_run = JobRun(
                        job_name=job_name,
                        started_at=start_time,
                        status="running",
                        records_processed=0
                    )
                    db.add(job_run)
                    await db.commit()
                    job_run_id = job_run.id
                except Exception as e:
                    logger.error(f"Failed to create job run record: {e}")
                    job_run_id = None

            # Execute the job
            try:
                logger.info(f"Starting job: {job_name}")
                result = await func(*args, **kwargs)

                # Extract records_processed if function returns it
                if isinstance(result, dict) and "records_processed" in result:
                    records_processed = result["records_processed"]
                elif isinstance(result, int):
                    records_processed = result

                status = "success"
                logger.info(f"Job completed: {job_name} ({records_processed} records)")

            except Exception as e:
                status = "failed"
                error_message = str(e)
                logger.error(f"Job failed: {job_name}: {e}", exc_info=True)

            # Update job run record
            if job_run_id:
                async with async_session() as db:
                    try:
                        result = await db.get(JobRun, job_run_id)
                        if result:
                            result.completed_at = datetime.utcnow()
                            result.status = status
                            result.records_processed = records_processed
                            result.error_message = error_message
                            result.duration_seconds = (
                                datetime.utcnow() - start_time
                            ).total_seconds()
                            await db.commit()
                    except Exception as e:
                        logger.error(f"Failed to update job run record: {e}")

        return wrapper


# Singleton instance
job_service = BackgroundJobService()
