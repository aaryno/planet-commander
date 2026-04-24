"""Audit system API schemas and routes.

Includes Pydantic response models for audit runs and findings,
and API endpoints for risk scoring and audit execution.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit_finding import AuditFinding
from app.models.audit_run import AuditRun
from app.models.gitlab_merge_request import GitLabMergeRequest
from app.services.audit_dispatcher import (
    assess_readiness,
    compute_merged_verdict,
    get_registered_audits,
    run_audit,
    select_persona_runners,
)
from app.services.change_risk_scorer import compute_change_risk
from app.services.cta_engine import CTAState, derive_cta_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audits", tags=["audits"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class FindingResponse(BaseModel):
    """Response model for an individual audit finding."""
    id: str
    code: str
    category: str
    severity: str
    confidence: str
    title: str
    description: str
    blocking: bool
    auto_fixable: bool
    actions: list[dict] | None
    status: str
    resolution: str | None
    source_file: str | None
    source_line: int | None
    related_entity_type: str | None
    related_entity_id: str | None


class AuditRunResponse(BaseModel):
    """Response model for an audit run with its findings."""
    id: str
    audit_family: str
    audit_tier: int
    source: str
    target_type: str
    target_id: str
    verdict: str
    confidence: float
    finding_count: int
    blocking_count: int
    auto_fixable_count: int
    dimension_scores: dict | None
    risk_score: float | None
    risk_level: str | None
    risk_factors: list[dict] | None
    duration_ms: int
    findings: list[FindingResponse] = Field(default_factory=list)
    created_at: str


class RunAuditRequest(BaseModel):
    """Request to run an audit against a target entity."""
    target_type: str  # "jira_issue" | "gitlab_merge_request"
    target_id: str    # JIRA key or MR UUID
    audit_families: list[str] | None = None  # None = run all applicable
    include_agent: bool = False  # Include LLM-based review persona audits


class RiskFactorResponse(BaseModel):
    """Single risk factor in a change risk assessment."""
    id: str
    score: float
    detail: str


class ChangeRiskResponse(BaseModel):
    """Response model for change risk scoring of a merge request."""
    mr_id: str
    repository: str
    title: str
    score: float
    level: str
    factors: list[RiskFactorResponse]
    additions: int
    deletions: int
    changed_file_count: int


class MergedVerdictResponse(BaseModel):
    """Response model for a merged verdict across multiple audit runs."""
    verdict: str
    finding_count: int
    blocking_count: int
    auto_fixable_count: int
    error_count: int
    warning_count: int
    dimension_scores: dict | None
    risk_score: float | None
    risk_level: str | None


class RunAuditResponse(BaseModel):
    """Response model for the POST /audits/run endpoint."""
    audit_runs: list[AuditRunResponse]
    merged_verdict: MergedVerdictResponse
    registered_families: list[str]


class CTAStateResponse(BaseModel):
    """Response model for derived CTA state.

    See AUDIT-SYSTEM-SPEC.md section 4 for color semantics.
    """
    label: str
    action: str
    subtext: str
    style: str
    secondary_actions: list[dict]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _cta_state_to_response(cta: CTAState) -> CTAStateResponse:
    """Convert a CTAState dataclass to a Pydantic response model."""
    return CTAStateResponse(
        label=cta.label,
        action=cta.action,
        subtext=cta.subtext,
        style=cta.style,
        secondary_actions=cta.secondary_actions,
    )


def _finding_to_dict(finding: AuditFinding) -> dict:
    """Convert an AuditFinding ORM model to a plain dict for CTA engine."""
    return {
        "code": finding.code,
        "auto_fixable": finding.auto_fixable,
        "blocking": finding.blocking,
        "severity": finding.severity,
        "category": finding.category,
        "status": finding.status,
    }


def _compute_readiness_from_run(run: AuditRun) -> str:
    """Derive a readiness string from an AuditRun's verdict.

    Maps AuditVerdict values to the readiness labels the CTA engine expects:
      - approved -> "ready"
      - changes_required -> "needs-work"
      - blocked -> "blocked"
      - unverified / unknown -> "exploratory-only"
    """
    verdict = run.verdict
    if verdict == "approved":
        return "ready"
    elif verdict == "changes_required":
        return "needs-work"
    elif verdict == "blocked":
        return "blocked"
    else:
        return "exploratory-only"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/run", response_model=RunAuditResponse)
async def run_audit_endpoint(
    body: RunAuditRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run audits against a target entity.

    Fetches the target (JIRA issue or GitLab MR) from the database,
    runs all applicable audit runners (or a filtered subset), persists
    the results, and returns the audit runs with a merged verdict.

    The ``audit_families`` field can filter which runners to invoke.
    If omitted, all registered runners whose context requirements are
    satisfied will be executed.

    When ``include_agent`` is False (default), persona runners (tier 3)
    are excluded. When True, persona runners are smart-selected based
    on the change risk factors detected in tier 2.
    """
    # Filter out persona runners unless include_agent is set
    PERSONA_FAMILIES = {"code-quality", "security", "architecture", "performance", "adversarial"}
    families = body.audit_families
    if not body.include_agent and families is None:
        # Run only deterministic runners
        families = [f for f in get_registered_audits() if f not in PERSONA_FAMILIES]

    audit_runs = await run_audit(
        db=db,
        target_type=body.target_type,
        target_id=body.target_id,
        families=families,
    )

    if not audit_runs:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No audit results for {body.target_type}:{body.target_id}. "
                f"Either the target was not found in the database or no "
                f"registered runners matched the context requirements. "
                f"Registered families: {get_registered_audits()}"
            ),
        )

    # Build merged verdict
    merged = compute_merged_verdict(audit_runs)

    # Fetch findings for each run
    run_responses: list[AuditRunResponse] = []
    for ar in audit_runs:
        findings_result = await db.execute(
            select(AuditFinding).where(AuditFinding.audit_run_id == ar.id)
        )
        findings = list(findings_result.scalars().all())

        run_responses.append(
            AuditRunResponse(
                id=str(ar.id),
                audit_family=ar.audit_family,
                audit_tier=ar.audit_tier,
                source=ar.source,
                target_type=ar.target_type,
                target_id=ar.target_id,
                verdict=ar.verdict,
                confidence=ar.confidence,
                finding_count=ar.finding_count,
                blocking_count=ar.blocking_count,
                auto_fixable_count=ar.auto_fixable_count,
                dimension_scores=ar.dimension_scores,
                risk_score=ar.risk_score,
                risk_level=ar.risk_level,
                risk_factors=ar.risk_factors,
                duration_ms=ar.duration_ms,
                findings=[
                    FindingResponse(
                        id=str(f.id),
                        code=f.code,
                        category=f.category,
                        severity=f.severity,
                        confidence=f.confidence,
                        title=f.title,
                        description=f.description,
                        blocking=f.blocking,
                        auto_fixable=f.auto_fixable,
                        actions=f.actions,
                        status=f.status,
                        resolution=f.resolution,
                        source_file=f.source_file,
                        source_line=f.source_line,
                        related_entity_type=f.related_entity_type,
                        related_entity_id=f.related_entity_id,
                    )
                    for f in findings
                ],
                created_at=ar.created_at.isoformat() if ar.created_at else "",
            )
        )

    return RunAuditResponse(
        audit_runs=run_responses,
        merged_verdict=MergedVerdictResponse(
            verdict=merged["verdict"],
            finding_count=merged["finding_count"],
            blocking_count=merged["blocking_count"],
            auto_fixable_count=merged["auto_fixable_count"],
            error_count=merged["error_count"],
            warning_count=merged["warning_count"],
            dimension_scores=merged["dimension_scores"],
            risk_score=merged["risk_score"],
            risk_level=merged["risk_level"],
        ),
        registered_families=get_registered_audits(),
    )


