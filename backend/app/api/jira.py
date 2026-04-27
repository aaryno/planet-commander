import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.jira_issue import JiraIssue
from app.services.jira_service import search_tickets

logger = logging.getLogger(__name__)

router = APIRouter()

# TODO: Add SSE (Server-Sent Events) for JIRA sync progress
# Similar to Slack sync (/slack/sync-stream), create /jira/sync-stream
# to show real-time progress when syncing JIRA tickets, including:
# - "Syncing tickets... X/Y complete"
# - "Found X new/updated tickets"
# - "Last updated: Xm ago"
# This will provide better UX than the spinner-only approach


@router.get("/ticket/{key}")
async def get_ticket(key: str, db: AsyncSession = Depends(get_db)):
    """Fetch a single JIRA ticket by key (e.g. COMPUTE-2152). Checks local DB first."""
    # Try local DB first
    result = await db.execute(
        select(JiraIssue).where(JiraIssue.external_key == key.upper())
    )
    row = result.scalar_one_or_none()
    if row:
        return {
            "key": row.external_key,
            "summary": row.title,
            "status": row.status,
            "priority": row.priority or "",
            "assignee": row.assignee or "Unassigned",
            "type": "Task",
            "labels": row.labels if isinstance(row.labels, list) else [],
            "fix_versions": row.fix_versions if isinstance(row.fix_versions, list) else [],
            "description": row.description or "",
            "comments": [],
            "url": row.url,
        }

    # Fallback to JIRA API
    tickets = await search_tickets(key, limit=1, db=db)
    if not tickets:
        raise HTTPException(status_code=404, detail=f"Ticket not found: {key}")
    return tickets[0]


