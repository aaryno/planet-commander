"""Layout API endpoints - save/load grid layout configurations."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.page_layout import PageLayout

router = APIRouter()


class LayoutRequest(BaseModel):
    """Request body for saving layout."""
    page: str
    layout: list[dict]  # Grid layout items


class LayoutResponse(BaseModel):
    """Response with layout configuration."""
    page: str
    layout: list[dict]
    updated_at: str | None = None


# Default layout for dashboard
DEFAULT_DASHBOARD_LAYOUT = [
    {"i": "slack", "x": 0, "y": 0, "w": 6, "h": 4},
    {"i": "mrs", "x": 6, "y": 0, "w": 6, "h": 4},
    {"i": "jira", "x": 0, "y": 4, "w": 4, "h": 4},
    {"i": "oncall", "x": 4, "y": 4, "w": 4, "h": 3},
    {"i": "traffic", "x": 8, "y": 4, "w": 4, "h": 4},
    {"i": "workload", "x": 0, "y": 8, "w": 6, "h": 4},
    {"i": "docs", "x": 6, "y": 8, "w": 6, "h": 4},
]


@router.get("")
async def get_layout(page: str = "dashboard", db: AsyncSession = Depends(get_db)) -> LayoutResponse:
    """Get layout configuration for a page."""
    result = await db.execute(
        select(PageLayout).where(PageLayout.page == page)
    )
    page_layout = result.scalar_one_or_none()

    if not page_layout:
        # Return default layout
        default = DEFAULT_DASHBOARD_LAYOUT if page == "dashboard" else []
        return LayoutResponse(page=page, layout=default)

    return LayoutResponse(
        page=page_layout.page,
        layout=page_layout.layout.get("items", []),
        updated_at=page_layout.updated_at.isoformat()
    )


@router.put("")
async def save_layout(req: LayoutRequest, db: AsyncSession = Depends(get_db)) -> LayoutResponse:
    """Save or update layout configuration for a page."""
    # Use INSERT ... ON CONFLICT DO UPDATE
    stmt = insert(PageLayout).values(
        page=req.page,
        layout={"items": req.layout}
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=['page'],
        set_={'layout': {"items": req.layout}}
    )

    await db.execute(stmt)
    await db.commit()

    # Fetch the updated record
    result = await db.execute(
        select(PageLayout).where(PageLayout.page == req.page)
    )
    page_layout = result.scalar_one()

    return LayoutResponse(
        page=page_layout.page,
        layout=page_layout.layout.get("items", []),
        updated_at=page_layout.updated_at.isoformat()
    )