@router.get("/risk/{mr_id}", response_model=ChangeRiskResponse)
async def get_change_risk(
    mr_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Compute change risk score for a GitLab merge request.

    Looks up the MR by UUID in the database, then runs the deterministic
    change risk scorer against its changed_files, additions, and deletions.

    The mr_id parameter can be a UUID (internal ID) or an external MR ID
    (integer). UUID is tried first, then external_mr_id fallback.
    """
    mr: GitLabMergeRequest | None = None

    # Try UUID lookup first
    try:
        mr_uuid = uuid.UUID(mr_id)
        result = await db.execute(
            select(GitLabMergeRequest).where(GitLabMergeRequest.id == mr_uuid)
        )
        mr = result.scalar_one_or_none()
    except ValueError:
        pass

    # Fallback: try external_mr_id (integer)
    if mr is None:
        try:
            ext_id = int(mr_id)
            result = await db.execute(
                select(GitLabMergeRequest)
                .where(GitLabMergeRequest.external_mr_id == ext_id)
                .order_by(GitLabMergeRequest.updated_at.desc())
                .limit(1)
            )
            mr = result.scalar_one_or_none()
        except ValueError:
            pass

    if mr is None:
        raise HTTPException(
            status_code=404,
            detail=f"Merge request '{mr_id}' not found",
        )

    # Extract changed_files from JSONB (stored as list of strings)
    changed_files: list[str] = []
    if mr.changed_files:
        if isinstance(mr.changed_files, list):
            changed_files = mr.changed_files
        elif isinstance(mr.changed_files, dict):
            # Handle case where files are stored as dict with paths as keys
            changed_files = list(mr.changed_files.keys())

    risk = compute_change_risk(
        changed_files=changed_files,
        additions=mr.additions or 0,
        deletions=mr.deletions or 0,
    )

    return ChangeRiskResponse(
        mr_id=str(mr.id),
        repository=mr.repository,
        title=mr.title,
        score=risk["score"],
        level=risk["level"],
        factors=[
            RiskFactorResponse(
                id=f["id"],
                score=f["score"],
                detail=f["detail"],
            )
            for f in risk["factors"]
        ],
        additions=mr.additions or 0,
        deletions=mr.deletions or 0,
        changed_file_count=mr.changed_file_count or len(changed_files),
    )


@router.get("/cta/{target_type}/{target_id}", response_model=CTAStateResponse)
async def get_cta_state(
    target_type: str,
    target_id: str,
    db: AsyncSession = Depends(get_db),
) -> CTAStateResponse:
    """Get the current CTA state for a target entity.

    Queries the latest AuditRun for the given target and derives the
    appropriate call-to-action using the CTA state machine.

    If no audit runs exist for the target, returns the "Analyze Readiness"
    CTA (no-snapshot state).
    """
    # Find the latest AuditRun for this target
    result = await db.execute(
        select(AuditRun)
        .where(
            AuditRun.target_type == target_type,
            AuditRun.target_id == target_id,
        )
        .order_by(AuditRun.created_at.desc())
        .limit(1)
    )
    latest_run = result.scalars().first()

    if latest_run is None:
        # No snapshot -- derive CTA with no readiness
        cta = derive_cta_state(
            readiness=None,
            findings=[],
            auto_fixable_count=0,
            blocking_count=0,
        )
        return _cta_state_to_response(cta)

    # Fetch open findings for this run
    findings_result = await db.execute(
        select(AuditFinding)
        .where(AuditFinding.audit_run_id == latest_run.id)
        .where(AuditFinding.status == "open")
    )
    findings = list(findings_result.scalars().all())

    # Derive readiness from the run verdict
    readiness = _compute_readiness_from_run(latest_run)

    # Build finding dicts for the CTA engine
    finding_dicts = [_finding_to_dict(f) for f in findings]

    cta = derive_cta_state(
        readiness=readiness,
        findings=finding_dicts,
        auto_fixable_count=latest_run.auto_fixable_count,
        blocking_count=latest_run.blocking_count,
    )
    return _cta_state_to_response(cta)
