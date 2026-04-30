"""GitLab service for multi-project MR management.

Supports listing, viewing, approving, and reviewing MRs across all projects.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.mr_review import MRReview
from app.services.project_config import ProjectConfigService

logger = logging.getLogger(__name__)

# Simple in-memory cache for MR lists
_mrs_cache: dict[str, tuple[list[dict], datetime]] = {}
_CACHE_TTL = timedelta(seconds=30)

GLAB_DIR = Path.home() / "tools" / "glab"
GLAB_MR = str(GLAB_DIR / "glab-mr")


async def _run_cmd(cmd: list[str], timeout: int = 30) -> str | None:
    """Run a command and return stdout, or None on failure."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode != 0:
            logger.warning("Command failed: %s -> %s", " ".join(cmd), stderr.decode("utf-8", errors="replace")[:200])
            return None
        return stdout.decode("utf-8", errors="replace")
    except asyncio.TimeoutError:
        logger.warning("Command timed out: %s", " ".join(cmd))
        return None
    except FileNotFoundError:
        logger.warning("Command not found: %s", cmd[0])
        return None


def _parse_mr_list(output: str, repo: str, web_url: str) -> list[dict]:
    """Parse glab-mr list output into structured MR data."""
    mrs = []
    for line in output.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("Showing") or line.startswith("No "):
            continue

        # Tab-separated: !iid, repo!iid, title, branch info
        parts = line.split("\t")
        if len(parts) >= 3:
            iid_match = re.match(r"!(\d+)", parts[0])
            if iid_match:
                iid = int(iid_match.group(1))
                title = parts[2].strip()
                branch = ""
                if len(parts) >= 4:
                    branch_match = re.search(r"← \((.+?)\)", parts[3])
                    if branch_match:
                        branch = branch_match.group(1)
                mrs.append({
                    "iid": iid,
                    "title": title,
                    "branch": branch,
                    "url": f"{web_url}/-/merge_requests/{iid}",
                })
                continue

        # Fallback: look for !number pattern
        match = re.match(r"!(\d+)\s+(.+)", line)
        if match:
            iid = int(match.group(1))
            mrs.append({
                "iid": iid,
                "title": match.group(2).strip(),
                "branch": "",
                "url": f"{web_url}/-/merge_requests/{iid}",
            })
    return mrs


async def list_open_mrs(
    db: AsyncSession,
    projects: list[str] | None = None,
) -> dict[str, Any]:
    """List open MRs across selected projects.

    Args:
        db: Database session for project config and review state lookups.
        projects: List of project keys. If None, fetch all active projects.

    Returns:
        Dict with mrs: [{project, iid, title, author, age_created, age_last_commit, url, is_draft, is_mine}, ...]
    """
    project_configs = await ProjectConfigService(db).get_gitlab_projects()

    if projects is None:
        projects = list(project_configs.keys())

    # Fetch MRs from all projects in parallel
    tasks = []
    valid_projects = []
    for project_key in projects:
        config = project_configs.get(project_key)
        if not config:
            continue
        valid_projects.append(project_key)
        tasks.append(_fetch_project_mrs(project_key, config))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Combine results
    all_mrs = []
    for project_key, result in zip(valid_projects, results):
        if isinstance(result, Exception):
            logger.error(f"Failed to fetch MRs for {project_key}: {result}")
            continue
        all_mrs.extend(result)

    # Fetch review state for all MRs
    review_states = await _get_review_states(db, all_mrs)
    for mr in all_mrs:
        key = f"{mr['project']}:{mr['iid']}"
        mr['needs_review'] = review_states.get(key, {}).get('needs_review', True)
        mr['reviews'] = review_states.get(key, {}).get('reviews', [])

    return {
        "mrs": all_mrs,
        "total": len(all_mrs),
        "projects": projects,
    }


