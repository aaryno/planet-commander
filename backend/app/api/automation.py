"""Workflow automation API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict, List

from app.database import get_db
from app.services.pr_automation import PRAutomationService
from app.services.jira_sync_automation import JiraSyncAutomationService
from app.services.slack_notifications import SlackNotificationService
from app.services.gitlab_automation import GitLabAutomationService

router = APIRouter(prefix="/automation", tags=["automation"])


# PR/MR Automation

@router.post("/pr/chat/{chat_id}")
async def create_pr_from_chat(
    chat_id: str,
    target_branch: str = "main",
    auto_push: bool = False,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Create a merge request from a chat session."""
    pr_service = PRAutomationService(db)

    try:
        result = await pr_service.create_pr_from_chat(
            chat_id,
            target_branch=target_branch,
            auto_push=auto_push
        )
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pr/context/{context_id}")
async def create_pr_from_context(
    context_id: str,
    target_branch: str = "main",
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Create a merge request from a work context."""
    pr_service = PRAutomationService(db)

    try:
        result = await pr_service.create_pr_from_context(
            context_id,
            target_branch=target_branch
        )
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# JIRA Automation

@router.post("/jira/sync-context/{context_id}")
async def sync_context_to_jira(
    context_id: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Sync work context status to linked JIRA tickets."""
    jira_service = JiraSyncAutomationService(db)

    try:
        result = await jira_service.sync_context_to_jira(context_id)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jira/comment-context/{context_id}")
async def comment_on_context_jira(
    context_id: str,
    comment: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Add comment to all JIRA tickets linked to a context."""
    jira_service = JiraSyncAutomationService(db)

    try:
        result = await jira_service.add_context_comment_to_jira(context_id, comment)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# Slack Notifications

@router.post("/slack/notify-pr")
async def notify_pr_created(
    channel: str,
    pr_url: str,
    title: str,
    author: str,
    jira_key: str | None = None,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Send Slack notification about new PR/MR."""
    slack_service = SlackNotificationService(db)

    try:
        result = await slack_service.notify_pr_created(channel, pr_url, title, author, jira_key)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/slack/notify-status-change")
async def notify_status_change(
    channel: str,
    context_title: str,
    old_status: str,
    new_status: str,
    jira_keys: List[str] | None = None,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Send Slack notification about context status change."""
    slack_service = SlackNotificationService(db)

    try:
        result = await slack_service.notify_context_status_change(
            channel, context_title, old_status, new_status, jira_keys
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/slack/notify-health-alert")
async def notify_health_alert(
    channel: str,
    context_title: str,
    health_status: str,
    issues: List[str],
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Send Slack notification about context health issues."""
    slack_service = SlackNotificationService(db)

    try:
        result = await slack_service.notify_health_alert(channel, context_title, health_status, issues)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# GitLab Automation

@router.post("/gitlab/approve-mr")
async def approve_mr(
    project: str,
    mr_iid: int,
    worktree_path: str | None = None
) -> Dict[str, Any]:
    """Approve a GitLab merge request."""
    gitlab_service = GitLabAutomationService()

    try:
        result = await gitlab_service.approve_mr(project, mr_iid, worktree_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gitlab/merge-mr")
async def merge_mr(
    project: str,
    mr_iid: int,
    when_pipeline_succeeds: bool = True,
    delete_source_branch: bool = True,
    squash: bool = False,
    worktree_path: str | None = None
) -> Dict[str, Any]:
    """Merge a GitLab merge request."""
    gitlab_service = GitLabAutomationService()

    try:
        result = await gitlab_service.merge_mr(
            project, mr_iid, when_pipeline_succeeds, delete_source_branch, squash, worktree_path
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gitlab/mr-status")
async def check_mr_status(
    project: str,
    mr_iid: int,
    worktree_path: str | None = None
) -> Dict[str, Any]:
    """Check GitLab MR status (pipeline, approvals, mergeable)."""
    gitlab_service = GitLabAutomationService()

    try:
        result = await gitlab_service.check_mr_status(project, mr_iid, worktree_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gitlab/auto-approve-merge")
async def auto_approve_and_merge(
    project: str,
    mr_iid: int,
    worktree_path: str | None = None,
    squash: bool = False
) -> Dict[str, Any]:
    """Auto-approve and merge a GitLab MR (convenience endpoint)."""
    gitlab_service = GitLabAutomationService()

    try:
        result = await gitlab_service.auto_approve_and_merge(project, mr_iid, worktree_path, squash)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
