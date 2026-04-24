"""PagerDuty API endpoints."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.pagerduty_incident import PagerDutyIncident
from app.services.pagerduty_service import PagerDutyService

logger = logging.getLogger(__name__)

router = APIRouter()


# Response Models

class PagerDutyIncidentResponse(BaseModel):
    """PagerDuty incident response model."""
    id: str
    external_incident_id: str
    incident_number: Optional[int]
    title: str
    status: str
    urgency: Optional[str]
    service_name: Optional[str]
    escalation_policy_name: Optional[str]
    assigned_to: Optional[List[Dict]]
    teams: Optional[List[Dict]]
    triggered_at: datetime
    acknowledged_at: Optional[datetime]
    resolved_at: Optional[datetime]
    incident_url: Optional[str]
    html_url: Optional[str]

    # Computed properties
    is_active: bool
    is_resolved: bool
    is_high_urgency: bool
    duration_minutes: Optional[int]
    time_to_ack_minutes: Optional[int]
    team_names: List[str]
    assigned_user_names: List[str]
    is_compute_team: bool
    age_minutes: int

    @classmethod
    def from_model(cls, incident: PagerDutyIncident):
        """Convert PagerDutyIncident model to response."""
        return cls(
            id=str(incident.id),
            external_incident_id=incident.external_incident_id,
            incident_number=incident.incident_number,
            title=incident.title,
            status=incident.status,
            urgency=incident.urgency,
            service_name=incident.service_name,
            escalation_policy_name=incident.escalation_policy_name,
            assigned_to=incident.assigned_to,
            teams=incident.teams,
            triggered_at=incident.triggered_at,
            acknowledged_at=incident.acknowledged_at,
            resolved_at=incident.resolved_at,
            incident_url=incident.incident_url,
            html_url=incident.html_url,
            is_active=incident.is_active,
            is_resolved=incident.is_resolved,
            is_high_urgency=incident.is_high_urgency,
            duration_minutes=incident.duration_minutes,
            time_to_ack_minutes=incident.time_to_ack_minutes,
            team_names=incident.team_names,
            assigned_user_names=incident.assigned_user_names,
            is_compute_team=incident.is_compute_team,
            age_minutes=incident.age_minutes,
        )

    class Config:
        from_attributes = True


class PagerDutyIncidentListResponse(BaseModel):
    """List of PagerDuty incidents."""
    incidents: List[PagerDutyIncidentResponse]
    total: int


class PagerDutyIncidentDetailResponse(PagerDutyIncidentResponse):
    """Detailed PagerDuty incident with full metadata."""
    description: Optional[str]
    priority: Optional[Dict]
    acknowledgements: Optional[List[Dict]]
    assignments: Optional[List[Dict]]
    log_entries: Optional[List[Dict]]
    alerts: Optional[List[Dict]]
    incident_key: Optional[str]
    last_status_change_at: Optional[datetime]

    @classmethod
    def from_model(cls, incident: PagerDutyIncident):
        """Convert PagerDutyIncident model to detailed response."""
        base = PagerDutyIncidentResponse.from_model(incident)
        return cls(
            **base.model_dump(),
            description=incident.description,
            priority=incident.priority,
            acknowledgements=incident.acknowledgements,
            assignments=incident.assignments,
            log_entries=incident.log_entries,
            alerts=incident.alerts,
            incident_key=incident.incident_key,
            last_status_change_at=incident.last_status_change_at,
        )


class PagerDutySyncResponse(BaseModel):
    """Response for sync operations."""
    status: str
    message: str
    incident_id: Optional[str] = None
    incidents_synced: Optional[int] = None


class PagerDutyEnrichmentResponse(BaseModel):
    """Response for enrichment operations."""
    incident_ids: List[str]
    incidents_fetched: int
    incidents_cached: int
    errors: List[str]


# API Endpoints

@router.get("", response_model=PagerDutyIncidentListResponse)
async def list_incidents(
    status: Optional[str] = Query(None, description="Filter by status: triggered, acknowledged, resolved"),
    urgency: Optional[str] = Query(None, description="Filter by urgency: high, low"),
    team: Optional[str] = Query(None, description="Filter by team name (partial match)"),
    service: Optional[str] = Query(None, description="Filter by service name (partial match)"),
    days: int = Query(7, ge=1, le=90, description="Days back to search"),
    limit: int = Query(50, ge=1, le=200, description="Max incidents to return"),
    db: AsyncSession = Depends(get_db),
):
    """List PagerDuty incidents with filters.

    Returns incidents from the last N days matching the specified filters.
    Results are ordered by triggered_at descending (most recent first).
    """
    service_obj = PagerDutyService(db)
    since = datetime.utcnow() - timedelta(days=days)

    incidents = await service_obj.search_incidents(
        status=status,
        urgency=urgency,
        service_name=service,
        team_name=team,
        since=since,
        limit=limit,
    )

    return PagerDutyIncidentListResponse(
        incidents=[PagerDutyIncidentResponse.from_model(i) for i in incidents],
        total=len(incidents),
    )


@router.get("/compute-team", response_model=PagerDutyIncidentListResponse)
async def list_compute_team_incidents(
    status: Optional[str] = Query(None, description="Filter by status: triggered, acknowledged, resolved"),
    days: int = Query(7, ge=1, le=90, description="Days back to search"),
    limit: int = Query(50, ge=1, le=200, description="Max incidents to return"),
    db: AsyncSession = Depends(get_db),
):
    """List Compute team PagerDuty incidents.

    Convenience endpoint that filters to incidents belonging to the Compute team
    escalation policy.
    """
    service_obj = PagerDutyService(db)

    incidents = await service_obj.get_compute_team_incidents(
        status=status,
        days=days,
        limit=limit,
    )

    return PagerDutyIncidentListResponse(
        incidents=[PagerDutyIncidentResponse.from_model(i) for i in incidents],
        total=len(incidents),
    )


@router.get("/{incident_id}", response_model=PagerDutyIncidentDetailResponse)
async def get_incident(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed information about a specific incident.

    Args:
        incident_id: PagerDuty incident ID (e.g., "Q123ABC456")

    Returns:
        Detailed incident information including timeline, alerts, and logs.

    Raises:
        404: Incident not found in cache
    """
    service_obj = PagerDutyService(db)
    incident = await service_obj.get_incident_by_id(incident_id)

    if not incident:
        raise HTTPException(
            status_code=404,
            detail=f"Incident {incident_id} not found in cache. Use /sync/{incident_id} to fetch from PagerDuty."
        )

    return PagerDutyIncidentDetailResponse.from_model(incident)


