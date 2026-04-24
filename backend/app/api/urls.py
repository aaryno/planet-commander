"""URL extraction and unknown URL management API endpoints."""
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import UnknownURL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/urls", tags=["urls"])


class UnknownURLResponse(BaseModel):
    """Unknown URL in response."""

    id: str
    url: str
    domain: str
    first_seen_in_chat_id: str | None
    occurrence_count: int
    first_seen_at: str
    last_seen_at: str
    reviewed: bool
    promoted_to_pattern: bool
    ignored: bool
    review_notes: str | None


class ReviewURLRequest(BaseModel):
    """Request to update review status."""

    reviewed: bool | None = None
    ignored: bool | None = None
    promoted_to_pattern: bool | None = None
    review_notes: str | None = None


@router.get("/unknown")
async def list_unknown_urls(
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    """List unknown URLs that need review.

    Args:
        limit: Maximum number of URLs to return (default: 50)

    Returns:
        List of unknown URLs with metadata
    """
    # Get total count
    total_result = await db.execute(select(func.count()).select_from(UnknownURL))
    total = total_result.scalar() or 0

    # Get unreviewed count
    unreviewed_result = await db.execute(
        select(func.count()).select_from(UnknownURL).where(UnknownURL.reviewed == False)
    )
    unreviewed_count = unreviewed_result.scalar() or 0

    # Get unknown URLs (unreviewed first, then by occurrence count)
    result = await db.execute(
        select(UnknownURL)
        .order_by(
            UnknownURL.reviewed.asc(),  # Unreviewed first
            UnknownURL.occurrence_count.desc(),  # Then by frequency
            UnknownURL.first_seen_at.desc()  # Then by recency
        )
        .limit(limit)
    )
    unknown_urls = result.scalars().all()

    return {
        "unknown_urls": [
            UnknownURLResponse(
                id=str(url.id),
                url=url.url,
                domain=url.domain,
                first_seen_in_chat_id=str(url.first_seen_in_chat_id) if url.first_seen_in_chat_id else None,
                occurrence_count=url.occurrence_count,
                first_seen_at=url.first_seen_at.isoformat() if url.first_seen_at else "",
                last_seen_at=url.last_seen_at.isoformat() if url.last_seen_at else "",
                reviewed=url.reviewed,
                promoted_to_pattern=url.promoted_to_pattern,
                ignored=url.ignored,
                review_notes=url.review_notes,
            )
            for url in unknown_urls
        ],
        "total": total,
        "unreviewed_count": unreviewed_count,
    }


@router.patch("/unknown/{url_id}")
async def update_unknown_url(
    url_id: str,
    updates: ReviewURLRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update review status of an unknown URL.

    Args:
        url_id: UUID of unknown URL
        updates: Review status updates

    Returns:
        Updated unknown URL
    """
    try:
        url_uuid = uuid.UUID(url_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid URL ID format")

    # Find URL
    result = await db.execute(
        select(UnknownURL).where(UnknownURL.id == url_uuid)
    )
    unknown_url = result.scalar_one_or_none()

    if not unknown_url:
        raise HTTPException(status_code=404, detail="Unknown URL not found")

    # Update fields
    if updates.reviewed is not None:
        unknown_url.reviewed = updates.reviewed
    if updates.ignored is not None:
        unknown_url.ignored = updates.ignored
    if updates.promoted_to_pattern is not None:
        unknown_url.promoted_to_pattern = updates.promoted_to_pattern
    if updates.review_notes is not None:
        unknown_url.review_notes = updates.review_notes

    await db.commit()
    await db.refresh(unknown_url)

    return UnknownURLResponse(
        id=str(unknown_url.id),
        url=unknown_url.url,
        domain=unknown_url.domain,
        first_seen_in_chat_id=str(unknown_url.first_seen_in_chat_id) if unknown_url.first_seen_in_chat_id else None,
        occurrence_count=unknown_url.occurrence_count,
        first_seen_at=unknown_url.first_seen_at.isoformat() if unknown_url.first_seen_at else "",
        last_seen_at=unknown_url.last_seen_at.isoformat() if unknown_url.last_seen_at else "",
        reviewed=unknown_url.reviewed,
        promoted_to_pattern=unknown_url.promoted_to_pattern,
        ignored=unknown_url.ignored,
        review_notes=unknown_url.review_notes,
    )


@router.post("/unknown/{url_id}/generate-pattern")
async def generate_url_pattern(
    url_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Generate a URL pattern template for an unknown URL.

    Args:
        url_id: UUID of unknown URL

    Returns:
        Pattern template with regex and handler suggestion
    """
    try:
        url_uuid = uuid.UUID(url_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid URL ID format")

    # Find URL
    result = await db.execute(
        select(UnknownURL).where(UnknownURL.id == url_uuid)
    )
    unknown_url = result.scalar_one_or_none()

    if not unknown_url:
        raise HTTPException(status_code=404, detail="Unknown URL not found")

    # Generate pattern suggestions
    from urllib.parse import urlparse
    parsed = urlparse(unknown_url.url)
    path = parsed.path

    # Simple pattern generation: replace digits with capture groups
    import re
    pattern_suggestion = re.sub(r'\d+', r'(\\d+)', path)
    pattern_suggestion = re.escape(parsed.netloc) + pattern_suggestion

    # Detect likely entity type based on URL structure
    entity_type_guess = "unknown"
    if "/issues/" in path or "/browse/" in path:
        entity_type_guess = "issue"
    elif "/pull/" in path or "/merge_requests/" in path:
        entity_type_guess = "pull_request"
    elif "/wiki/" in path:
        entity_type_guess = "wiki_page"
    elif "/documents/" in path or "/docs/" in path:
        entity_type_guess = "document"

    return {
        "url": unknown_url.url,
        "domain": unknown_url.domain,
        "pattern_suggestion": pattern_suggestion,
        "entity_type_guess": entity_type_guess,
        "code_template": f"""
# Add to URLClassifier.PATTERNS in url_classifier.py

URLType.{unknown_url.domain.upper().replace('.', '_').replace('-', '_')} = "{unknown_url.domain.replace('.', '_')}"

PATTERNS[URLType.{unknown_url.domain.upper().replace('.', '_').replace('-', '_')}] = (
    re.compile(r'{pattern_suggestion}'),
    lambda m: {{"id": m.group(1)}}  # Adjust groups as needed
)
""".strip(),
    }