async def _fetch_project_mrs(project_key: str, config: dict) -> list[dict]:
    """Fetch MRs for a single project with detailed information."""
    # Check cache first
    now = datetime.utcnow()
    if project_key in _mrs_cache:
        cached_mrs, cached_at = _mrs_cache[project_key]
        if now - cached_at < _CACHE_TTL:
            logger.debug(f"Using cached MRs for {project_key} (age: {(now - cached_at).seconds}s)")
            return cached_mrs

    repo = config["repo"]
    web_url = config["web_url"]

    # Fetch MR list
    output = await _run_cmd([GLAB_MR, "list", repo, "50"])
    if output is None:
        return []

    basic_mrs = _parse_mr_list(output, repo, web_url)

    # Fetch detailed info for each MR in parallel
    tasks = [_fetch_mr_details(project_key, mr["iid"], repo) for mr in basic_mrs]
    detailed_results = await asyncio.gather(*tasks, return_exceptions=True)

    mrs = []
    for basic_mr, details in zip(basic_mrs, detailed_results):
        if isinstance(details, Exception):
            # Fallback to basic info if details fail
            mrs.append({
                "project": project_key,
                "iid": basic_mr["iid"],
                "title": basic_mr["title"],
                "author": "unknown",
                "url": basic_mr["url"],
                "branch": basic_mr.get("branch", ""),
                "age_created_hours": 0,
                "age_last_commit_hours": 0,
                "is_draft": False,
                "is_mine": False,
            })
        else:
            mrs.append(details)

    # Cache the results
    _mrs_cache[project_key] = (mrs, datetime.utcnow())

    return mrs


async def _fetch_mr_details(project: str, mr_iid: int, repo: str) -> dict:
    """Fetch detailed MR information using glab API."""
    # Use glab API to get MR details
    output = await _run_cmd(["glab", "api", f"projects/{repo.replace('/', '%2F')}/merge_requests/{mr_iid}"])
    if output is None:
        return {
            "project": project,
            "iid": mr_iid,
            "title": f"MR #{mr_iid}",
            "author": "unknown",
            "age_created_hours": 0,
            "age_last_commit_hours": 0,
            "is_draft": False,
            "is_mine": False,
        }

    try:
        data = json.loads(output)

        # Calculate ages
        created_at = datetime.fromisoformat(data.get("created_at", "").replace("Z", "+00:00"))
        age_created = (datetime.now(created_at.tzinfo) - created_at).total_seconds() / 3600

        updated_at = datetime.fromisoformat(data.get("updated_at", "").replace("Z", "+00:00"))
        age_last_commit = (datetime.now(updated_at.tzinfo) - updated_at).total_seconds() / 3600

        # Check if mine (compare author username)
        author = data.get("author", {}).get("username", "")
        is_mine = author == "aaryn"  # TODO: Make this dynamic

        return {
            "project": project,
            "iid": mr_iid,
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "author": author,
            "url": data.get("web_url", ""),
            "branch": data.get("source_branch", ""),
            "target_branch": data.get("target_branch", ""),
            "sha": data.get("sha", ""),
            "age_created_hours": int(age_created),
            "age_last_commit_hours": int(age_last_commit),
            "is_draft": data.get("draft", False) or data.get("work_in_progress", False),
            "is_mine": is_mine,
            "state": data.get("state", ""),
            "labels": data.get("labels", []),
            "pipeline_status": data.get("pipeline", {}).get("status") if data.get("pipeline") else None,
            "pipeline_web_url": data.get("pipeline", {}).get("web_url") if data.get("pipeline") else None,
            "has_conflicts": data.get("has_conflicts", False),
            "user_notes_count": data.get("user_notes_count", 0),
            "merge_status": data.get("merge_status", ""),
            "upvotes": data.get("upvotes", 0),
        }
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error(f"Failed to parse MR details for {project}!{mr_iid}: {e}")
        return {
            "project": project,
            "iid": mr_iid,
            "title": f"MR #{mr_iid}",
            "author": "unknown",
            "age_created_hours": 0,
            "age_last_commit_hours": 0,
            "is_draft": False,
            "is_mine": False,
        }


