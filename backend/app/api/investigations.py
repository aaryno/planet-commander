"""Investigation API endpoints for agent-assisted finding resolution.

Provides endpoints for checking investigatability and triggering
investigations on audit findings using the investigation engine.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/investigations", tags=["investigations"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class InvestigationContext(BaseModel):
    """Context provided for an investigation."""

    jira_key: str = Field(..., description="JIRA issue key (e.g. COMPUTE-1234)")
    title: str = Field(default="", description="Issue title")
    description: str = Field(default="", description="Issue body text")
    repo_info: str = Field(default="", description="Optional repo structure / context")


class RunInvestigationRequest(BaseModel):
    """Request to run an investigation for a finding code."""

    finding_code: str = Field(..., description="The finding code to investigate")
    context: InvestigationContext


class InvestigationResultResponse(BaseModel):
    """Structured result from an investigation."""

    analysis: str
    draft: str
    metadata: dict = Field(default_factory=dict)
    cost_usd: float
    model: str = ""
    turns_used: int = 0


class InvestigatableCheckResponse(BaseModel):
    """Response for checking if a finding code is investigatable."""

    finding_code: str
    investigatable: bool
    spec: dict | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/check/{finding_code}",
    response_model=InvestigatableCheckResponse,
)
async def check_investigatable(finding_code: str):
    """Check whether a finding code can be investigated.

    Returns the investigation spec if the code is investigatable,
    or investigatable=false otherwise.
    """
    from app.services.investigation_engine import (
        get_investigation_spec,
        is_investigatable,
    )

    investigatable = is_investigatable(finding_code)
    spec = get_investigation_spec(finding_code) if investigatable else None

    return InvestigatableCheckResponse(
        finding_code=finding_code,
        investigatable=investigatable,
        spec=spec,
    )


@router.post("/run", response_model=InvestigationResultResponse)
async def run_investigation(request: RunInvestigationRequest):
    """Trigger an investigation for a finding code.

    Calls the investigation engine to analyze the finding in context
    and produce a structured result with JIRA-ready draft text.

    The investigation uses Claude Sonnet for deeper reasoning and
    is budget-capped at $0.50 per investigation.
    """
    from app.services.investigation_engine import (
        investigate_finding,
        is_investigatable,
    )

    # Validate finding code
    if not is_investigatable(request.finding_code):
        raise HTTPException(
            status_code=400,
            detail=f"Finding code '{request.finding_code}' is not investigatable. "
            f"Use GET /api/investigations/check/{{finding_code}} to verify.",
        )

    # Build context dict
    context = {
        "jira_key": request.context.jira_key,
        "title": request.context.title,
        "description": request.context.description,
        "repo_info": request.context.repo_info,
    }

    try:
        result = await investigate_finding(request.finding_code, context)
    except ValueError as e:
        # API key not available or invalid finding code
        raise HTTPException(status_code=503, detail=f"Investigation unavailable: {e}")
    except RuntimeError as e:
        # Budget exceeded
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        logger.error(
            "Investigation failed for %s: %s: %s",
            request.finding_code,
            type(e).__name__,
            e,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Investigation failed: {type(e).__name__}: {e}",
        )

    return InvestigationResultResponse(**result)
