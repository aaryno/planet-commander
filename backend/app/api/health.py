"""Health audit API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict, List

from app.database import get_db
from app.services.health_audit import HealthAuditService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/audit/{context_id}")
async def audit_context(
    context_id: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Audit health of a specific work context."""
    health_service = HealthAuditService(db)

    try:
        result = await health_service.audit_context_health(context_id)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit")
async def audit_all_contexts(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Audit health of all active work contexts."""
    health_service = HealthAuditService(db)

    try:
        result = await health_service.audit_all_contexts()
        await db.commit()
        return result
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stale")
async def get_stale_contexts(
    days: int = 30,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, List[Dict[str, Any]]]:
    """Get stale contexts (no updates in N days)."""
    health_service = HealthAuditService(db)

    try:
        stale = await health_service.detect_stale_contexts(days_threshold=days)
        return {"stale_contexts": stale, "days_threshold": days}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orphaned")
async def get_orphaned_entities(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, List[Dict[str, Any]]]:
    """Get orphaned entities (not linked to any context)."""
    health_service = HealthAuditService(db)

    try:
        orphaned = await health_service.detect_orphaned_entities()
        return orphaned
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mark-orphaned")
async def mark_stale_orphaned(
    days: int = 60,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Mark stale contexts as orphaned."""
    health_service = HealthAuditService(db)

    try:
        count = await health_service.mark_stale_as_orphaned(days_threshold=days)
        await db.commit()
        return {"marked_orphaned": count, "days_threshold": days}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
