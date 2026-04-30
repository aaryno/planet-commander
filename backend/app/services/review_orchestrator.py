"""Review orchestrator — coordinates MR review agent + audit persona pipeline.

Spawns a main Claude Code agent for interactive review (Chat tab) while
running the structured audit pipeline in parallel (Summary tab).

Flow:
  1. Ensure MR exists in DB (sync from GitLab if needed)
  2. Fetch actual diff content from GitLab
  3. Spawn main review agent on the MR's branch
  4. Run Tier 2 risk scoring → select persona runners
  5. Run Tier 3 persona runners in parallel with diff content
  6. Store AuditRun + AuditFinding results
  7. Link results to MR review record
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_finding import AuditFinding
from app.models.audit_run import AuditRun
from app.models.gitlab_merge_request import GitLabMergeRequest
from app.models.mr_review import MRReview
from app.services.project_config import ProjectConfigService

logger = logging.getLogger(__name__)

GLAB_DIR = Path.home() / "tools" / "glab"
GLAB_MR = str(GLAB_DIR / "glab-mr")


@dataclass
class ReviewResult:
    """Result of orchestrated review."""

    agent_id: str | None = None
    session_id: str | None = None
    audit_run_ids: list[str] = field(default_factory=list)
    personas_selected: list[str] = field(default_factory=list)
    risk_score: float | None = None
    risk_level: str | None = None
    diff_lines: int = 0
    error: str | None = None


async def _fetch_diff(project: str, mr_iid: int, repo: str) -> str | None:
    """Fetch MR diff content via glab."""
    if not repo:
        return None

    try:
        proc = await asyncio.create_subprocess_exec(
            GLAB_MR, "diff", str(mr_iid), repo,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode != 0:
            logger.warning("glab diff failed for %s!%d: %s", project, mr_iid, stderr.decode()[:200])
            return None
        return stdout.decode("utf-8", errors="replace")
    except asyncio.TimeoutError:
        logger.warning("glab diff timed out for %s!%d", project, mr_iid)
        return None
    except Exception as e:
        logger.warning("glab diff error for %s!%d: %s", project, mr_iid, e)
        return None


async def _ensure_mr_in_db(
    db: AsyncSession, project: str, mr_iid: int
) -> GitLabMergeRequest | None:
    """Find MR in DB, or return None if not synced yet."""
    project_configs = await ProjectConfigService(db).get_gitlab_projects()
    config = project_configs.get(project)
    if not config:
        return None
    repo = config["repo"]

    result = await db.execute(
        select(GitLabMergeRequest).where(
            GitLabMergeRequest.repository == repo,
            GitLabMergeRequest.external_mr_id == mr_iid,
        )
    )
    return result.scalar_one_or_none()


async def _run_audit_pipeline(
    db: AsyncSession,
    mr: GitLabMergeRequest,
    diff_content: str | None,
) -> tuple[list[AuditRun], list[str], float | None, str | None]:
    """Run Tier 2 risk scoring + Tier 3 persona reviews.

    Returns (audit_runs, personas_selected, risk_score, risk_level).
    """
    from app.services.audit_dispatcher import (
        AuditRequest,
        run_audit,
        select_persona_runners,
    )

    mr_id = str(mr.id)

    # Tier 2: Change risk scoring
    tier2_runs = await run_audit(
        db, "gitlab_merge_request", mr_id, families=["change-risk-score"]
    )

    risk_score: float | None = None
    risk_level: str | None = None
    risk_factors: list[dict] = []
    for run in tier2_runs:
        if run.risk_score is not None:
            risk_score = run.risk_score
            risk_level = run.risk_level
        if run.risk_factors:
            risk_factors.extend(run.risk_factors)

    # Tier 3: Select and run persona runners
    personas = select_persona_runners(risk_factors)
    logger.info(
        "MR %s!%d: risk=%.2f (%s), personas=%s",
        mr.repository, mr.external_mr_id,
        risk_score or 0, risk_level or "unknown", personas,
    )

    # Inject diff content into the audit request if available
    if diff_content:
        _patch_diff_into_request(mr_id, diff_content)

    tier3_runs = await run_audit(
        db, "gitlab_merge_request", mr_id, families=personas
    )

    if diff_content:
        _unpatch_diff()

    all_runs = tier2_runs + tier3_runs
    return all_runs, personas, risk_score, risk_level


# Temporary thread-local storage for diff content injection
_diff_override: dict[str, str] = {}


def _patch_diff_into_request(mr_id: str, diff_content: str) -> None:
    """Store diff content for persona runners to pick up."""
    _diff_override[mr_id] = diff_content


def _unpatch_diff() -> None:
    """Clear diff override."""
    _diff_override.clear()


def get_diff_override(mr_id: str) -> str | None:
    """Called by enhanced persona runner to get injected diff content."""
    return _diff_override.get(mr_id)


async def orchestrate_review(
    db: AsyncSession,
    project: str,
    mr_iid: int,
    agent_api_url: str = "http://localhost:9000/api",
) -> ReviewResult:
    """Full review orchestration: agent + audit pipeline.

    1. Fetch diff from GitLab
    2. Spawn main review agent on the MR's branch
    3. Run audit pipeline (risk scoring + personas) in background
    4. Record review session
    """
    from app.services.gitlab_service import _fetch_mr_details, _record_review
    import aiohttp

    result = ReviewResult()

    # Look up repo path from DB
    project_configs = await ProjectConfigService(db).get_gitlab_projects()
    config = project_configs.get(project, {})
    repo = config.get("repo", "")
    if not repo:
        result.error = f"Unknown project: {project}"
        return result

    # 1. Fetch MR details and diff in parallel
    try:
        mr_details, diff_content = await asyncio.gather(
            _fetch_mr_details(project, mr_iid, repo),
            _fetch_diff(project, mr_iid, repo),
        )
    except Exception as e:
        result.error = f"Failed to fetch MR details: {e}"
        return result

    result.diff_lines = len(diff_content.splitlines()) if diff_content else 0

    # 2. Spawn main review agent
    try:
        async with aiohttp.ClientSession() as client:
            spawn_payload = {
                "project": project,
                "worktree_branch": mr_details["branch"],
                "initial_prompt": (
                    f"Review MR !{mr_iid}: {mr_details['title']}\n\n"
                    f"Branch: {mr_details['branch']}\n\n"
                    f"Use /mr-review to review this merge request."
                ),
                "source": "mr-review",
            }

            async with client.post(
                f"{agent_api_url}/agents", json=spawn_payload
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    result.error = f"Failed to spawn agent: {error_text}"
                    return result

                agent_data = await resp.json()
                result.agent_id = agent_data["id"]
                result.session_id = agent_data["session_id"]

    except Exception as e:
        result.error = f"Failed to spawn agent: {e}"
        return result

    # 3. Record review
    try:
        await _record_review(
            db, project, mr_iid,
            result.agent_id, result.session_id, mr_details["sha"],
        )
    except Exception as e:
        logger.warning("Failed to record review: %s", e)

    # 4. Run audit pipeline in background
    mr_record = await _ensure_mr_in_db(db, project, mr_iid)
    if mr_record:
        asyncio.create_task(
            _run_audit_background(mr_record, diff_content, result)
        )
    else:
        logger.warning(
            "MR %s!%d not in DB — skipping audit pipeline. "
            "Run MR sync first.",
            project, mr_iid,
        )

    return result


async def _run_audit_background(
    mr: GitLabMergeRequest,
    diff_content: str | None,
    result: ReviewResult,
) -> None:
    """Background task to run the audit pipeline."""
    try:
        from app.database import get_db as _get_db_gen

        async for session in _get_db_gen():
            audit_runs, personas, risk_score, risk_level = await _run_audit_pipeline(
                session, mr, diff_content
            )
            result.audit_run_ids = [str(r.id) for r in audit_runs]
            result.personas_selected = personas
            result.risk_score = risk_score
            result.risk_level = risk_level

            logger.info(
                "Audit pipeline complete for %s!%d: %d runs, personas=%s",
                mr.repository, mr.external_mr_id,
                len(audit_runs), personas,
            )
            break
    except Exception as e:
        logger.exception("Audit pipeline failed for %s!%d: %s", mr.repository, mr.external_mr_id, e)


async def get_review_findings(
    db: AsyncSession, project: str, mr_iid: int
) -> dict[str, Any]:
    """Fetch audit findings for an MR review.

    Returns structured data for the Summary tab.
    """
    project_configs = await ProjectConfigService(db).get_gitlab_projects()
    config = project_configs.get(project)
    if not config:
        return {"findings": [], "personas": [], "status": "unknown"}
    repo = config["repo"]

    # Find the MR
    mr_result = await db.execute(
        select(GitLabMergeRequest).where(
            GitLabMergeRequest.repository == repo,
            GitLabMergeRequest.external_mr_id == mr_iid,
        )
    )
    mr = mr_result.scalar_one_or_none()
    if not mr:
        return {"findings": [], "personas": [], "status": "no_mr"}

    mr_id = str(mr.id)

    # Fetch all audit runs for this MR
    runs_result = await db.execute(
        select(AuditRun)
        .where(
            AuditRun.target_type == "gitlab_merge_request",
            AuditRun.target_id == mr_id,
        )
        .order_by(AuditRun.created_at.desc())
    )
    runs = list(runs_result.scalars().all())

    if not runs:
        return {"findings": [], "personas": [], "status": "pending"}

    # Fetch findings for all runs
    run_ids = [r.id for r in runs]
    findings_result = await db.execute(
        select(AuditFinding)
        .where(AuditFinding.audit_run_id.in_(run_ids))
        .order_by(AuditFinding.severity.desc())
    )
    findings = list(findings_result.scalars().all())

    # Group by persona
    persona_results: list[dict] = []
    for run in runs:
        run_findings = [f for f in findings if f.audit_run_id == run.id]
        persona_results.append({
            "persona": run.audit_family,
            "verdict": run.verdict,
            "model": run.model_used,
            "duration_ms": run.duration_ms,
            "cost_usd": run.cost_usd,
            "risk_score": run.risk_score,
            "risk_level": run.risk_level,
            "finding_count": len(run_findings),
            "blocking_count": sum(1 for f in run_findings if f.blocking),
            "findings": [
                {
                    "id": str(f.id),
                    "code": f.code,
                    "category": f.category,
                    "severity": f.severity,
                    "title": f.title,
                    "description": f.description,
                    "blocking": f.blocking,
                    "auto_fixable": f.auto_fixable,
                    "source_file": f.source_file,
                    "source_line": f.source_line,
                    "status": f.status,
                }
                for f in run_findings
            ],
        })

    # Compute merged verdict
    from app.services.audit_dispatcher import compute_merged_verdict
    merged = compute_merged_verdict(runs)

    return {
        "status": "complete",
        "verdict": merged["verdict"],
        "finding_count": merged["finding_count"],
        "blocking_count": merged["blocking_count"],
        "risk_score": merged.get("risk_score"),
        "risk_level": merged.get("risk_level"),
        "total_cost_usd": sum(r.cost_usd for r in runs),
        "personas": persona_results,
    }
