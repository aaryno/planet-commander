"""Audit dispatcher with registry pattern.

Central orchestrator that registers audit runners, validates context
availability, runs audits against targets, persists results, and
produces merged verdicts.

Spec reference: dashboard/AUDIT-SYSTEM-SPEC.md section 6.
Issue: aaryn/claude#10
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_finding import AuditFinding
from app.models.audit_run import AuditRun
from app.models.entity_link import EntityLink, LinkSourceType, LinkStatus, LinkType
from app.models.gitlab_merge_request import GitLabMergeRequest
from app.models.jira_issue import JiraIssue

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class AuditRequest:
    """Input to an audit runner.

    Carries the target identity plus any pre-fetched context data that
    the runner may need (JIRA issue fields, MR metadata, changed files).
    """

    target_type: str  # "jira_issue" | "gitlab_merge_request"
    target_id: str  # JIRA key or MR UUID
    jira_issue: dict | None = None  # Serialised JiraIssue data
    merge_request: dict | None = None  # Serialised GitLabMergeRequest data
    changed_files: list[str] | None = None


@dataclass
class AuditRunResult:
    """Output from an audit runner.

    Contains the verdict, findings, and optional dimension/risk scores.
    The dispatcher persists these into ``AuditRun`` + ``AuditFinding`` rows.
    """

    verdict: str  # AuditVerdict value
    confidence: float
    findings: list[dict[str, Any]]  # Finding dicts ready for AuditFinding creation
    dimension_scores: dict | None = None
    risk_score: float | None = None
    risk_level: str | None = None
    risk_factors: list[dict] | None = None
    duration_ms: int = 0
    model_used: str | None = None
    cost_usd: float = 0.0
    raw_output: str | None = None


# ---------------------------------------------------------------------------
# AuditRunner protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class AuditRunner(Protocol):
    """Protocol for audit runners.

    Any object implementing this protocol can be registered with the
    dispatcher and run against audit targets.
    """

    audit_family: str
    required_context: list[str]  # e.g. ["jira_issue"], ["gitlab_merge_request"]

    async def run(self, request: AuditRequest) -> AuditRunResult: ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_registry: dict[str, AuditRunner] = {}


def register_audit(runner: AuditRunner) -> None:
    """Register an audit runner in the global registry.

    Args:
        runner: An object satisfying the AuditRunner protocol.
            Must have ``audit_family`` and ``required_context`` attributes.

    Raises:
        ValueError: If the runner's audit_family is already registered.
    """
    family = runner.audit_family
    if family in _registry:
        logger.warning(
            "Overwriting existing audit runner for family %r", family
        )
    _registry[family] = runner
    logger.info("Registered audit runner: %s", family)


def get_registered_audits() -> list[str]:
    """Return the list of registered audit family names."""
    return list(_registry.keys())


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def _has_required_context(
    runner: AuditRunner,
    request: AuditRequest,
) -> bool:
    """Check whether the request has the data required by the runner."""
    for ctx in runner.required_context:
        if ctx == "jira_issue" and request.jira_issue is None:
            return False
        if ctx == "gitlab_merge_request" and request.merge_request is None:
            return False
    return True


async def _fetch_target_data(
    db: AsyncSession,
    target_type: str,
    target_id: str,
) -> AuditRequest:
    """Build an AuditRequest by fetching target data from the database.

    Looks up the target entity and populates the context fields that
    downstream runners need.
    """
    request = AuditRequest(target_type=target_type, target_id=target_id)

    if target_type == "jira_issue":
        result = await db.execute(
            select(JiraIssue).where(JiraIssue.external_key == target_id)
        )
        issue = result.scalar_one_or_none()
        if issue is not None:
            request.jira_issue = {
                "external_key": issue.external_key,
                "title": issue.title,
                "description": issue.description or "",
                "acceptance_criteria": issue.acceptance_criteria,
                "labels": issue.labels,
                "status": issue.status,
                "priority": issue.priority,
                "assignee": issue.assignee,
            }

    elif target_type == "gitlab_merge_request":
        mr: GitLabMergeRequest | None = None
        # Try UUID lookup
        try:
            mr_uuid = uuid.UUID(target_id)
            result = await db.execute(
                select(GitLabMergeRequest).where(
                    GitLabMergeRequest.id == mr_uuid
                )
            )
            mr = result.scalar_one_or_none()
        except ValueError:
            pass

        # Fallback: try external_mr_id (integer)
        if mr is None:
            try:
                ext_id = int(target_id)
                result = await db.execute(
                    select(GitLabMergeRequest)
                    .where(GitLabMergeRequest.external_mr_id == ext_id)
                    .order_by(GitLabMergeRequest.updated_at.desc())
                    .limit(1)
                )
                mr = result.scalar_one_or_none()
            except ValueError:
                pass

        if mr is not None:
            # Extract changed_files from JSONB
            changed_files: list[str] = []
            if mr.changed_files:
                if isinstance(mr.changed_files, list):
                    changed_files = mr.changed_files
                elif isinstance(mr.changed_files, dict):
                    changed_files = list(mr.changed_files.keys())

            request.merge_request = {
                "id": str(mr.id),
                "external_mr_id": mr.external_mr_id,
                "repository": mr.repository,
                "title": mr.title,
                "description": mr.description,
                "source_branch": mr.source_branch,
                "target_branch": mr.target_branch,
                "author": mr.author,
                "state": mr.state,
                "additions": mr.additions or 0,
                "deletions": mr.deletions or 0,
                "changed_file_count": mr.changed_file_count or len(changed_files),
                "changed_files": changed_files,
            }
            request.changed_files = changed_files

    return request


# ---------------------------------------------------------------------------
# Core dispatch
# ---------------------------------------------------------------------------


async def run_audit(
    db: AsyncSession,
    target_type: str,
    target_id: str,
    families: list[str] | None = None,
) -> list[AuditRun]:
    """Run selected audits against a target. Returns persisted AuditRun objects.

    Workflow:
      1. Fetch target data from DB.
      2. Determine which runners to invoke (all registered, or filtered by families).
      3. Validate context availability for each runner.
      4. Run each runner, collect results.
      5. Persist AuditRun + AuditFinding rows.
      6. Create EntityLinks (audited_by, has_finding, finding_for).
      7. Return the persisted AuditRun list.

    Args:
        db: Async SQLAlchemy session.
        target_type: Entity type string ("jira_issue" or "gitlab_merge_request").
        target_id: Entity identifier (JIRA key or MR UUID/external ID).
        families: Optional list of audit family names to run. If None, runs
            all registered runners whose context requirements are met.

    Returns:
        List of persisted AuditRun ORM objects.
    """
    # 1. Fetch target data
    request = await _fetch_target_data(db, target_type, target_id)

    # 2. Determine runners to execute
    if families:
        runners = [
            (name, runner)
            for name, runner in _registry.items()
            if name in families
        ]
        # Warn about unknown families
        known = set(_registry.keys())
        for f in families:
            if f not in known:
                logger.warning("Requested audit family %r is not registered", f)
    else:
        runners = list(_registry.items())

    # Sort by tier: deterministic (tier 1-2) first, agent_review (tier 3) last
    PERSONA_FAMILIES = {"code-quality", "security", "architecture", "performance", "adversarial"}
    deterministic = [(n, r) for n, r in runners if n not in PERSONA_FAMILIES]
    persona = [(n, r) for n, r in runners if n in PERSONA_FAMILIES]
    runners = deterministic + persona

    if not runners:
        logger.info("No audit runners to execute for target %s:%s", target_type, target_id)
        return []

    # 3 + 4. Run each runner with context validation
    audit_runs: list[AuditRun] = []

    for family_name, runner in runners:
        if not _has_required_context(runner, request):
            logger.info(
                "Skipping %s: missing required context %s",
                family_name,
                runner.required_context,
            )
            continue

        t0 = time.monotonic()
        try:
            result = await runner.run(request)
        except Exception:
            logger.exception("Audit runner %s failed", family_name)
            continue
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        # Override duration_ms with actual measured time if runner reported 0
        if result.duration_ms == 0:
            result.duration_ms = elapsed_ms

        # 5. Persist AuditRun
        audit_run = AuditRun(
            audit_family=family_name,
            audit_tier=1,  # deterministic tier; runners can override via result
            source="deterministic",
            target_type=target_type,
            target_id=target_id,
            verdict=result.verdict,
            confidence=result.confidence,
            finding_count=len(result.findings),
            blocking_count=sum(1 for f in result.findings if f.get("blocking")),
            auto_fixable_count=sum(
                1 for f in result.findings if f.get("auto_fixable")
            ),
            error_count=sum(
                1 for f in result.findings if f.get("severity") == "error"
            ),
            warning_count=sum(
                1 for f in result.findings if f.get("severity") == "warning"
            ),
            dimension_scores=result.dimension_scores,
            risk_score=result.risk_score,
            risk_level=result.risk_level,
            risk_factors=result.risk_factors,
            duration_ms=result.duration_ms,
            model_used=result.model_used,
            cost_usd=result.cost_usd,
            raw_output=result.raw_output,
        )
        db.add(audit_run)
        await db.flush()  # Get the generated ID

        # 5b. Persist AuditFindings
        for finding_dict in result.findings:
            finding = AuditFinding(
                audit_run_id=audit_run.id,
                code=finding_dict.get("code", "UNKNOWN"),
                category=finding_dict.get("category", "system"),
                severity=finding_dict.get("severity", "info"),
                confidence=finding_dict.get("confidence", "high"),
                title=finding_dict.get("title", "Untitled finding"),
                description=finding_dict.get("description", ""),
                blocking=finding_dict.get("blocking", False),
                auto_fixable=finding_dict.get("auto_fixable", False),
                actions=finding_dict.get("actions"),
                status=finding_dict.get("status", "open"),
                related_entity_type=finding_dict.get("related_entity_type"),
                related_entity_id=finding_dict.get("related_entity_id"),
                source_file=finding_dict.get("source_file"),
                source_line=finding_dict.get("source_line"),
            )
            db.add(finding)

        await db.flush()

        # 6. Create EntityLinks
        # audited_by: target entity -> AuditRun
        db.add(EntityLink(
            from_type=target_type,
            from_id=target_id,
            to_type="audit_run",
            to_id=str(audit_run.id),
            link_type=LinkType.AUDITED_BY,
            source_type=LinkSourceType.AGENT,
            confidence_score=1.0,
            status=LinkStatus.CONFIRMED,
            link_metadata={"audit_family": family_name},
        ))

        # has_finding + finding_for: for each finding
        # (We need to flush and query back to get finding IDs)
        findings_result = await db.execute(
            select(AuditFinding).where(
                AuditFinding.audit_run_id == audit_run.id
            )
        )
        persisted_findings = list(findings_result.scalars().all())

        for pf in persisted_findings:
            # has_finding: AuditRun -> AuditFinding
            db.add(EntityLink(
                from_type="audit_run",
                from_id=str(audit_run.id),
                to_type="audit_finding",
                to_id=str(pf.id),
                link_type=LinkType.HAS_FINDING,
                source_type=LinkSourceType.AGENT,
                confidence_score=1.0,
                status=LinkStatus.CONFIRMED,
            ))

            # finding_for: AuditFinding -> target entity
            db.add(EntityLink(
                from_type="audit_finding",
                from_id=str(pf.id),
                to_type=target_type,
                to_id=target_id,
                link_type=LinkType.FINDING_FOR,
                source_type=LinkSourceType.AGENT,
                confidence_score=1.0,
                status=LinkStatus.CONFIRMED,
            ))

        # Update JiraIssue audit reference if applicable
        if target_type == "jira_issue" and family_name == "readiness-dimensions":
            issue_result = await db.execute(
                select(JiraIssue).where(JiraIssue.external_key == target_id)
            )
            jira_issue = issue_result.scalar_one_or_none()
            if jira_issue is not None:
                jira_issue.last_context_audit_id = audit_run.id

        audit_runs.append(audit_run)

    await db.commit()
    return audit_runs


# ---------------------------------------------------------------------------
# Merged verdict
# ---------------------------------------------------------------------------


def compute_merged_verdict(audit_runs: list[AuditRun]) -> dict[str, Any]:
    """Merge verdicts from multiple audit runs into a single assessment.

    Priority logic:
      - Any blocking findings -> "blocked"
      - All verdicts are "approved" -> "approved"
      - Any verdict is "changes_required" -> "changes_required"
      - Otherwise -> "unverified"

    Also aggregates dimension scores, finding counts, and risk data.

    Args:
        audit_runs: List of AuditRun objects (with populated fields).

    Returns:
        Dict with merged verdict information.
    """
    if not audit_runs:
        return {
            "verdict": "unverified",
            "finding_count": 0,
            "blocking_count": 0,
            "auto_fixable_count": 0,
            "error_count": 0,
            "warning_count": 0,
            "dimension_scores": None,
            "risk_score": None,
            "risk_level": None,
        }

    total_findings = sum(r.finding_count for r in audit_runs)
    total_blocking = sum(r.blocking_count for r in audit_runs)
    total_auto_fixable = sum(r.auto_fixable_count for r in audit_runs)
    total_errors = sum(r.error_count for r in audit_runs)
    total_warnings = sum(r.warning_count for r in audit_runs)

    # Collect dimension scores (from readiness audits)
    merged_dimensions: dict | None = None
    for run in audit_runs:
        if run.dimension_scores:
            if merged_dimensions is None:
                merged_dimensions = {}
            merged_dimensions.update(run.dimension_scores)

    # Collect risk score (from change-risk audits)
    risk_score: float | None = None
    risk_level: str | None = None
    for run in audit_runs:
        if run.risk_score is not None:
            risk_score = run.risk_score
            risk_level = run.risk_level

    # Determine merged verdict
    verdicts = [r.verdict for r in audit_runs]

    if total_blocking > 0:
        verdict = "blocked"
    elif all(v == "approved" for v in verdicts):
        verdict = "approved"
    elif any(v == "changes_required" for v in verdicts):
        verdict = "changes_required"
    else:
        verdict = "unverified"

    return {
        "verdict": verdict,
        "finding_count": total_findings,
        "blocking_count": total_blocking,
        "auto_fixable_count": total_auto_fixable,
        "error_count": total_errors,
        "warning_count": total_warnings,
        "dimension_scores": merged_dimensions,
        "risk_score": risk_score,
        "risk_level": risk_level,
    }


# ---------------------------------------------------------------------------
# Smart runner selection
# ---------------------------------------------------------------------------

RISK_TO_PERSONA: dict[str, list[str]] = {
    "auth-boundary": ["security"],
    "secrets-exposure": ["security"],
    "iam-terraform": ["security"],
    "api-contract": ["architecture", "code-quality"],
    "api-protocol": ["architecture"],
    "shared-module": ["architecture", "code-quality"],
    "database-migration": ["adversarial"],
    "database-schema": ["adversarial", "performance"],
    "crd-definition": ["architecture"],
    "deployment-config": ["adversarial"],
    "no-test-changes": ["code-quality"],
}


def select_persona_runners(risk_factors: list[dict]) -> list[str]:
    """Select persona runners based on change risk factors.

    Maps risk factor categories to the most relevant review personas,
    avoiding unnecessary LLM calls for irrelevant personas.

    Args:
        risk_factors: List of risk factor dicts with "id" keys.

    Returns:
        Deduplicated list of persona audit family names to run.
    """
    if not risk_factors:
        return ["code-quality"]  # default: always run code quality

    selected: set[str] = set()
    for factor in risk_factors:
        factor_id = factor.get("id", "")
        # Strip "risk-" prefix if present
        category = factor_id.replace("risk-", "")
        if category in RISK_TO_PERSONA:
            selected.update(RISK_TO_PERSONA[category])

    # Always include code-quality as baseline
    selected.add("code-quality")
    return sorted(selected)


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


async def assess_readiness(
    db: AsyncSession,
    jira_key: str,
    include_agent: bool = False,
) -> dict[str, Any]:
    """Full readiness assessment for a JIRA issue.

    Runs the pipeline in tier order:
      1. Readiness dimensions (deterministic)
      2. Change risk score (deterministic, if MR linked)
      3. Review personas (agent, if include_agent=True — smart-selected)

    Args:
        db: Async SQLAlchemy session.
        jira_key: JIRA issue key (e.g., "COMPUTE-2059").
        include_agent: Whether to include LLM-based persona reviews.

    Returns:
        Dict with merged verdict, CTA state, and audit run details.
    """
    # Tier 1: readiness dimensions
    tier1_runs = await run_audit(
        db, "jira_issue", jira_key, families=["readiness-dimensions"]
    )

    # Tier 2: change risk (if MR is linked via entity links)
    tier2_runs: list[AuditRun] = []
    from app.models.entity_link import EntityLink as EL

    mr_links = await db.execute(
        select(EL).where(
            EL.from_id == jira_key,
            EL.from_type == "jira_issue",
            EL.to_type == "gitlab_merge_request",
        )
    )
    linked_mrs = list(mr_links.scalars().all())
    for link in linked_mrs:
        mr_runs = await run_audit(
            db, "gitlab_merge_request", link.to_id,
            families=["change-risk-score"],
        )
        tier2_runs.extend(mr_runs)

    # Tier 3: persona reviews (smart-selected from risk factors)
    tier3_runs: list[AuditRun] = []
    if include_agent and linked_mrs:
        # Determine which personas to run based on risk factors
        risk_factors: list[dict] = []
        for run in tier2_runs:
            if run.risk_factors:
                risk_factors.extend(run.risk_factors)

        persona_families = select_persona_runners(risk_factors)
        logger.info("Smart-selected persona runners: %s", persona_families)

        for link in linked_mrs:
            persona_runs = await run_audit(
                db, "gitlab_merge_request", link.to_id,
                families=persona_families,
            )
            tier3_runs.extend(persona_runs)

    # Merge all runs
    all_runs = tier1_runs + tier2_runs + tier3_runs
    merged = compute_merged_verdict(all_runs)

    # Derive CTA
    from app.services.cta_engine import derive_cta_state

    readiness = merged.get("verdict", "unverified")
    if readiness == "approved":
        readiness = "ready"
    elif readiness in ("changes_required", "blocked"):
        readiness = "needs-work" if readiness == "changes_required" else "blocked"
    else:
        readiness = "exploratory-only"

    cta = derive_cta_state(
        readiness=readiness,
        findings=[],
        auto_fixable_count=merged.get("auto_fixable_count", 0),
        blocking_count=merged.get("blocking_count", 0),
    )

    # Total cost
    total_cost = sum(r.cost_usd for r in all_runs)

    return {
        **merged,
        "cta": {
            "label": cta.label,
            "action": cta.action,
            "subtext": cta.subtext,
            "style": cta.style,
        },
        "audit_run_count": len(all_runs),
        "total_cost_usd": total_cost,
        "persona_runners_used": [r.audit_family for r in tier3_runs],
    }


# ---------------------------------------------------------------------------
# Built-in runners
# ---------------------------------------------------------------------------


class ReadinessAuditRunner:
    """Readiness dimensions audit runner.

    Wraps ``readiness_scorer.score_dimensions()`` and
    ``readiness_scorer.compute_readiness_verdict()`` to produce a
    deterministic readiness assessment for JIRA tickets.
    """

    audit_family: str = "readiness-dimensions"
    required_context: list[str] = ["jira_issue"]

    async def run(self, request: AuditRequest) -> AuditRunResult:
        from app.services.readiness_scorer import (
            build_readiness_findings,
            compute_readiness_confidence,
            compute_readiness_verdict,
            score_dimensions,
        )

        issue = request.jira_issue
        assert issue is not None, "ReadinessAuditRunner requires jira_issue context"

        scores = score_dimensions(
            description=issue.get("description", ""),
            acceptance_criteria=issue.get("acceptance_criteria"),
            labels=issue.get("labels"),
        )

        verdict = compute_readiness_verdict(scores)
        confidence = compute_readiness_confidence(scores)
        findings = build_readiness_findings(scores, request.target_id)

        return AuditRunResult(
            verdict=verdict,
            confidence=confidence,
            findings=findings,
            dimension_scores=scores,
        )


class ChangeRiskAuditRunner:
    """Change risk scoring audit runner.

    Wraps ``change_risk_scorer.compute_change_risk()`` and
    ``change_risk_scorer.build_risk_findings()`` to produce a
    deterministic risk assessment for GitLab merge requests.
    """

    audit_family: str = "change-risk-score"
    required_context: list[str] = ["gitlab_merge_request"]

    async def run(self, request: AuditRequest) -> AuditRunResult:
        from app.services.change_risk_scorer import (
            build_risk_findings,
            compute_change_risk,
        )

        mr = request.merge_request
        assert mr is not None, "ChangeRiskAuditRunner requires gitlab_merge_request context"

        # Extract data from serialised MR dict
        changed_files = mr.get("changed_files", []) or request.changed_files or []
        additions = mr.get("additions", 0)
        deletions = mr.get("deletions", 0)

        risk_result = compute_change_risk(
            changed_files=changed_files,
            additions=additions,
            deletions=deletions,
        )

        # Determine verdict from risk level
        level = risk_result["level"]
        if level == "high":
            verdict = "changes_required"
        elif level == "medium":
            verdict = "changes_required"
        else:
            verdict = "approved"

        mr_identifier = mr.get("id", request.target_id)
        findings = build_risk_findings(risk_result, mr_identifier)

        return AuditRunResult(
            verdict=verdict,
            confidence=0.85,  # deterministic scorer, moderate confidence
            findings=findings,
            risk_score=risk_result["score"],
            risk_level=risk_result["level"],
            risk_factors=risk_result["factors"],
        )


# ---------------------------------------------------------------------------
# Auto-registration of built-in runners
# ---------------------------------------------------------------------------

def _register_builtins() -> None:
    """Register built-in audit runners at module import time."""
    register_audit(ReadinessAuditRunner())
    register_audit(ChangeRiskAuditRunner())


_register_builtins()


# ---------------------------------------------------------------------------
# Import persona runners to trigger their auto-registration
# ---------------------------------------------------------------------------
# This import MUST come after _register_builtins() to avoid circular imports.
# The persona runner module imports AuditRequest/AuditRunResult/register_audit
# from this module, so this module must be fully initialised first.

try:
    import app.services.audit_runners  # noqa: F401 — triggers _register_persona_runners()
except Exception as _exc:
    logger.warning("Failed to load persona audit runners: %s", _exc)