@router.post("/sync/{incident_id}", response_model=PagerDutySyncResponse)
async def sync_incident(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch and sync a specific incident from PagerDuty.

    Fetches the incident from PagerDuty API via MCP and stores/updates it in the cache.

    Args:
        incident_id: PagerDuty incident ID (e.g., "Q123ABC456")

    Returns:
        Sync status and incident ID

    Raises:
        404: Incident not found in PagerDuty
        500: Error syncing incident
    """
    service_obj = PagerDutyService(db)

    try:
        # Fetch from MCP
        incident_data = await service_obj.fetch_incident_from_mcp(incident_id)
        
        if not incident_data:
            raise HTTPException(
                status_code=404,
                detail=f"Incident {incident_id} not found in PagerDuty"
            )

        # Sync to DB
        incident = await service_obj.sync_incident(incident_data)
        await db.commit()

        return PagerDutySyncResponse(
            status="success",
            message=f"Incident {incident_id} synced successfully",
            incident_id=incident_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing incident {incident_id}: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error syncing incident: {str(e)}"
        )


@router.post("/scan-recent", response_model=PagerDutySyncResponse)
async def scan_recent_incidents(
    days: int = Query(1, ge=1, le=30, description="Days back to scan"),
    statuses: Optional[List[str]] = Query(
        ["triggered", "acknowledged", "resolved"],
        description="Statuses to include"
    ),
    compute_team_only: bool = Query(True, description="Only scan Compute team incidents"),
    db: AsyncSession = Depends(get_db),
):
    """Scan and sync recent incidents from PagerDuty.

    Fetches recent incidents from PagerDuty API and syncs them to the cache.
    Useful for bulk updates or initial sync.

    Args:
        days: Number of days back to scan (1-30)
        statuses: List of incident statuses to include
        compute_team_only: If True, only fetch Compute team incidents

    Returns:
        Number of incidents synced
    """
    service_obj = PagerDutyService(db)

    try:
        since = datetime.utcnow() - timedelta(days=days)
        team_ids = [PagerDutyService.COMPUTE_TEAM_ESCALATION_POLICY_ID] if compute_team_only else None

        # Fetch from MCP
        incidents_data = await service_obj.fetch_recent_incidents(
            statuses=statuses,
            team_ids=team_ids,
            since=since,
            limit=100,
        )

        # Sync all
        synced = 0
        errors = []
        for incident_data in incidents_data:
            try:
                await service_obj.sync_incident(incident_data)
                synced += 1
            except Exception as e:
                logger.error(f"Error syncing incident {incident_data.get('id')}: {e}")
                errors.append(str(e))

        await db.commit()

        message = f"Synced {synced}/{len(incidents_data)} incidents from last {days} day(s)"
        if errors:
            message += f" ({len(errors)} errors)"

        return PagerDutySyncResponse(
            status="success" if synced > 0 else "partial",
            message=message,
            incidents_synced=synced,
        )

    except Exception as e:
        logger.error(f"Error scanning recent incidents: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error scanning incidents: {str(e)}"
        )


@router.post("/enrich-text", response_model=PagerDutyEnrichmentResponse)
async def enrich_text(
    text: str = Query(..., description="Text to scan for PagerDuty incident references"),
    db: AsyncSession = Depends(get_db),
):
    """Extract PagerDuty incident references from text and enrich.

    Scans the provided text for PagerDuty incident IDs (URLs, PD- prefix, etc.),
    fetches any incidents not in cache, and returns enrichment statistics.

    Useful for auto-enriching JIRA descriptions, Slack messages, etc.

    Args:
        text: Text containing potential incident references

    Returns:
        Enrichment statistics (IDs found, fetched, cached, errors)
    """
    service_obj = PagerDutyService(db)

    try:
        stats = await service_obj.enrich_from_references(text)
        await db.commit()

        return PagerDutyEnrichmentResponse(**stats)

    except Exception as e:
        logger.error(f"Error enriching text: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error enriching text: {str(e)}"
        )