async def get_mr_pipelines(
    db: AsyncSession,
    project: str,
    mr_iid: int,
) -> dict:
    """Fetch all pipelines for an MR, with jobs for the most recent one."""
    project_configs = await ProjectConfigService(db).get_gitlab_projects()
    config = project_configs.get(project)
    if not config:
        return {"pipelines": [], "error": f"Unknown project: {project}"}

    repo = config["repo"]
    encoded_repo = repo.replace("/", "%2F")

    # Fetch pipelines for the MR
    output = await _run_cmd([
        "glab", "api",
        f"projects/{encoded_repo}/merge_requests/{mr_iid}/pipelines",
    ])
    if output is None:
        return {"pipelines": []}

    try:
        pipelines_data = json.loads(output)
    except json.JSONDecodeError:
        return {"pipelines": []}

    pipelines = []
    for p in pipelines_data:
        pipelines.append({
            "id": p.get("id"),
            "status": p.get("status"),
            "ref": p.get("ref"),
            "sha": p.get("sha", "")[:8],
            "web_url": p.get("web_url"),
            "created_at": p.get("created_at"),
            "source": p.get("source"),
        })

    if not pipelines:
        return {"pipelines": []}

    # Fetch jobs for the most recent (first) pipeline
    active_pipeline = pipelines[0]
    jobs_output = await _run_cmd([
        "glab", "api",
        f"projects/{encoded_repo}/pipelines/{active_pipeline['id']}/jobs?per_page=100",
    ])

    stages: dict[str, list[dict]] = {}
    if jobs_output:
        try:
            jobs_data = json.loads(jobs_output)
            for job in jobs_data:
                stage_name = job.get("stage", "unknown")
                if stage_name not in stages:
                    stages[stage_name] = []
                duration = job.get("duration")
                stages[stage_name].append({
                    "id": job.get("id"),
                    "name": job.get("name"),
                    "status": job.get("status"),
                    "stage": stage_name,
                    "duration": round(duration, 1) if duration else None,
                    "web_url": job.get("web_url"),
                    "failure_reason": job.get("failure_reason"),
                    "allow_failure": job.get("allow_failure", False),
                    "started_at": job.get("started_at"),
                    "finished_at": job.get("finished_at"),
                })
        except json.JSONDecodeError:
            pass

    # Compute stage-level status summary
    stage_list = []
    for stage_name, jobs in stages.items():
        statuses = [j["status"] for j in jobs]
        if "failed" in statuses:
            stage_status = "failed"
        elif "running" in statuses:
            stage_status = "running"
        elif "pending" in statuses or "created" in statuses:
            stage_status = "pending"
        elif "manual" in statuses and all(s in ("manual", "skipped", "success") for s in statuses):
            stage_status = "manual"
        elif all(s == "skipped" for s in statuses):
            stage_status = "skipped"
        elif all(s in ("success", "skipped") for s in statuses):
            stage_status = "success"
        elif "canceled" in statuses:
            stage_status = "canceled"
        else:
            stage_status = "unknown"

        stage_list.append({
            "name": stage_name,
            "status": stage_status,
            "jobs": jobs,
        })

    active_pipeline["stages"] = stage_list

    return {
        "pipelines": pipelines,
        "active_pipeline": active_pipeline,
    }


async def get_mr_details(db: AsyncSession, project: str, mr_iid: int) -> dict:
    """Get detailed information for a specific MR."""
    project_configs = await ProjectConfigService(db).get_gitlab_projects()
    config = project_configs.get(project, {})
    repo = config.get("repo", project)

    details = await _fetch_mr_details(project, mr_iid, repo)

    # Get review state
    review_state = await _get_mr_review_state(db, project, mr_iid)
    details['needs_review'] = review_state.get('needs_review', True)
    details['reviews'] = review_state.get('reviews', [])

    return details


async def approve_mr(db: AsyncSession, project: str, mr_iid: int) -> dict:
    """Approve an MR using glab."""
    project_configs = await ProjectConfigService(db).get_gitlab_projects()
    config = project_configs.get(project)
    if not config:
        return {"success": False, "error": f"Unknown project: {project}"}
    repo = config["repo"]

    output = await _run_cmd(["glab", "mr", "approve", str(mr_iid), "-R", repo])
    if output is None:
        return {"success": False, "error": "Failed to approve MR"}

    return {"success": True, "message": "MR approved"}


async def close_mr(db: AsyncSession, project: str, mr_iid: int) -> dict:
    """Close an MR using glab."""
    project_configs = await ProjectConfigService(db).get_gitlab_projects()
    config = project_configs.get(project)
    if not config:
        return {"success": False, "error": f"Unknown project: {project}"}
    repo = config["repo"]

    output = await _run_cmd(["glab", "mr", "close", str(mr_iid), "-R", repo])
    if output is None:
        return {"success": False, "error": "Failed to close MR"}

    return {"success": True, "message": "MR closed"}


