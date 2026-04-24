"""Workspace API endpoints."""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import workspace_service

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models

class WorkspaceCreate(BaseModel):
    created_from_type: str  # "jira", "agent", "mr", "deployment"
    created_from_id: str
    project: Optional[str] = None
    title: Optional[str] = None
    auto_discover: bool = True


class WorkspaceUpdate(BaseModel):
    title: Optional[str] = None
    archived: Optional[bool] = None


class JiraTicketAdd(BaseModel):
    jira_key: str
    is_primary: bool = False


class JiraTicketUpdate(BaseModel):
    is_primary: Optional[bool] = None
    description_expanded: Optional[bool] = None
    comments_expanded: Optional[bool] = None


class AgentAdd(BaseModel):
    agent_id: str  # UUID as string
    is_pinned: bool = True
    linked_jira_keys: Optional[list[str]] = None


class AgentUpdate(BaseModel):
    is_pinned: Optional[bool] = None
    linked_jira_keys: Optional[list[str]] = None


class BranchAdd(BaseModel):
    branch_name: str
    worktree_path: Optional[str] = None
    is_active: bool = False
    related_jira_keys: Optional[list[str]] = None


class MRAdd(BaseModel):
    mr_project: str
    mr_iid: int
    branch_name: str
    status: Optional[str] = None
    url: Optional[str] = None


class DeploymentAdd(BaseModel):
    environment: str
    namespace: str = ""
    version: Optional[str] = None
    status: Optional[str] = None
    url: Optional[str] = None


def _serialize_workspace(workspace) -> dict:
    """Convert workspace model to API response."""
    return {
        "id": str(workspace.id),
        "title": workspace.title,
        "project": workspace.project,
        "created_from": {
            "type": workspace.created_from_type,
            "id": workspace.created_from_id,
        },
        "jira_tickets": [
            {
                "key": ticket.jira_key,
                "is_primary": ticket.is_primary,
                "description_expanded": ticket.description_expanded,
                "comments_expanded": ticket.comments_expanded,
                "pinned_at": ticket.pinned_at.isoformat() if ticket.pinned_at else None,
            }
            for ticket in workspace.jira_tickets
        ],
        "agents": [
            {
                "id": str(wa.agent_id),
                "session_id": wa.agent.claude_session_id if wa.agent else None,
                "title": wa.agent.title if wa.agent else None,
                "first_prompt": wa.agent.first_prompt if wa.agent else None,
                "status": wa.agent.status if wa.agent else "dead",
                "is_pinned": wa.is_pinned,
                "message_count": wa.agent.message_count if wa.agent else 0,
                "added_at": wa.added_at.isoformat() if wa.added_at else None,
                "last_active_at": wa.agent.last_active_at.isoformat() if wa.agent and wa.agent.last_active_at else None,
            }
            for wa in workspace.agents
        ],
        "branches": [
            {
                "name": branch.branch_name,
                "worktree_path": branch.worktree_path,
                "is_active": branch.is_active,
                "added_at": branch.added_at.isoformat() if branch.added_at else None,
            }
            for branch in workspace.branches
        ],
        "merge_requests": [
            {
                "project": mr.mr_project,
                "iid": mr.mr_iid,
                "branch_name": mr.branch_name,
                "status": mr.status,
                "url": mr.url,
                "added_at": mr.added_at.isoformat() if mr.added_at else None,
            }
            for mr in workspace.merge_requests
        ],
        "deployments": [
            {
                "environment": dep.environment,
                "namespace": dep.namespace,
                "version": dep.version,
                "status": dep.status,
                "url": dep.url,
                "added_at": dep.added_at.isoformat() if dep.added_at else None,
                "updated_at": dep.updated_at.isoformat() if dep.updated_at else None,
            }
            for dep in workspace.deployments
        ],
        "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
        "last_active_at": workspace.last_active_at.isoformat() if workspace.last_active_at else None,
        "archived_at": workspace.archived_at.isoformat() if workspace.archived_at else None,
    }


