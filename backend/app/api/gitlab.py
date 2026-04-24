from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import gitlab_service

router = APIRouter()


@router.get("")
async def list_open_mrs(projects: list[str] | None = Query(None)):
    """List open MRs across selected projects.

    Query params:
        projects: List of project keys (wx, jobs, g4, temporal). If empty, fetch all.
    """
    return await gitlab_service.list_open_mrs(projects)


@router.get("/by-jira/{jira_key}")
async def mrs_by_jira_key(jira_key: str):
    """Find open MRs whose title contains a JIRA key."""
    try:
        result = await gitlab_service.list_open_mrs(None)
        key_upper = jira_key.upper()
        filtered = [
            mr for mr in result.get("mrs", [])
            if key_upper in (mr.get("title", "") or "").upper()
        ]
        return {"mrs": filtered, "total": len(filtered), "jira_key": jira_key}
    except Exception:
        return {"mrs": [], "total": 0, "jira_key": jira_key}


@router.get("/{project}/{mr_iid}")
async def get_mr_details(project: str, mr_iid: int):
    """Get detailed information for a specific MR."""
    return await gitlab_service.get_mr_details(project, mr_iid)


@router.get("/{project}/{mr_iid}/pipelines")
async def get_mr_pipelines(project: str, mr_iid: int):
    """Get all pipelines and jobs for an MR."""
    return await gitlab_service.get_mr_pipelines(project, mr_iid)


@router.post("/{project}/{mr_iid}/review")
async def trigger_mr_review(project: str, mr_iid: int):
    """Trigger an MR review by spawning a headless agent."""
    return await gitlab_service.trigger_review(project, mr_iid)


@router.post("/{project}/{mr_iid}/approve")
async def approve_mr(project: str, mr_iid: int):
    """Approve an MR."""
    return await gitlab_service.approve_mr(project, mr_iid)


@router.post("/{project}/{mr_iid}/close")
async def close_mr(project: str, mr_iid: int):
    """Close an MR."""
    return await gitlab_service.close_mr(project, mr_iid)


@router.post("/{project}/{mr_iid}/draft")
async def toggle_draft(project: str, mr_iid: int, is_draft: bool):
    """Toggle draft status on an MR."""
    return await gitlab_service.toggle_draft(project, mr_iid, is_draft)


@router.get("/{project}/{mr_iid}/review/findings")
async def get_review_findings(
    project: str, mr_iid: int, db: AsyncSession = Depends(get_db)
):
    """Get structured audit findings for an MR review.

    Returns persona-grouped findings for the Summary tab.
    """
    from app.services.review_orchestrator import get_review_findings
    return await get_review_findings(db, project, mr_iid)