async def toggle_draft(db: AsyncSession, project: str, mr_iid: int, is_draft: bool) -> dict:
    """Toggle draft status on an MR."""
    project_configs = await ProjectConfigService(db).get_gitlab_projects()
    config = project_configs.get(project)
    if not config:
        return {"success": False, "error": f"Unknown project: {project}"}
    repo = config["repo"]

    output = await _run_cmd([
        "glab", "api", "-X", "PUT",
        f"projects/{repo.replace('/', '%2F')}/merge_requests/{mr_iid}",
        "-f", f"draft={str(is_draft).lower()}"
    ])

    if output is None:
        return {"success": False, "error": "Failed to toggle draft status"}

    return {"success": True, "is_draft": is_draft}


async def trigger_review(
    db: AsyncSession,
    project: str,
    mr_iid: int,
    agent_api_url: str = "http://localhost:9000/api",
) -> dict:
    """Trigger an MR review: spawn agent + run audit persona pipeline.

    Orchestrates:
    1. Spawn main review agent on the MR's branch (Chat tab)
    2. Run Tier 2 risk scoring → select relevant personas
    3. Run Tier 3 persona reviews in parallel via Claude API (Summary tab)
    4. Store structured AuditRun + AuditFinding results
    """
    from app.services.review_orchestrator import orchestrate_review

    try:
        result = await orchestrate_review(
            db, project, mr_iid, agent_api_url
        )

        if result.error:
            return {"success": False, "error": result.error}

        return {
            "success": True,
            "agent_id": result.agent_id,
            "session_id": result.session_id,
            "message": f"Review agent spawned + {len(result.personas_selected)} persona audits queued",
            "personas": result.personas_selected,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
            "diff_lines": result.diff_lines,
        }

    except Exception as e:
        logger.error(f"Failed to trigger review: {e}")
        return {"success": False, "error": str(e)}


async def _get_review_states(session: AsyncSession, mrs: list[dict]) -> dict[str, dict]:
    """Get review states for multiple MRs."""
    if not mrs:
        return {}

    # Build lookup keys
    keys = [(mr["project"], mr["iid"]) for mr in mrs]

    # Fetch all review records
    stmt = select(MRReview).where(
        MRReview.project.in_([k[0] for k in keys])
    )
    result = await session.execute(stmt)
    reviews = {(r.project, r.mr_iid): r for r in result.scalars()}

    # Build result dict
    states = {}
    for mr in mrs:
        key = f"{mr['project']}:{mr['iid']}"
        review = reviews.get((mr["project"], mr["iid"]))

        if review:
            # Check if commit changed
            needs_review = review.needs_review or (review.last_commit_sha != mr.get("sha"))
            states[key] = {
                "needs_review": needs_review,
                "reviews": review.reviews,
            }
        else:
            states[key] = {
                "needs_review": True,
                "reviews": [],
            }

    return states


async def _get_mr_review_state(session: AsyncSession, project: str, mr_iid: int) -> dict:
    """Get review state for a single MR."""
    stmt = select(MRReview).where(
        MRReview.project == project,
        MRReview.mr_iid == mr_iid,
    )
    result = await session.execute(stmt)
    review = result.scalar_one_or_none()

    if review:
        return {
            "needs_review": review.needs_review,
            "reviews": review.reviews,
        }

    return {
        "needs_review": True,
        "reviews": [],
    }


async def _record_review(
    session: AsyncSession,
    project: str,
    mr_iid: int,
    agent_id: str,
    session_id: str,
    commit_sha: str,
) -> None:
    """Record a review session for an MR."""
    stmt = select(MRReview).where(
        MRReview.project == project,
        MRReview.mr_iid == mr_iid,
    )
    result = await session.execute(stmt)
    review = result.scalar_one_or_none()

    review_entry = {
        "agent_id": agent_id,
        "session_id": session_id,
        "commit_sha": commit_sha,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if review:
        # Update existing
        review.reviews.append(review_entry)
        review.last_commit_sha = commit_sha
        review.needs_review = False
        review.updated_at = datetime.utcnow()
    else:
        # Create new
        review = MRReview(
            project=project,
            mr_iid=mr_iid,
            last_commit_sha=commit_sha,
            needs_review=False,
            reviews=[review_entry],
        )
        session.add(review)

    await session.commit()
