"""Grafana alert definition API endpoints."""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.grafana_alert_service import GrafanaAlertService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/grafana/alerts", tags=["grafana-alerts"])


# Pydantic response models
class AlertDefinitionResponse(BaseModel):
    """Response model for alert definition data."""

    id: str
    alert_name: str
    file_path: str
    team: Optional[str]
    project: Optional[str]
    alert_expr: str
    alert_for: Optional[str]
    labels: dict
    annotations: dict
    severity: Optional[str]
    runbook_url: Optional[str]
    summary: Optional[str]
    file_modified_at: Optional[datetime]
    last_synced_at: datetime
    is_active: bool
    is_critical: bool
    is_warning: bool
    has_runbook: bool

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, alert):
        """Create response from ORM model."""
        return cls(
            id=str(alert.id),
            alert_name=alert.alert_name,
            file_path=alert.file_path,
            team=alert.team,
            project=alert.project,
            alert_expr=alert.alert_expr,
            alert_for=alert.alert_for,
            labels=alert.labels or {},
            annotations=alert.annotations or {},
            severity=alert.severity,
            runbook_url=alert.runbook_url,
            summary=alert.summary,
            file_modified_at=alert.file_modified_at,
            last_synced_at=alert.last_synced_at,
            is_active=alert.is_active,
            is_critical=alert.is_critical,
            is_warning=alert.is_warning,
            has_runbook=alert.has_runbook,
        )


class AlertFiringResponse(BaseModel):
    """Response model for alert firing data."""

    id: str
    alert_definition_id: Optional[str]
    alert_name: str
    fired_at: datetime
    resolved_at: Optional[datetime]
    state: Optional[str]
    labels: dict
    annotations: dict
    fingerprint: Optional[str]
    value: Optional[float]
    external_alert_id: Optional[str]
    fetched_at: datetime
    duration_seconds: Optional[int]
    is_resolved: bool
    is_firing: bool

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, firing):
        """Create response from ORM model."""
        return cls(
            id=str(firing.id),
            alert_definition_id=str(firing.alert_definition_id) if firing.alert_definition_id else None,
            alert_name=firing.alert_name,
            fired_at=firing.fired_at,
            resolved_at=firing.resolved_at,
            state=firing.state,
            labels=firing.labels or {},
            annotations=firing.annotations or {},
            fingerprint=firing.fingerprint,
            value=firing.value,
            external_alert_id=firing.external_alert_id,
            fetched_at=firing.fetched_at,
            duration_seconds=firing.duration_seconds,
            is_resolved=firing.is_resolved,
            is_firing=firing.is_firing,
        )


class ScanResponse(BaseModel):
    """Response model for repo scan operation."""

    total_scanned: int
    new_alerts: int
    updated_alerts: int
    error_count: int
    note: Optional[str]


class CreateAlertRequest(BaseModel):
    """Request model for creating alert from name."""

    alert_name: str
    summary: Optional[str] = None
    severity: Optional[str] = None


