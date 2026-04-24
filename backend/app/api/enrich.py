"""Entity enrichment API endpoints.

Provides endpoints to trigger auto-context enrichment and check enrichment status.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.entity_enrichment import EntityEnrichmentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enrich", tags=["enrichment"])


# Response Models


class EnrichmentResult(BaseModel):
    """Result of enrichment operation."""

    status: str
    entity_type: str
    entity_id: str
    entity_key: str | None = None
    references_detected: int
    links_created: int
    detected_types: set[str] = Field(default_factory=set)
    links: list[dict] = Field(default_factory=list)
    enriched_at: str | None = None
    error: str | None = None


class EnrichmentStatusResponse(BaseModel):
    """Enrichment status for an entity."""

    entity_type: str
    entity_id: str
    total_links: int
    link_types: dict = Field(default_factory=dict)
    last_enriched_at: str | None = None


# API Endpoints


@router.post("/{entity_type}/{entity_id}", response_model=EnrichmentResult)
async def enrich_entity(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
) -> EnrichmentResult:
    """Trigger enrichment for an entity.

    Scans entity content for cross-references and creates entity links.

    Supported entity types:
    - jira_issue (entity_id = JIRA key like COMPUTE-1234)
    - agent (entity_id = chat UUID)
    - artifact (entity_id = artifact UUID) [future]
    - context (entity_id = context UUID) [future]

    Args:
        entity_type: Type of entity to enrich
        entity_id: Entity identifier (key or UUID)
        db: Database session

    Returns:
        Enrichment result with detected references and created links
    """
    service = EntityEnrichmentService(db)

    if entity_type == "jira_issue":
        # entity_id is JIRA key (e.g., COMPUTE-1234)
        result = await service.enrich_jira_issue(entity_id)
    elif entity_type == "agent" or entity_type == "chat":
        # entity_id is chat UUID
        try:
            chat_id = uuid.UUID(entity_id)
            result = await service.enrich_chat(chat_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid UUID for chat: {entity_id}",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported entity type: {entity_type}. "
            f"Supported types: jira_issue, agent/chat",
        )

    if result.get("status") == "failed":
        raise HTTPException(
            status_code=404,
            detail=result.get("error", "Enrichment failed"),
        )

    return EnrichmentResult(**result)


@router.get("/{entity_type}/{entity_id}/status", response_model=EnrichmentStatusResponse)
async def get_enrichment_status(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
) -> EnrichmentStatusResponse:
    """Get enrichment status for an entity.

    Returns information about detected references and created links.

    Args:
        entity_type: Type of entity
        entity_id: Entity identifier
        db: Database session

    Returns:
        Enrichment status with link counts and types
    """
    service = EntityEnrichmentService(db)
    status = await service.get_enrichment_status(entity_type, entity_id)

    return EnrichmentStatusResponse(**status)
