"""Entity link management API endpoints for Planet Commander Phase 1.

Provides endpoints for creating and managing relationships between entities.
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import LinkType, LinkSourceType, LinkStatus
from app.services.entity_link import EntityLinkService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/links", tags=["links"])


# Request/Response Models


class CreateLinkRequest(BaseModel):
    """Request to create a new entity link."""

    from_type: str = Field(
        ..., description="Source entity type (context, jira_issue, chat, branch, worktree, etc.)"
    )
    from_id: str = Field(..., description="Source entity ID")
    to_type: str = Field(
        ..., description="Target entity type (context, jira_issue, chat, branch, worktree, etc.)"
    )
    to_id: str = Field(..., description="Target entity ID")
    link_type: str = Field(..., description="Type of relationship (implements, discussed_in, etc.)")
    source_type: str = Field(
        default="manual", description="How the link was created (manual, inferred, imported, agent)"
    )
    confidence_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Confidence score for inferred links (0.0-1.0)"
    )


class LinkResponse(BaseModel):
    """Entity link response."""

    id: str
    from_type: str
    from_id: str
    to_type: str
    to_id: str
    link_type: str
    source_type: str
    status: str
    confidence_score: float | None
    created_at: str
    updated_at: str


class BatchConfirmRequest(BaseModel):
    """Request to confirm multiple links."""

    link_ids: list[str] = Field(..., description="List of link IDs to confirm")


# Endpoints


@router.post("", response_model=LinkResponse)
async def create_link(request: CreateLinkRequest, db: AsyncSession = Depends(get_db)):
    """Create a new entity link.

    Creates a relationship between two entities. If the link already exists,
    returns the existing link.

    Args:
        request: Link creation request

    Returns:
        Created or existing link
    """
    # Validate link_type
    try:
        link_type = LinkType(request.link_type)
    except ValueError:
        valid_types = [t.value for t in LinkType]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid link_type. Must be one of: {', '.join(valid_types)}",
        )

    # Validate source_type
    try:
        source_type = LinkSourceType(request.source_type)
    except ValueError:
        valid_types = [t.value for t in LinkSourceType]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source_type. Must be one of: {', '.join(valid_types)}",
        )

    service = EntityLinkService(db)

    try:
        link = await service.create_link(
            from_type=request.from_type,
            from_id=request.from_id,
            to_type=request.to_type,
            to_id=request.to_id,
            link_type=link_type,
            source_type=source_type,
            confidence_score=request.confidence_score,
        )

        # Commit the new link
        await db.commit()

        return _build_link_response(link)

    except Exception as e:
        logger.error(f"Failed to create link: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{link_id}/confirm", response_model=LinkResponse)
async def confirm_link(link_id: str, db: AsyncSession = Depends(get_db)):
    """Confirm a suggested link.

    Changes link status from 'suggested' to 'confirmed'.

    Args:
        link_id: Link UUID

    Returns:
        Updated link
    """
    try:
        link_uuid = uuid.UUID(link_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid link ID format")

    service = EntityLinkService(db)

    try:
        link = await service.confirm_link(link_uuid)

        # Commit the status change
        await db.commit()

        return _build_link_response(link)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to confirm link {link_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{link_id}/reject", response_model=LinkResponse)
async def reject_link(link_id: str, db: AsyncSession = Depends(get_db)):
    """Reject a suggested link.

    Changes link status from 'suggested' to 'rejected'.

    Args:
        link_id: Link UUID

    Returns:
        Updated link
    """
    try:
        link_uuid = uuid.UUID(link_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid link ID format")

    service = EntityLinkService(db)

    try:
        link = await service.reject_link(link_uuid)

        # Commit the status change
        await db.commit()

        return _build_link_response(link)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to reject link {link_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{link_id}")
async def delete_link(link_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a link.

    Permanently removes the link from the database.

    Args:
        link_id: Link UUID

    Returns:
        Success message
    """
    try:
        link_uuid = uuid.UUID(link_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid link ID format")

    service = EntityLinkService(db)

    try:
        await service.delete_link(link_uuid)

        # Commit the deletion
        await db.commit()

        return {"status": "deleted", "link_id": link_id}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete link {link_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/context/{context_id}", response_model=list[LinkResponse])
async def get_context_links(context_id: str, db: AsyncSession = Depends(get_db)):
    """Get all links for a context.

    Returns all entity links where the context is source or target.

    Args:
        context_id: WorkContext UUID

    Returns:
        List of links
    """
    try:
        context_uuid = uuid.UUID(context_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid context ID format")

    service = EntityLinkService(db)

    try:
        links = await service.get_links_for_context(context_uuid)

        return [_build_link_response(link) for link in links]

    except Exception as e:
        logger.error(f"Failed to get links for context {context_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/suggested", response_model=list[LinkResponse])
async def get_suggested_links(db: AsyncSession = Depends(get_db)):
    """Get all suggested (unconfirmed) links.

    Returns all links with status='suggested' that need user review.

    Returns:
        List of suggested links
    """
    service = EntityLinkService(db)

    try:
        links = await service.get_suggested_links()

        return [_build_link_response(link) for link in links]

    except Exception as e:
        logger.error(f"Failed to get suggested links: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/batch-confirm", response_model=dict)
async def batch_confirm_links(request: BatchConfirmRequest, db: AsyncSession = Depends(get_db)):
    """Confirm multiple suggested links at once.

    Args:
        request: Batch confirm request with link IDs

    Returns:
        Number of links confirmed
    """
    # Validate all link IDs
    try:
        link_uuids = [uuid.UUID(link_id) for link_id in request.link_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="One or more invalid link ID formats")

    service = EntityLinkService(db)

    try:
        confirmed_count = await service.batch_confirm_links(link_uuids)

        # Commit all status changes
        await db.commit()

        return {
            "status": "success",
            "confirmed_count": confirmed_count,
            "total_requested": len(request.link_ids),
        }

    except Exception as e:
        logger.error(f"Failed to batch confirm links: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Helper Functions


def _build_link_response(link: Any) -> LinkResponse:
    """Build LinkResponse from EntityLink model.

    Args:
        link: EntityLink instance

    Returns:
        LinkResponse for API
    """
    return LinkResponse(
        id=str(link.id),
        from_type=link.from_type,
        from_id=link.from_id,
        to_type=link.to_type,
        to_id=link.to_id,
        link_type=link.link_type.value,
        source_type=link.source_type.value,
        status=link.status.value,
        confidence_score=link.confidence_score,
        created_at=link.created_at.isoformat(),
        updated_at=link.updated_at.isoformat(),
    )
