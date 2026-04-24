"""Coach session API endpoints for guided human audit walkthrough.

Provides endpoints for creating, managing, and transitioning
coach sessions that guide humans through audit findings.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.coach_session import CoachItemStatus, CoachSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coach", tags=["coach"])


# ---------------------------------------------------------------------------
# Valid state transitions for coach items
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[str, set[str]] = {
    CoachItemStatus.OPEN: {
        CoachItemStatus.IN_PROGRESS,
        CoachItemStatus.DEFERRED,
        CoachItemStatus.BLOCKED,
    },
    CoachItemStatus.IN_PROGRESS: {
        CoachItemStatus.ANSWERED,
        CoachItemStatus.RESOLVED,
        CoachItemStatus.DEFERRED,
        CoachItemStatus.BLOCKED,
    },
    CoachItemStatus.ANSWERED: {
        CoachItemStatus.RESOLVED,
        CoachItemStatus.IN_PROGRESS,
        CoachItemStatus.DEFERRED,
    },
    CoachItemStatus.RESOLVED: set(),  # terminal
    CoachItemStatus.DEFERRED: {
        CoachItemStatus.OPEN,
        CoachItemStatus.IN_PROGRESS,
    },
    CoachItemStatus.BLOCKED: {
        CoachItemStatus.OPEN,
        CoachItemStatus.IN_PROGRESS,
    },
}

# Statuses that count toward completion
COMPLETED_STATUSES = {CoachItemStatus.RESOLVED, CoachItemStatus.DEFERRED}


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------


class CoachItemResponse(BaseModel):
    """Single item within a coach session."""

    id: str
    code: str | None = None
    category: str | None = None
    severity: str | None = None
    title: str | None = None
    description: str | None = None
    blocking: bool = False
    status: str
    resolution: str | None = None
    notes: str | None = None


class CoachSessionResponse(BaseModel):
    """Full coach session state."""

    id: str
    target_type: str
    target_id: str
    readiness: str
    active_item_id: str | None
    completed_count: int
    total_count: int
    items: list[CoachItemResponse]
    audit_run_id: str | None
    created_at: str
    updated_at: str


class CreateCoachSessionRequest(BaseModel):
    """Request to create or retrieve a coach session."""

    target_type: str = Field(..., description="Entity type, e.g. 'jira_issue'")
    target_id: str = Field(..., description="Entity identifier, e.g. JIRA key")
    audit_run_id: str | None = Field(
        default=None, description="Optional audit run to seed items from"
    )


class TransitionItemRequest(BaseModel):
    """Request to transition a coach item to a new status."""

    status: str = Field(..., description="Target status for the item")
    resolution: str | None = Field(
        default=None, description="Resolution text (for resolved items)"
    )
    notes: str | None = Field(
        default=None, description="Optional notes about the transition"
    )


class TransitionItemResponse(BaseModel):
    """Response after transitioning a coach item."""

    item: CoachItemResponse
    next_item: CoachItemResponse | None = None
    all_done: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_item(item: dict) -> CoachItemResponse:
    """Convert a raw JSONB item dict into a response model."""
    return CoachItemResponse(
        id=item.get("id", ""),
        code=item.get("code"),
        category=item.get("category"),
        severity=item.get("severity"),
        title=item.get("title"),
        description=item.get("description"),
        blocking=item.get("blocking", False),
        status=item.get("status", CoachItemStatus.OPEN),
        resolution=item.get("resolution"),
        notes=item.get("notes"),
    )


def _serialize_session(session: CoachSession) -> CoachSessionResponse:
    """Convert a CoachSession ORM object into a response model."""
    return CoachSessionResponse(
        id=str(session.id),
        target_type=session.target_type,
        target_id=session.target_id,
        readiness=session.readiness,
        active_item_id=session.active_item_id,
        completed_count=session.completed_count,
        total_count=session.total_count,
        items=[_serialize_item(item) for item in (session.items or [])],
        audit_run_id=str(session.audit_run_id) if session.audit_run_id else None,
        created_at=session.created_at.isoformat() if session.created_at else "",
        updated_at=session.updated_at.isoformat() if session.updated_at else "",
    )


def _find_next_open_item(items: list[dict], exclude_id: str | None = None) -> dict | None:
    """Find the next item that is open or in_progress (blocking items first)."""
    # First pass: blocking items
    for item in items:
        if item.get("id") == exclude_id:
            continue
        if item.get("status") in (CoachItemStatus.OPEN, CoachItemStatus.IN_PROGRESS):
            if item.get("blocking", False):
                return item
    # Second pass: non-blocking items
    for item in items:
        if item.get("id") == exclude_id:
            continue
        if item.get("status") in (CoachItemStatus.OPEN, CoachItemStatus.IN_PROGRESS):
            return item
    return None


def _recalculate_completed(items: list[dict]) -> int:
    """Count items in completed statuses."""
    return sum(1 for item in items if item.get("status") in COMPLETED_STATUSES)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/sessions", response_model=CoachSessionResponse)
async def create_or_get_session(
    request: CreateCoachSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new coach session or return an existing one for the target.

    If a session already exists for the (target_type, target_id) pair,
    the existing session is returned. Otherwise a new empty session is created.
    """
    # Check for existing session
    result = await db.execute(
        select(CoachSession).where(
            CoachSession.target_type == request.target_type,
            CoachSession.target_id == request.target_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return _serialize_session(existing)

    # Build initial items list (empty by default; callers can populate later)
    items: list[dict] = []
    audit_run_id = None
    if request.audit_run_id:
        try:
            audit_run_id = uuid.UUID(request.audit_run_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid audit_run_id format")

    session = CoachSession(
        target_type=request.target_type,
        target_id=request.target_id,
        readiness="pending",
        active_item_id=None,
        completed_count=0,
        total_count=len(items),
        items=items,
        audit_run_id=audit_run_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _serialize_session(session)


@router.get("/sessions/{session_id}", response_model=CoachSessionResponse)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the current state of a coach session including all items."""
    result = await db.execute(
        select(CoachSession).where(CoachSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Coach session not found")
    return _serialize_session(session)


@router.post(
    "/sessions/{session_id}/items/{item_id}/transition",
    response_model=TransitionItemResponse,
)
async def transition_item(
    session_id: uuid.UUID,
    item_id: str,
    request: TransitionItemRequest,
    db: AsyncSession = Depends(get_db),
):
    """Transition a coach item to a new status.

    Validates the transition is allowed, updates the item, recalculates
    completed_count, and returns the updated item plus the next open item.
    """
    # Validate target status
    try:
        target_status = CoachItemStatus(request.status)
    except ValueError:
        valid = [s.value for s in CoachItemStatus]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{request.status}'. Must be one of: {valid}",
        )

    # Fetch session
    result = await db.execute(
        select(CoachSession).where(CoachSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Coach session not found")

    # Find item in JSONB array
    items = list(session.items)  # copy to allow mutation
    target_item: dict | None = None
    target_idx: int | None = None
    for idx, item in enumerate(items):
        if item.get("id") == item_id:
            target_item = item
            target_idx = idx
            break

    if target_item is None or target_idx is None:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found in session")

    # Validate transition
    current_status = target_item.get("status", CoachItemStatus.OPEN)
    allowed = VALID_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{current_status}' to '{target_status}'. "
            f"Allowed transitions: {sorted(s.value for s in allowed) if allowed else 'none (terminal state)'}",
        )

    # Apply transition
    target_item["status"] = target_status.value
    if request.resolution is not None:
        target_item["resolution"] = request.resolution
    if request.notes is not None:
        target_item["notes"] = request.notes

    items[target_idx] = target_item

    # Recalculate counts
    completed_count = _recalculate_completed(items)
    all_done = completed_count >= len(items) and len(items) > 0

    # Find next open item
    next_item = _find_next_open_item(items, exclude_id=item_id if target_status in COMPLETED_STATUSES else None)

    # Update active_item_id
    if all_done:
        active_item_id = None
    elif next_item:
        active_item_id = next_item.get("id")
    else:
        active_item_id = session.active_item_id

    # Persist changes — assign new list to trigger JSONB change detection
    session.items = items
    session.completed_count = completed_count
    session.active_item_id = active_item_id
    await db.commit()
    await db.refresh(session)

    return TransitionItemResponse(
        item=_serialize_item(target_item),
        next_item=_serialize_item(next_item) if next_item else None,
        all_done=all_done,
    )


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a coach session."""
    result = await db.execute(
        select(CoachSession).where(CoachSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Coach session not found")

    await db.delete(session)
    await db.commit()


# ---------------------------------------------------------------------------
# Claude API endpoints (explain + respond)
# ---------------------------------------------------------------------------


class ExplainItemResponse(BaseModel):
    """Response from explaining a coach item via Claude API."""

    explanation: str
    recommended_approach: str
    exact_edit: str | None = None
    question: str
    usage: dict = Field(default_factory=dict)


class RespondToItemRequest(BaseModel):
    """Request body for submitting a user response to a coach item."""

    response: str = Field(..., description="User's text response to the coaching question")


class RespondToItemResponse(BaseModel):
    """Response from evaluating a user's answer via Claude API."""

    complete: bool
    follow_up: str | None = None
    summary: str
    suggested_resolution: str
    usage: dict = Field(default_factory=dict)


@router.post(
    "/sessions/{session_id}/items/{item_id}/explain",
    response_model=ExplainItemResponse,
)
async def explain_item(
    session_id: uuid.UUID,
    item_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Explain a coach item using Claude API.

    When a user opens a coach item, this endpoint calls Claude to provide
    a structured explanation of what needs attention, a recommended approach,
    and optionally an exact edit to apply.
    """
    from app.services.coach_prompts import explain_item as _explain_item

    # Fetch session
    result = await db.execute(
        select(CoachSession).where(CoachSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Coach session not found")

    # Find item in JSONB array
    target_item: dict | None = None
    for item in (session.items or []):
        if item.get("id") == item_id:
            target_item = item
            break

    if target_item is None:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found in session")

    # Build issue context from session metadata
    issue_context = {
        "jira_key": session.target_id,
        "title": session.target_id,  # Best available; enriched context can be added later
        "description": "",
    }

    try:
        result = await _explain_item(target_item, issue_context)
    except ValueError as e:
        # API key not available
        raise HTTPException(
            status_code=503,
            detail=f"Claude API unavailable: {e}",
        )
    except Exception as e:
        logger.error("explain_item failed for session=%s item=%s: %s", session_id, item_id, e)
        raise HTTPException(
            status_code=502,
            detail=f"Claude API call failed: {type(e).__name__}: {e}",
        )

    return ExplainItemResponse(**result)


@router.post(
    "/sessions/{session_id}/items/{item_id}/respond",
    response_model=RespondToItemResponse,
)
async def respond_to_item(
    session_id: uuid.UUID,
    item_id: str,
    request: RespondToItemRequest,
    db: AsyncSession = Depends(get_db),
):
    """Evaluate a user's response to a coach item using Claude API.

    When a user submits a response to a coaching question, this endpoint
    calls Claude to evaluate whether the response adequately addresses
    the audit item.
    """
    from app.services.coach_prompts import evaluate_response

    # Fetch session
    result = await db.execute(
        select(CoachSession).where(CoachSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Coach session not found")

    # Find item in JSONB array
    target_item: dict | None = None
    for item in (session.items or []):
        if item.get("id") == item_id:
            target_item = item
            break

    if target_item is None:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found in session")

    # Build issue context from session metadata
    issue_context = {
        "jira_key": session.target_id,
        "title": session.target_id,
        "description": "",
    }

    try:
        result = await evaluate_response(target_item, request.response, issue_context)
    except ValueError as e:
        # API key not available
        raise HTTPException(
            status_code=503,
            detail=f"Claude API unavailable: {e}",
        )
    except Exception as e:
        logger.error("respond_to_item failed for session=%s item=%s: %s", session_id, item_id, e)
        raise HTTPException(
            status_code=502,
            detail=f"Claude API call failed: {type(e).__name__}: {e}",
        )

    return RespondToItemResponse(**result)