@router.get("", response_model=List[AlertDefinitionResponse])
async def list_alerts(
    team: Optional[str] = Query(None, description="Filter by team (compute, datapipeline, etc.)"),
    project: Optional[str] = Query(None, description="Filter by project (jobs, wx, g4, etc.)"),
    severity: Optional[str] = Query(None, description="Filter by severity (critical, warning, info)"),
    limit: int = Query(100, le=500, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
) -> List[AlertDefinitionResponse]:
    """List alert definitions with optional filters.

    Args:
        team: Filter by team name
        project: Filter by project name
        severity: Filter by severity level
        limit: Maximum results (default 100, max 500)
        db: Database session

    Returns:
        List of alert definitions matching filters
    """
    service = GrafanaAlertService(db)

    results = await service.search_alerts(
        team=team,
        project=project,
        severity=severity,
        limit=limit,
    )

    return [AlertDefinitionResponse.from_orm(a) for a in results]


@router.get("/search", response_model=List[AlertDefinitionResponse])
async def search_alerts(
    query: str = Query(..., description="Search query (alert name)"),
    team: Optional[str] = Query(None, description="Filter by team"),
    project: Optional[str] = Query(None, description="Filter by project"),
    limit: int = Query(20, le=100, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
) -> List[AlertDefinitionResponse]:
    """Search alerts by name.

    Args:
        query: Search query string
        team: Filter by team
        project: Filter by project
        limit: Maximum results (default 20, max 100)
        db: Database session

    Returns:
        List of matching alert definitions
    """
    service = GrafanaAlertService(db)

    # Get all alerts matching team/project filters
    results = await service.search_alerts(
        team=team,
        project=project,
        limit=500,  # Get more for client-side filtering
    )

    # Filter by query (case-insensitive substring match)
    query_lower = query.lower()
    filtered = [a for a in results if query_lower in a.alert_name.lower()]

    # Apply limit
    filtered = filtered[:limit]

    return [AlertDefinitionResponse.from_orm(a) for a in filtered]


@router.get("/{alert_name}", response_model=AlertDefinitionResponse)
async def get_alert_definition(
    alert_name: str,
    db: AsyncSession = Depends(get_db),
) -> AlertDefinitionResponse:
    """Get single alert definition by name.

    Args:
        alert_name: Alert name (e.g., "jobs-scheduler-low-runs")
        db: Database session

    Returns:
        Alert definition details

    Raises:
        HTTPException: 404 if alert not found
    """
    service = GrafanaAlertService(db)

    alert = await service.get_alert_by_name(alert_name)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert not found: {alert_name}")

    return AlertDefinitionResponse.from_orm(alert)


@router.post("", response_model=AlertDefinitionResponse)
async def create_alert_from_name(
    request: CreateAlertRequest,
    db: AsyncSession = Depends(get_db),
) -> AlertDefinitionResponse:
    """Create alert definition from alert name.

    Useful for creating alerts discovered in Slack firing messages.
    Uses metadata inference to populate team/project/severity.

    Args:
        request: Alert creation request with name and optional metadata
        db: Database session

    Returns:
        Created alert definition
    """
    service = GrafanaAlertService(db)

    alert = await service.create_alert_from_name(
        alert_name=request.alert_name,
        summary=request.summary,
        severity=request.severity,
    )

    return AlertDefinitionResponse.from_orm(alert)


@router.post("/scan", response_model=ScanResponse)
async def scan_alert_repo(
    db: AsyncSession = Depends(get_db),
) -> ScanResponse:
    """Trigger alert repository scan.

    Scans ~/code/build-deploy/planet-grafana-cloud-users/modules/
    for alert directory structure.

    Note: Full Terraform parsing deferred to future phase.
    Phase 1 scans directory structure only.

    Args:
        db: Database session

    Returns:
        Scan statistics
    """
    service = GrafanaAlertService(db)

    logger.info("Manual alert repo scan triggered via API")
    stats = await service.scan_alert_repo()

    return ScanResponse(
        total_scanned=stats["total_scanned"],
        new_alerts=stats["new_alerts"],
        updated_alerts=stats["updated_alerts"],
        error_count=len(stats["errors"]),
        note=stats.get("note"),
    )


@router.get("/{alert_name}/firings", response_model=List[AlertFiringResponse])
async def get_alert_firings(
    alert_name: str,
    limit: int = Query(20, le=100, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
) -> List[AlertFiringResponse]:
    """Get recent firings for alert.

    Args:
        alert_name: Alert name
        limit: Maximum results (default 20, max 100)
        db: Database session

    Returns:
        List of recent alert firings

    Note: Firing history populated from Grafana API in future phase.
    For Phase 1, may be empty until Slack integration populates firings.
    """
    # TODO: Implement firing history query
    # For now, return empty list (firings populated in future phase)
    logger.info(f"Alert firing query for {alert_name} (not yet implemented)")
    return []