# Workspace CRUD Endpoints

@router.post("")
async def create_workspace(
    request: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new workspace from any resource type."""
    workspace = await workspace_service.create_workspace(
        db,
        created_from_type=request.created_from_type,
        created_from_id=request.created_from_id,
        project=request.project,
        title=request.title,
        auto_discover=request.auto_discover,
    )

    return _serialize_workspace(workspace)


@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get workspace by ID with all relationships."""
    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    workspace = await workspace_service.get_workspace(db, workspace_uuid)

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return _serialize_workspace(workspace)


@router.get("")
async def list_workspaces(
    project: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List workspaces with filtering and pagination."""
    workspaces, total = await workspace_service.list_workspaces(
        db,
        project=project,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )

    return {
        "workspaces": [_serialize_workspace(w) for w in workspaces],
        "total": total,
    }


@router.patch("/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    request: WorkspaceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update workspace metadata."""
    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    workspace = await workspace_service.update_workspace(
        db,
        workspace_uuid,
        title=request.title,
        archived=request.archived,
    )

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return _serialize_workspace(workspace)


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete workspace and all associations."""
    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    success = await workspace_service.delete_workspace(db, workspace_uuid)

    if not success:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return {"success": True}


# JIRA Ticket Management

@router.post("/{workspace_id}/jira")
async def add_jira_ticket(
    workspace_id: str,
    request: JiraTicketAdd,
    db: AsyncSession = Depends(get_db),
):
    """Add JIRA ticket to workspace."""
    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    await workspace_service.add_jira_ticket(
        db,
        workspace_uuid,
        request.jira_key,
        is_primary=request.is_primary,
    )

    workspace = await workspace_service.get_workspace(db, workspace_uuid)
    return _serialize_workspace(workspace)


@router.delete("/{workspace_id}/jira/{jira_key}")
async def remove_jira_ticket(
    workspace_id: str,
    jira_key: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove JIRA ticket from workspace."""
    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    success = await workspace_service.remove_jira_ticket(db, workspace_uuid, jira_key)

    if not success:
        raise HTTPException(status_code=404, detail="JIRA ticket not found in workspace")

    return {"success": True}


@router.patch("/{workspace_id}/jira/{jira_key}")
async def update_jira_ticket(
    workspace_id: str,
    jira_key: str,
    request: JiraTicketUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update JIRA ticket settings."""
    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    ticket = await workspace_service.update_jira_ticket(
        db,
        workspace_uuid,
        jira_key,
        is_primary=request.is_primary,
        description_expanded=request.description_expanded,
        comments_expanded=request.comments_expanded,
    )

    if not ticket:
        raise HTTPException(status_code=404, detail="JIRA ticket not found in workspace")

    workspace = await workspace_service.get_workspace(db, workspace_uuid)
    return _serialize_workspace(workspace)


# Agent Management

@router.post("/{workspace_id}/agents")
async def add_agent(
    workspace_id: str,
    request: AgentAdd,
    db: AsyncSession = Depends(get_db),
):
    """Add agent to workspace."""
    try:
        workspace_uuid = uuid.UUID(workspace_id)
        agent_uuid = uuid.UUID(request.agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace or agent ID")

    await workspace_service.add_agent(
        db,
        workspace_uuid,
        agent_uuid,
        is_pinned=request.is_pinned,
        linked_jira_keys=request.linked_jira_keys,
    )

    workspace = await workspace_service.get_workspace(db, workspace_uuid)
    return _serialize_workspace(workspace)


@router.delete("/{workspace_id}/agents/{agent_id}")
async def remove_agent(
    workspace_id: str,
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove agent from workspace."""
    try:
        workspace_uuid = uuid.UUID(workspace_id)
        agent_uuid = uuid.UUID(agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace or agent ID")

    success = await workspace_service.remove_agent(db, workspace_uuid, agent_uuid)

    if not success:
        raise HTTPException(status_code=404, detail="Agent not found in workspace")

    return {"success": True}


@router.patch("/{workspace_id}/agents/{agent_id}")
async def update_agent(
    workspace_id: str,
    agent_id: str,
    request: AgentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update agent settings."""
    try:
        workspace_uuid = uuid.UUID(workspace_id)
        agent_uuid = uuid.UUID(agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace or agent ID")

    agent = await workspace_service.update_agent(
        db,
        workspace_uuid,
        agent_uuid,
        is_pinned=request.is_pinned,
        linked_jira_keys=request.linked_jira_keys,
    )

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found in workspace")

    workspace = await workspace_service.get_workspace(db, workspace_uuid)
    return _serialize_workspace(workspace)


# Branch Management

@router.post("/{workspace_id}/branches")
async def add_branch(
    workspace_id: str,
    request: BranchAdd,
    db: AsyncSession = Depends(get_db),
):
    """Add branch to workspace."""
    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    await workspace_service.add_branch(
        db,
        workspace_uuid,
        request.branch_name,
        worktree_path=request.worktree_path,
        is_active=request.is_active,
        related_jira_keys=request.related_jira_keys,
    )

    workspace = await workspace_service.get_workspace(db, workspace_uuid)
    return _serialize_workspace(workspace)


@router.delete("/{workspace_id}/branches/{branch_name}")
async def remove_branch(
    workspace_id: str,
    branch_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove branch from workspace."""
    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    success = await workspace_service.remove_branch(db, workspace_uuid, branch_name)

    if not success:
        raise HTTPException(status_code=404, detail="Branch not found in workspace")

    return {"success": True}


# MR Management

@router.post("/{workspace_id}/mrs")
async def add_merge_request(
    workspace_id: str,
    request: MRAdd,
    db: AsyncSession = Depends(get_db),
):
    """Add merge request to workspace."""
    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    await workspace_service.add_merge_request(
        db,
        workspace_uuid,
        request.mr_project,
        request.mr_iid,
        request.branch_name,
        status=request.status,
        url=request.url,
    )

    workspace = await workspace_service.get_workspace(db, workspace_uuid)
    return _serialize_workspace(workspace)


@router.delete("/{workspace_id}/mrs/{mr_project}/{mr_iid}")
async def remove_merge_request(
    workspace_id: str,
    mr_project: str,
    mr_iid: int,
    db: AsyncSession = Depends(get_db),
):
    """Remove merge request from workspace."""
    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    success = await workspace_service.remove_merge_request(db, workspace_uuid, mr_project, mr_iid)

    if not success:
        raise HTTPException(status_code=404, detail="MR not found in workspace")

    return {"success": True}


# Deployment Management

@router.post("/{workspace_id}/deployments")
async def add_deployment(
    workspace_id: str,
    request: DeploymentAdd,
    db: AsyncSession = Depends(get_db),
):
    """Add deployment to workspace."""
    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    await workspace_service.add_deployment(
        db,
        workspace_uuid,
        request.environment,
        namespace=request.namespace,
        version=request.version,
        status=request.status,
        url=request.url,
    )

    workspace = await workspace_service.get_workspace(db, workspace_uuid)
    return _serialize_workspace(workspace)


@router.delete("/{workspace_id}/deployments/{environment}/{namespace}")
async def remove_deployment(
    workspace_id: str,
    environment: str,
    namespace: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Remove deployment from workspace."""
    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    success = await workspace_service.remove_deployment(db, workspace_uuid, environment, namespace)

    if not success:
        raise HTTPException(status_code=404, detail="Deployment not found in workspace")

    return {"success": True}


# Auto-Discovery

@router.post("/{workspace_id}/discover")
async def discover_resources(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Auto-discover and add related resources to workspace."""
    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    discovered = await workspace_service.auto_discover_resources(db, workspace_uuid)

    workspace = await workspace_service.get_workspace(db, workspace_uuid)

    return {
        "workspace": _serialize_workspace(workspace),
        "discovered": discovered,
    }
