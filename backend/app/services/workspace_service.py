"""Workspace management service - CRUD operations and auto-discovery."""

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import Agent
from app.models.workspace import (
    Workspace,
    WorkspaceAgent,
    WorkspaceAgentJira,
    WorkspaceBranch,
    WorkspaceBranchJira,
    WorkspaceDeployment,
    WorkspaceJiraTicket,
    WorkspaceMR,
)

logger = logging.getLogger(__name__)

# JIRA ticket pattern
_JIRA_RE = re.compile(r"(COMPUTE-\d+|WX-\d+|G4-\d+|JOBS-\d+|TEMPORAL-\d+)", re.IGNORECASE)


async def create_workspace(
    db: AsyncSession,
    created_from_type: str,
    created_from_id: str,
    project: Optional[str] = None,
    title: Optional[str] = None,
    auto_discover: bool = True,
) -> Workspace:
    """Create a new workspace from any resource type.

    Args:
        db: Database session
        created_from_type: "jira", "agent", "mr", or "deployment"
        created_from_id: Resource identifier (JIRA key, agent ID, etc.)
        project: Project name (inferred if not provided)
        title: Custom title (auto-generated if not provided)
        auto_discover: Whether to auto-discover related resources

    Returns:
        Created workspace with related resources populated
    """
    # Infer project if not provided
    if not project:
        project = await _infer_project(db, created_from_type, created_from_id)

    # Generate title if not provided
    if not title:
        title = await _generate_title(db, created_from_type, created_from_id)

    # Create workspace
    workspace = Workspace(
        id=uuid.uuid4(),
        title=title,
        project=project,
        created_from_type=created_from_type,
        created_from_id=created_from_id,
        created_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc),
    )
    db.add(workspace)
    await db.flush()

    # Add initial resource based on type
    if created_from_type == "jira":
        await add_jira_ticket(db, workspace.id, created_from_id, is_primary=True)
    elif created_from_type == "agent":
        await add_agent(db, workspace.id, uuid.UUID(created_from_id))
    elif created_from_type == "mr":
        # Parse MR ID (format: "project/iid")
        parts = created_from_id.split("/")
        if len(parts) == 2:
            mr_project, mr_iid = parts[0], int(parts[1])
            # We'll add branch/MR in auto-discovery

    # Auto-discover related resources
    if auto_discover:
        await auto_discover_resources(db, workspace.id)

    await db.commit()

    # Reload with relationships
    return await get_workspace(db, workspace.id)


async def get_workspace(db: AsyncSession, workspace_id: uuid.UUID) -> Optional[Workspace]:
    """Get workspace with all relationships loaded."""
    result = await db.execute(
        select(Workspace)
        .where(Workspace.id == workspace_id)
        .options(
            selectinload(Workspace.jira_tickets),
            selectinload(Workspace.agents).selectinload(WorkspaceAgent.agent),
            selectinload(Workspace.branches),
            selectinload(Workspace.merge_requests),
            selectinload(Workspace.deployments),
        )
    )
    return result.scalar_one_or_none()


async def list_workspaces(
    db: AsyncSession,
    project: Optional[str] = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Workspace], int]:
    """List workspaces with filtering and pagination."""
    query = select(Workspace)

    if project:
        query = query.where(Workspace.project == project)

    if not include_archived:
        query = query.where(Workspace.archived_at.is_(None))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get paginated results
    query = (
        query
        .order_by(Workspace.last_active_at.desc())
        .limit(limit)
        .offset(offset)
        .options(
            selectinload(Workspace.jira_tickets),
            selectinload(Workspace.agents).selectinload(WorkspaceAgent.agent),
            selectinload(Workspace.branches),
            selectinload(Workspace.merge_requests),
            selectinload(Workspace.deployments),
        )
    )

    result = await db.execute(query)
    workspaces = list(result.scalars().all())

    return workspaces, total


