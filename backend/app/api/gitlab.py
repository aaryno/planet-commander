from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import gitlab_service

router = APIRouter()


@router.get("")
async def list_open_mrs(
    projects: list[str] | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List open MRs across selected projects.

    Query params:
        projects: List of project keys. If empty, fetch all active projects.
    """
    return await gitlab_service.list_open_mrs(db, projects)


@router.get("/by-jira/{jira_key}")
async def mrs_by_jira_key(jira_key: str, db: AsyncSession = Depends(get_db)):
    """Find open MRs whose title contains a JIRA key."""
    try:
        result = await gitlab_service.list_open_mrs(db, None)
        key_upper = jira_key.upper()
        filtered = [
            mr for mr in result.get("mrs", [])
            if key_upper in (mr.get("title", "") or "").upper()
        ]
        return {"mrs": filtered, "total": len(filtered), "jira_key": jira_key}
    except Exception:
        return {"mrs": [], "total": 0, "jira_key": jira_key}


@router.get("/{project}/{mr_iid}")
async def get_mr_details(
    project: str,
    mr_iid: int,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed information for a specific MR."""
    return await gitlab_service.get_mr_details(db, project, mr_iid)


@router.get("/{project}/{mr_iid}/pipelines")
async def get_mr_pipelines(
    project: str,
    mr_iid: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all pipelines and jobs for an MR."""
    return await gitlab_service.get_mr_pipelines(db, project, mr_iid)


@router.post("/{project}/{mr_iid}/review")
async def trigger_mr_review(
    project: str,
    mr_iid: int,
    db: AsyncSession = Depends(get_db),
):
    """Trigger an MR review by spawning a headless agent."""
    return await gitlab_service.trigger_review(db, project, mr_iid)


@router.post("/{project}/{mr_iid}/approve")
async def approve_mr(
    project: str,
    mr_iid: int,
    db: AsyncSession = Depends(get_db),
):
    """Approve an MR."""
    return await gitlab_service.approve_mr(db, project, mr_iid)


@router.post("/{project}/{mr_iid}/close")
async def close_mr(
    project: str,
    mr_iid: int,
    db: AsyncSession = Depends(get_db),
):
    """Close an MR."""
    return await gitlab_service.close_mr(db, project, mr_iid)


@router.post("/{project}/{mr_iid}/draft")
async def toggle_draft(
    project: str,
    mr_iid: int,
    is_draft: bool,
    db: AsyncSession = Depends(get_db),
):
    """Toggle draft status on an MR."""
    return await gitlab_service.toggle_draft(db, project, mr_iid, is_draft)


@router.get("/{project}/{mr_iid}/review/findings")
async def get_review_findings(
    project: str, mr_iid: int, db: AsyncSession = Depends(get_db)
):
    """Get structured audit findings for an MR review.

    Returns persona-grouped findings for the Summary tab.
    """
    from app.services.review_orchestrator import get_review_findings
    return await get_review_findings(db, project, mr_iid)
