"""Background job status and management API"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel

from app.database import get_db
from app.models import JobRun
from app.services.background_jobs import job_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobRunResponse(BaseModel):
    """Job run response model"""
    id: int
    job_name: str
    started_at: str
    completed_at: str | None
    status: str
    records_processed: int
    error_message: str | None
    duration_seconds: float | None


class JobStatusResponse(BaseModel):
    """Current job status response"""
    job_id: str
    next_run_time: str | None


@router.get("/runs")
async def get_job_runs(
    limit: int = 20,
    job_name: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """Get recent background job runs

    Args:
        limit: Maximum number of runs to return (default: 20)
        job_name: Filter by specific job name (optional)
        db: Database session

    Returns:
        List of recent job runs
    """
    query = select(JobRun).order_by(desc(JobRun.started_at)).limit(limit)

    if job_name:
        query = query.where(JobRun.job_name == job_name)

    result = await db.execute(query)
    runs = result.scalars().all()

    return {
        "runs": [
            JobRunResponse(
                id=run.id,
                job_name=run.job_name,
                started_at=run.started_at.isoformat(),
                completed_at=run.completed_at.isoformat() if run.completed_at else None,
                status=run.status,
                records_processed=run.records_processed,
                error_message=run.error_message,
                duration_seconds=run.duration_seconds,
            )
            for run in runs
        ],
        "total": len(runs)
    }


@router.get("/status")
async def get_job_status():
    """Get status of all scheduled jobs

    Returns:
        List of scheduled jobs with next run times
    """
    jobs = job_service.get_jobs()

    return {
        "jobs": [
            JobStatusResponse(
                job_id=job.id,
                next_run_time=job.next_run_time.isoformat() if job.next_run_time else None
            )
            for job in jobs
        ],
        "total": len(jobs),
        "scheduler_running": job_service._running
    }


@router.post("/trigger/{job_name}")
async def trigger_job(job_name: str):
    """Manually trigger a background job

    Args:
        job_name: Name of the job to trigger

    Returns:
        Success message
    """
    jobs = job_service.get_jobs()
    job_ids = [job.id for job in jobs]

    if job_name not in job_ids:
        return {
            "success": False,
            "error": f"Job not found: {job_name}",
            "available_jobs": job_ids
        }

    try:
        # Trigger job to run immediately
        job_service.scheduler.get_job(job_name).modify(next_run_time=None)
        logger.info(f"Manually triggered job: {job_name}")

        return {
            "success": True,
            "message": f"Job triggered: {job_name}"
        }
    except Exception as e:
        logger.error(f"Failed to trigger job {job_name}: {e}")
        return {
            "success": False,
            "error": str(e)
        }