async def update_workspace(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    title: Optional[str] = None,
    archived: Optional[bool] = None,
) -> Optional[Workspace]:
    """Update workspace metadata."""
    workspace = await get_workspace(db, workspace_id)
    if not workspace:
        return None

    if title is not None:
        workspace.title = title

    if archived is not None:
        workspace.archived_at = datetime.now(timezone.utc) if archived else None

    workspace.last_active_at = datetime.now(timezone.utc)

    await db.commit()
    return await get_workspace(db, workspace_id)


async def delete_workspace(db: AsyncSession, workspace_id: uuid.UUID) -> bool:
    """Delete workspace and all associations (cascade)."""
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        return False

    await db.delete(workspace)
    await db.commit()
    return True


# JIRA Ticket Management

async def add_jira_ticket(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    jira_key: str,
    is_primary: bool = False,
) -> WorkspaceJiraTicket:
    """Add JIRA ticket to workspace."""
    # If setting as primary, unmark other primary tickets
    if is_primary:
        result = await db.execute(
            select(WorkspaceJiraTicket).where(
                and_(
                    WorkspaceJiraTicket.workspace_id == workspace_id,
                    WorkspaceJiraTicket.is_primary == True,
                )
            )
        )
        existing_primary = result.scalars().all()
        for ticket in existing_primary:
            ticket.is_primary = False

    ticket = WorkspaceJiraTicket(
        workspace_id=workspace_id,
        jira_key=jira_key.upper(),
        is_primary=is_primary,
    )
    db.add(ticket)

    # Update workspace last_active_at
    await _touch_workspace(db, workspace_id)

    await db.commit()
    return ticket