@router.get("/search")
async def search_jira_tickets(
    q: str = Query("", description="Search text or ticket key"),
    project: str | None = Query(None, description="JIRA project key (comma-separated for multiple)"),
    limit: int = Query(20, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Search JIRA tickets — local DB first (53K+ tickets), falls back to JIRA API."""
    query = q.strip()
    if not query:
        # No query — return recent from API
        projects = [p.strip() for p in project.split(",") if p.strip()] if project else None
        tickets = await search_tickets(q, projects=projects, limit=limit, db=db)
        return {"tickets": tickets, "total": len(tickets)}

    # Search local DB with ILIKE across external_key, title, assignee
    pattern = f"%{query}%"
    stmt = select(JiraIssue).where(
        or_(
            JiraIssue.external_key.ilike(pattern),
            JiraIssue.title.ilike(pattern),
            JiraIssue.assignee.ilike(pattern),
        )
    )
    # Apply project filter if provided
    if project:
        projects_list = [p.strip().upper() for p in project.split(",") if p.strip()]
        if projects_list:
            project_filters = [JiraIssue.external_key.ilike(f"{p}-%") for p in projects_list]
            stmt = stmt.where(or_(*project_filters))

    stmt = stmt.order_by(JiraIssue.updated_at.desc()).limit(limit)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    if rows:
        tickets = [
            {
                "key": r.external_key,
                "summary": r.title,
                "status": r.status,
                "priority": r.priority or "",
                "assignee": r.assignee or "Unassigned",
                "type": "Task",
                "labels": r.labels if isinstance(r.labels, list) else [],
                "fix_versions": r.fix_versions if isinstance(r.fix_versions, list) else [],
                "description": r.description or "",
                "comments": [],
                "url": r.url,
            }
            for r in rows
        ]
        return {"tickets": tickets, "total": len(tickets), "source": "local"}

    # Fallback to JIRA API if nothing found locally
    projects_list = [p.strip() for p in project.split(",") if p.strip()] if project else None
    try:
        tickets = await search_tickets(q, projects=projects_list, limit=limit, db=db)
        return {"tickets": tickets, "total": len(tickets), "source": "api"}
    except Exception as e:
        logger.warning(f"JIRA API search failed: {e}")
        return {"tickets": [], "total": 0, "source": "api_error"}


@router.get("/my-tickets")
async def my_tickets(db: AsyncSession = Depends(get_db)):
    tickets = await search_tickets("", limit=30, db=db)
    return {"tickets": tickets, "total": len(tickets)}


@router.get("/sprint")
async def active_sprint():
    return {"sprint": None, "tickets": []}


@router.post("/tickets")
async def create_ticket():
    return {"status": "not implemented"}


@router.put("/tickets/{key}")
async def update_ticket(key: str):
    return {"status": "not implemented"}


@router.get("/summary")
async def jira_summary(
    project: str | None = Query(None, description="JIRA project key"),
    sprint: str | None = Query(None, description="Sprint name"),
    db: AsyncSession = Depends(get_db),
):
    """Get JIRA summary with 'Me' and 'Team' sections.

    Returns tickets grouped by relationship and status.
    """
    from app.services.jira_service import get_jira_summary

    try:
        summary = await get_jira_summary(project=project, db=db)
        return summary
    except Exception as e:
        logger.error("Failed to get JIRA summary: %s", e)
        # Return empty summary on error
        return {
            "me": {
                "assigned": [],
                "watching": [],
                "paired": [],
                "mr_reviewed": [],
                "slack_discussed": [],
            },
            "team": {
                "by_status": {
                    "backlog": [],
                    "selected": [],
                    "in_progress": [],
                    "in_review": [],
                    "ready_to_deploy": [],
                    "monitoring": [],
                    "done": [],
                },
                "stats": {
                    "backlog_count": 0,
                    "selected_count": 0,
                    "in_progress_count": 0,
                    "in_review_count": 0,
                    "ready_to_deploy_count": 0,
                    "monitoring_count": 0,
                    "done_count": 0,
                },
            },
            "project": project or "COMPUTE",
            "error": str(e),
        }

    # Old mock data below - can be removed after verifying real data works
    """
    from datetime import datetime, timedelta
    mock_tickets = [
        {
            "key": "COMPUTE-1234",
            "summary": "Fix task lease timeout logic",
            "status": "In Progress",
            "assignee": "Aaryn Olsson",
            "priority": "High",
            "type": "Bug",
            "fix_versions": [],
            "labels": ["wx", "critical"],
            "my_relationships": {
                "assigned": True,
                "watching": False,
                "paired": False,
                "mr_reviewed": False,
                "slack_discussed": True,
            },
            "linked_mrs": [
                {
                    "project": "wx",
                    "iid": 831,
                    "title": "fix: task lease timeout",
                    "url": "https://hello.planet.com/code/wx/wx/-/merge_requests/831",
                }
            ],
            "slack_mentions": [
                {
                    "channel": "compute-platform",
                    "timestamp": "2026-03-11T14:30:00Z",
                    "user": "aaryn",
                }
            ],
            "age_days": 3,
            "last_updated": (datetime.now() - timedelta(days=1)).isoformat(),
        },
        {
            "key": "COMPUTE-5678",
            "summary": "G4 OOM detection improvements",
            "status": "In Review",
            "assignee": "Dharma Bellamkonda",
            "priority": "Medium",
            "type": "Story",
            "fix_versions": [],
            "labels": ["g4"],
            "my_relationships": {
                "assigned": False,
                "watching": True,
                "paired": False,
                "mr_reviewed": True,
                "slack_discussed": False,
            },
            "linked_mrs": [
                {
                    "project": "g4",
                    "iid": 456,
                    "title": "feat: improve OOM detection",
                    "url": "https://hello.planet.com/code/product/g4-wk/g4/-/merge_requests/456",
                }
            ],
            "age_days": 7,
            "last_updated": (datetime.now() - timedelta(hours=3)).isoformat(),
        },
        {
            "key": "COMPUTE-9012",
            "summary": "Add retry logic to Jobs worker",
            "status": "Selected for Development",
            "assignee": "Justin Smallkowski",
            "priority": "Medium",
            "type": "Story",
            "fix_versions": [],
            "labels": ["jobs"],
            "my_relationships": {
                "assigned": False,
                "watching": False,
                "paired": False,
                "mr_reviewed": False,
                "slack_discussed": False,
            },
            "age_days": 2,
            "last_updated": (datetime.now() - timedelta(days=2)).isoformat(),
        },
        {
            "key": "COMPUTE-3456",
            "summary": "Temporal Cloud onboarding automation",
            "status": "Done",
            "assignee": "Aaryn Olsson",
            "priority": "High",
            "type": "Story",
            "fix_versions": ["Q1-2026"],
            "labels": ["temporal", "automation"],
            "my_relationships": {
                "assigned": True,
                "watching": False,
                "paired": False,
                "mr_reviewed": False,
                "slack_discussed": True,
            },
            "linked_mrs": [
                {
                    "project": "temporal",
                    "iid": 234,
                    "title": "feat: automated tenant onboarding",
                    "url": "https://hello.planet.com/code/temporal/temporalio-cloud/-/merge_requests/234",
                }
            ],
            "age_days": 14,
            "last_updated": (datetime.now() - timedelta(days=1)).isoformat(),
        },
        {
            "key": "COMPUTE-7890",
            "summary": "WX task queue monitoring dashboard",
            "status": "In Progress",
            "assignee": "Ryan Cleere",
            "priority": "Low",
            "type": "Task",
            "fix_versions": [],
            "labels": ["wx", "monitoring"],
            "my_relationships": {
                "assigned": False,
                "watching": False,
                "paired": False,
                "mr_reviewed": False,
                "slack_discussed": False,
            },
            "age_days": 5,
            "last_updated": (datetime.now() - timedelta(hours=8)).isoformat(),
        },
        {
            "key": "COMPUTE-1111",
            "summary": "Optimize WX podrunner resource limits",
            "status": "Ready to Deploy",
            "assignee": "Aaryn Olsson",
            "priority": "High",
            "type": "Story",
            "fix_versions": [],
            "labels": ["wx", "performance"],
            "my_relationships": {
                "assigned": True,
                "watching": False,
                "paired": False,
                "mr_reviewed": False,
                "slack_discussed": False,
            },
            "linked_mrs": [
                {
                    "project": "wx",
                    "iid": 890,
                    "title": "feat: optimize podrunner limits",
                    "url": "https://hello.planet.com/code/wx/wx/-/merge_requests/890",
                }
            ],
            "age_days": 1,
            "last_updated": (datetime.now() - timedelta(hours=2)).isoformat(),
        },
        {
            "key": "COMPUTE-2222",
            "summary": "G4 API rate limiting",
            "status": "Monitoring",
            "assignee": "Dharma Bellamkonda",
            "priority": "Medium",
            "type": "Story",
            "fix_versions": [],
            "labels": ["g4", "production"],
            "my_relationships": {
                "assigned": False,
                "watching": True,
                "paired": False,
                "mr_reviewed": False,
                "slack_discussed": False,
            },
            "age_days": 3,
            "last_updated": (datetime.now() - timedelta(days=1)).isoformat(),
        },
    ]

    # Group tickets by relationship (Me section)
    me_assigned = [t for t in mock_tickets if t["my_relationships"]["assigned"] and t["status"] != "Done"]
    me_watching = [t for t in mock_tickets if t["my_relationships"]["watching"] and not t["my_relationships"]["assigned"]]
    me_paired = [t for t in mock_tickets if t["my_relationships"]["paired"]]
    me_mr_reviewed = [t for t in mock_tickets if t["my_relationships"]["mr_reviewed"] and not t["my_relationships"]["assigned"]]
    me_slack_discussed = [t for t in mock_tickets if t["my_relationships"]["slack_discussed"] and not any([
        t["my_relationships"]["assigned"],
        t["my_relationships"]["watching"],
        t["my_relationships"]["paired"],
        t["my_relationships"]["mr_reviewed"],
    ])]

    # Group tickets by status (Team section)
    team_selected = [t for t in mock_tickets if t["status"] == "Selected for Development"]
    team_in_progress = [t for t in mock_tickets if t["status"] == "In Progress"]
    team_in_review = [t for t in mock_tickets if t["status"] == "In Review" or t["status"] == "Code Review"]
    team_ready_to_deploy = [t for t in mock_tickets if t["status"] == "Ready to Deploy" or t["status"] == "Released to Staging"]
    team_monitoring = [t for t in mock_tickets if t["status"] == "Monitoring"]
    team_done = [t for t in mock_tickets if t["status"] == "Done"]

    return {
        "me": {
            "assigned": me_assigned,
            "watching": me_watching,
            "paired": me_paired,
            "mr_reviewed": me_mr_reviewed,
            "slack_discussed": me_slack_discussed,
        },
        "team": {
            "by_status": {
                "selected": team_selected,
                "in_progress": team_in_progress,
                "in_review": team_in_review,
                "ready_to_deploy": team_ready_to_deploy,
                "monitoring": team_monitoring,
                "done": team_done,
            },
            "stats": {
                "selected_count": len(team_selected),
                "in_progress_count": len(team_in_progress),
                "in_review_count": len(team_in_review),
                "ready_to_deploy_count": len(team_ready_to_deploy),
                "monitoring_count": len(team_monitoring),
                "done_count": len(team_done),
            },
        },
        "current_sprint": "Sprint 24",
        "project": project or "COMPUTE",
    }
    """