async def remove_jira_ticket(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    jira_key: str,
) -> bool:
    """Remove JIRA ticket from workspace."""
    result = await db.execute(
        select(WorkspaceJiraTicket).where(
            and_(
                WorkspaceJiraTicket.workspace_id == workspace_id,
                WorkspaceJiraTicket.jira_key == jira_key.upper(),
            )
        )
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        return False

    await db.delete(ticket)
    await _touch_workspace(db, workspace_id)
    await db.commit()
    return True


async def update_jira_ticket(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    jira_key: str,
    is_primary: Optional[bool] = None,
    description_expanded: Optional[bool] = None,
    comments_expanded: Optional[bool] = None,
) -> Optional[WorkspaceJiraTicket]:
    """Update JIRA ticket settings."""
    result = await db.execute(
        select(WorkspaceJiraTicket).where(
            and_(
                WorkspaceJiraTicket.workspace_id == workspace_id,
                WorkspaceJiraTicket.jira_key == jira_key.upper(),
            )
        )
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        return None

    if is_primary is not None and is_primary:
        # Unmark other primary tickets
        result = await db.execute(
            select(WorkspaceJiraTicket).where(
                and_(
                    WorkspaceJiraTicket.workspace_id == workspace_id,
                    WorkspaceJiraTicket.is_primary == True,
                    WorkspaceJiraTicket.jira_key != jira_key.upper(),
                )
            )
        )
        existing_primary = result.scalars().all()
        for other in existing_primary:
            other.is_primary = False

        ticket.is_primary = True

    if description_expanded is not None:
        ticket.description_expanded = description_expanded

    if comments_expanded is not None:
        ticket.comments_expanded = comments_expanded

    await _touch_workspace(db, workspace_id)
    await db.commit()
    return ticket


# Agent Management

async def add_agent(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    is_pinned: bool = True,
    linked_jira_keys: Optional[list[str]] = None,
) -> WorkspaceAgent:
    """Add agent to workspace."""
    workspace_agent = WorkspaceAgent(
        workspace_id=workspace_id,
        agent_id=agent_id,
        is_pinned=is_pinned,
    )
    db.add(workspace_agent)

    # Link to JIRA tickets if provided
    if linked_jira_keys:
        for jira_key in linked_jira_keys:
            # Ensure JIRA ticket exists in workspace
            result = await db.execute(
                select(WorkspaceJiraTicket).where(
                    and_(
                        WorkspaceJiraTicket.workspace_id == workspace_id,
                        WorkspaceJiraTicket.jira_key == jira_key.upper(),
                    )
                )
            )
            if result.scalar_one_or_none():
                link = WorkspaceAgentJira(
                    workspace_id=workspace_id,
                    agent_id=agent_id,
                    jira_key=jira_key.upper(),
                )
                db.add(link)

    await _touch_workspace(db, workspace_id)
    await db.commit()
    return workspace_agent


async def remove_agent(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> bool:
    """Remove agent from workspace."""
    result = await db.execute(
        select(WorkspaceAgent).where(
            and_(
                WorkspaceAgent.workspace_id == workspace_id,
                WorkspaceAgent.agent_id == agent_id,
            )
        )
    )
    workspace_agent = result.scalar_one_or_none()

    if not workspace_agent:
        return False

    await db.delete(workspace_agent)
    await _touch_workspace(db, workspace_id)
    await db.commit()
    return True


async def update_agent(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    is_pinned: Optional[bool] = None,
    linked_jira_keys: Optional[list[str]] = None,
) -> Optional[WorkspaceAgent]:
    """Update agent settings."""
    result = await db.execute(
        select(WorkspaceAgent).where(
            and_(
                WorkspaceAgent.workspace_id == workspace_id,
                WorkspaceAgent.agent_id == agent_id,
            )
        )
    )
    workspace_agent = result.scalar_one_or_none()

    if not workspace_agent:
        return None

    if is_pinned is not None:
        workspace_agent.is_pinned = is_pinned

    if linked_jira_keys is not None:
        # Remove existing links
        await db.execute(
            select(WorkspaceAgentJira).where(
                and_(
                    WorkspaceAgentJira.workspace_id == workspace_id,
                    WorkspaceAgentJira.agent_id == agent_id,
                )
            ).delete()
        )

        # Add new links
        for jira_key in linked_jira_keys:
            result = await db.execute(
                select(WorkspaceJiraTicket).where(
                    and_(
                        WorkspaceJiraTicket.workspace_id == workspace_id,
                        WorkspaceJiraTicket.jira_key == jira_key.upper(),
                    )
                )
            )
            if result.scalar_one_or_none():
                link = WorkspaceAgentJira(
                    workspace_id=workspace_id,
                    agent_id=agent_id,
                    jira_key=jira_key.upper(),
                )
                db.add(link)

    await _touch_workspace(db, workspace_id)
    await db.commit()
    return workspace_agent


# Branch Management

async def add_branch(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    branch_name: str,
    worktree_path: Optional[str] = None,
    is_active: bool = False,
    related_jira_keys: Optional[list[str]] = None,
) -> WorkspaceBranch:
    """Add branch to workspace."""
    # If setting as active, unmark other active branches
    if is_active:
        result = await db.execute(
            select(WorkspaceBranch).where(
                and_(
                    WorkspaceBranch.workspace_id == workspace_id,
                    WorkspaceBranch.is_active == True,
                )
            )
        )
        existing_active = result.scalars().all()
        for branch in existing_active:
            branch.is_active = False

    workspace_branch = WorkspaceBranch(
        workspace_id=workspace_id,
        branch_name=branch_name,
        worktree_path=worktree_path,
        is_active=is_active,
    )
    db.add(workspace_branch)

    # Link to JIRA tickets if provided
    if related_jira_keys:
        for jira_key in related_jira_keys:
            result = await db.execute(
                select(WorkspaceJiraTicket).where(
                    and_(
                        WorkspaceJiraTicket.workspace_id == workspace_id,
                        WorkspaceJiraTicket.jira_key == jira_key.upper(),
                    )
                )
            )
            if result.scalar_one_or_none():
                link = WorkspaceBranchJira(
                    workspace_id=workspace_id,
                    branch_name=branch_name,
                    jira_key=jira_key.upper(),
                )
                db.add(link)
    else:
        # Auto-detect JIRA key from branch name
        match = _JIRA_RE.search(branch_name)
        if match:
            jira_key = match.group(1).upper()
            # Check if this JIRA ticket exists in workspace
            result = await db.execute(
                select(WorkspaceJiraTicket).where(
                    and_(
                        WorkspaceJiraTicket.workspace_id == workspace_id,
                        WorkspaceJiraTicket.jira_key == jira_key,
                    )
                )
            )
            if result.scalar_one_or_none():
                link = WorkspaceBranchJira(
                    workspace_id=workspace_id,
                    branch_name=branch_name,
                    jira_key=jira_key,
                )
                db.add(link)

    await _touch_workspace(db, workspace_id)
    await db.commit()
    return workspace_branch


async def remove_branch(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    branch_name: str,
) -> bool:
    """Remove branch from workspace."""
    result = await db.execute(
        select(WorkspaceBranch).where(
            and_(
                WorkspaceBranch.workspace_id == workspace_id,
                WorkspaceBranch.branch_name == branch_name,
            )
        )
    )
    workspace_branch = result.scalar_one_or_none()

    if not workspace_branch:
        return False

    await db.delete(workspace_branch)
    await _touch_workspace(db, workspace_id)
    await db.commit()
    return True


# MR Management

async def add_merge_request(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    mr_project: str,
    mr_iid: int,
    branch_name: str,
    status: Optional[str] = None,
    url: Optional[str] = None,
) -> WorkspaceMR:
    """Add merge request to workspace."""
    workspace_mr = WorkspaceMR(
        workspace_id=workspace_id,
        mr_project=mr_project,
        mr_iid=mr_iid,
        branch_name=branch_name,
        status=status,
        url=url,
    )
    db.add(workspace_mr)

    # Ensure branch exists
    result = await db.execute(
        select(WorkspaceBranch).where(
            and_(
                WorkspaceBranch.workspace_id == workspace_id,
                WorkspaceBranch.branch_name == branch_name,
            )
        )
    )
    if not result.scalar_one_or_none():
        await add_branch(db, workspace_id, branch_name)

    await _touch_workspace(db, workspace_id)
    await db.commit()
    return workspace_mr


async def remove_merge_request(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    mr_project: str,
    mr_iid: int,
) -> bool:
    """Remove merge request from workspace."""
    result = await db.execute(
        select(WorkspaceMR).where(
            and_(
                WorkspaceMR.workspace_id == workspace_id,
                WorkspaceMR.mr_project == mr_project,
                WorkspaceMR.mr_iid == mr_iid,
            )
        )
    )
    workspace_mr = result.scalar_one_or_none()

    if not workspace_mr:
        return False

    await db.delete(workspace_mr)
    await _touch_workspace(db, workspace_id)
    await db.commit()
    return True


# Deployment Management

async def add_deployment(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    environment: str,
    namespace: str = "",
    version: Optional[str] = None,
    status: Optional[str] = None,
    url: Optional[str] = None,
) -> WorkspaceDeployment:
    """Add deployment to workspace."""
    deployment = WorkspaceDeployment(
        workspace_id=workspace_id,
        environment=environment,
        namespace=namespace,
        version=version,
        status=status,
        url=url,
    )
    db.add(deployment)

    await _touch_workspace(db, workspace_id)
    await db.commit()
    return deployment


async def remove_deployment(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    environment: str,
    namespace: str = "",
) -> bool:
    """Remove deployment from workspace."""
    result = await db.execute(
        select(WorkspaceDeployment).where(
            and_(
                WorkspaceDeployment.workspace_id == workspace_id,
                WorkspaceDeployment.environment == environment,
                WorkspaceDeployment.namespace == namespace,
            )
        )
    )
    deployment = result.scalar_one_or_none()

    if not deployment:
        return False

    await db.delete(deployment)
    await _touch_workspace(db, workspace_id)
    await db.commit()
    return True


# Auto-Discovery Logic

async def auto_discover_resources(db: AsyncSession, workspace_id: uuid.UUID) -> dict:
    """Auto-discover and add related resources to workspace.

    Returns:
        Dictionary with counts of discovered resources
    """
    workspace = await get_workspace(db, workspace_id)
    if not workspace:
        return {}

    discovered = {
        "jira_tickets": 0,
        "agents": 0,
        "branches": 0,
        "merge_requests": 0,
    }

    # Get existing JIRA tickets
    jira_keys = {ticket.jira_key for ticket in workspace.jira_tickets}

    # Discover agents related to JIRA tickets
    if jira_keys:
        for jira_key in jira_keys:
            result = await db.execute(
                select(Agent).where(Agent.jira_key == jira_key)
            )
            agents = result.scalars().all()

            for agent in agents:
                # Check if already in workspace
                existing = any(wa.agent_id == agent.id for wa in workspace.agents)
                if not existing:
                    await add_agent(db, workspace_id, agent.id, linked_jira_keys=[jira_key])
                    discovered["agents"] += 1

    # Discover branches from agents
    existing_agent_ids = {wa.agent_id for wa in workspace.agents}
    if existing_agent_ids:
        result = await db.execute(
            select(Agent).where(Agent.id.in_(existing_agent_ids))
        )
        agents = result.scalars().all()

        for agent in agents:
            if agent.git_branch:
                # Check if branch already in workspace
                existing_branch = any(
                    branch.branch_name == agent.git_branch for branch in workspace.branches
                )
                if not existing_branch:
                    # Extract JIRA key from branch name
                    related_jira = []
                    match = _JIRA_RE.search(agent.git_branch)
                    if match:
                        related_jira.append(match.group(1).upper())

                    await add_branch(
                        db,
                        workspace_id,
                        agent.git_branch,
                        worktree_path=agent.worktree_path,
                        related_jira_keys=related_jira if related_jira else None,
                    )
                    discovered["branches"] += 1

    # Discover JIRA tickets from branch names
    for branch in workspace.branches:
        match = _JIRA_RE.search(branch.branch_name)
        if match:
            jira_key = match.group(1).upper()
            if jira_key not in jira_keys:
                await add_jira_ticket(db, workspace_id, jira_key, is_primary=False)
                jira_keys.add(jira_key)
                discovered["jira_tickets"] += 1

    return discovered


# Helper Functions

async def _infer_project(db: AsyncSession, created_from_type: str, created_from_id: str) -> str:
    """Infer project from resource type and ID."""
    if created_from_type == "jira":
        # Extract project from JIRA key (e.g., COMPUTE-1234 → compute)
        match = re.match(r"([A-Z]+)-\d+", created_from_id, re.IGNORECASE)
        if match:
            project_prefix = match.group(1).lower()
            # Map common prefixes
            mapping = {
                "compute": "wx",  # Default compute to wx
                "wx": "wx",
                "g4": "g4",
                "jobs": "jobs",
                "temporal": "temporal",
            }
            return mapping.get(project_prefix, "wx")

    elif created_from_type == "agent":
        # Get agent and use its project
        result = await db.execute(
            select(Agent).where(Agent.id == uuid.UUID(created_from_id))
        )
        agent = result.scalar_one_or_none()
        if agent and agent.project:
            return agent.project

    # Default fallback
    return "wx"


async def _generate_title(db: AsyncSession, created_from_type: str, created_from_id: str) -> str:
    """Generate workspace title from resource type and ID."""
    if created_from_type == "jira":
        return f"Workspace for {created_from_id}"

    elif created_from_type == "agent":
        result = await db.execute(
            select(Agent).where(Agent.id == uuid.UUID(created_from_id))
        )
        agent = result.scalar_one_or_none()
        if agent:
            if agent.title:
                return f"Workspace: {agent.title}"
            elif agent.first_prompt:
                # Use first 50 chars of first prompt
                return f"Workspace: {agent.first_prompt[:50]}..."

    return f"Workspace ({created_from_type})"


async def _touch_workspace(db: AsyncSession, workspace_id: uuid.UUID) -> None:
    """Update workspace last_active_at timestamp."""
    workspace = await db.get(Workspace, workspace_id)
    if workspace:
        workspace.last_active_at = datetime.now(timezone.utc)
