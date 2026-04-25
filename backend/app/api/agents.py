import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from sqlalchemy import select
from app.database import get_db, async_session
from app.services.agent_service import (
    get_agent_by_id,
    get_agent_session_info,
    get_agents,
    sync_agents,
)
from app.services.session_reader import parse_chat_history
from app.services.worktree_service import enrich_agents_with_worktrees
from app.services.process_manager import process_manager

router = APIRouter()


def _inject_jira_context(message: str, agent: dict) -> str:
    """Inject JIRA context into message if agent has a JIRA key."""
    jira_key = agent.get("jira_key")
    if not jira_key:
        return message

    context = f"[Context: You are working on JIRA ticket {jira_key}. You can view it at https://hello.planet.com/jira/browse/{jira_key}]\n\n"
    return context + message


async def _inject_slack_context(message: str, agent: dict, db: AsyncSession) -> str:
    """Inject queued Slack context into agent messages.

    Drains the agent's context queue and prepends all pending
    Slack updates as a context block.
    """
    agent_id = agent.get("id")
    if not agent_id:
        return message

    try:
        from app.services.agent_context_queue import AgentContextQueueService

        service = AgentContextQueueService(db)
        items = await service.drain(agent_id, max_items=20)

        if not items:
            return message

        lines = [f"[Slack Context: {len(items)} new messages since your last turn]", ""]

        current_channel = None
        for item in items:
            if item.channel_name != current_channel:
                current_channel = item.channel_name
                lines.append(f"#{current_channel}:")

            age = _format_age(item.created_at)
            author = item.author or "unknown"
            content = item.content
            if len(content) > 300:
                content = content[:300] + "..."

            priority_marker = " [URGENT]" if item.priority == "high" else ""
            lines.append(f"  {author} ({age}){priority_marker}: {content}")

            if item.permalink:
                lines.append(f"    → {item.permalink}")

        lines.append("")
        context = "\n".join(lines) + "\n"
        return context + message

    except Exception as e:
        logger.warning(f"Failed to inject Slack context for agent {agent_id}: {e}")
        return message


def _format_age(dt: datetime) -> str:
    """Format a datetime as a human-readable age string."""
    if not dt:
        return ""
    delta = datetime.now(timezone.utc) - dt
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return f"{int(delta.total_seconds() / 60)}m ago"
    if hours < 24:
        return f"{int(hours)}h ago"
    return f"{int(hours / 24)}d ago"


class ChatMessage(BaseModel):
    message: str
    model: str | None = None  # claude model: opus, sonnet, haiku
    source: str | None = None  # UI source: sidebar, amv, mr-review, agents


def _inject_commander_context(message: str, agent: dict, source: str | None = None) -> str:
    """Inject Commander environment context so the agent knows where it's running."""
    source_labels = {
        "sidebar": "JIRA sidebar workspace",
        "amv": "Agent Multi-View",
        "mr-review": "MR Review panel",
        "agents": "Agents page",
    }
    view_label = source_labels.get(source or "", "dashboard")
    project = agent.get("project", "unknown")

    context = (
        f"[Commander: You are running inside Planet Commander ({view_label}). "
        f"Project: {project}. "
        f"When creating artifacts, save as markdown files in ~/claude/projects/ or ~/claude/artifacts/ — "
        f"NEVER use /tmp/ or HTML files. "
        f"Provide file paths as full absolute paths so they render as clickable GitLab links.]\n\n"
    )
    return context + message


@router.get("")
async def list_agents(
    project: str | None = None,
    status: str | None = None,
    label: str | None = None,
    include_hidden: bool = False,
    db: AsyncSession = Depends(get_db),
):
    agents = await get_agents(db, project=project, status=status, include_hidden=include_hidden)
    return {"agents": agents, "total": len(agents)}


@router.get("/search")
async def search_agents(
    q: str = Query(...),
    jira_key: str | None = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Search agents by query string or JIRA key."""
    from app.models.agent import Agent as AgentModel

    query = select(AgentModel)

    if jira_key:
        # Search by exact JIRA key match
        query = query.where(AgentModel.jira_key == jira_key.upper())
    else:
        # Search by title or first_prompt
        search_term = f"%{q}%"
        query = query.where(
            (AgentModel.title.ilike(search_term)) |
            (AgentModel.first_prompt.ilike(search_term))
        )

    # Order by most recent first
    query = query.order_by(AgentModel.last_active_at.desc())

    result = await db.execute(query)
    agents = result.scalars().all()

    # Convert to dicts
    from app.services.agent_service import _agent_to_dict
    agent_dicts = [await _agent_to_dict(agent, db) for agent in agents]

    return {"results": agent_dicts, "total": len(agent_dicts)}


@router.get("/by-jira/{jira_key}")
async def agents_by_jira_key(jira_key: str, db: AsyncSession = Depends(get_db)):
    """Find agents associated with a JIRA key."""
    from app.models.agent import Agent as AgentModel
    from app.services.agent_service import _agent_to_dict

    try:
        result = await db.execute(
            select(AgentModel)
            .where(AgentModel.jira_key == jira_key.upper())
            .order_by(AgentModel.created_at.desc())
        )
        agents = result.scalars().all()
        agent_dicts = [_agent_to_dict(a) for a in agents]
        return {"agents": agent_dicts, "total": len(agent_dicts), "jira_key": jira_key}
    except Exception as e:
        logger.error(f"Failed to find agents for JIRA key {jira_key}: {e}")
        return {"agents": [], "total": 0, "jira_key": jira_key}


@router.post("/sync")
async def sync_agents_endpoint(db: AsyncSession = Depends(get_db)):
    result = await sync_agents(db)
    worktree_matches = await enrich_agents_with_worktrees(db)
    result["worktree_matches"] = worktree_matches
    return result


@router.get("/{agent_id}")
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = await get_agent_by_id(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.get("/{agent_id}/history")
async def get_agent_history(
    agent_id: str,
    expand: bool = False,
    db: AsyncSession = Depends(get_db),
):
    session_info = await get_agent_session_info(db, agent_id)
    if session_info is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    messages = parse_chat_history(session_info, expand=expand)
    return {
        "messages": [
            {
                "role": m.role,
                "timestamp": m.timestamp,
                "content": m.content,
                "summary": m.summary,
                "tool_calls": m.tool_calls,
                "tool_call_count": m.tool_call_count,
                "has_thinking": m.has_thinking,
                "thinking": m.thinking,
                "model": m.model,
                "artifacts": m.artifacts if m.artifacts else None,
            }
            for m in messages
        ]
    }


def _clean_prompt(text: str) -> str:
    """Strip system tags, task notifications, and XML markup from user messages."""
    if not text:
        return text
    # Remove <system-reminder>...</system-reminder> blocks
    text = re.sub(r'<system-reminder>.*?</system-reminder>', '', text, flags=re.DOTALL)
    # Remove <task-notification>...</task-notification> blocks
    text = re.sub(r'<task-notification>.*?</task-notification>', '', text, flags=re.DOTALL)
    # Remove <local-command-caveat>...</local-command-caveat> blocks
    text = re.sub(r'<local-command-caveat>.*?</local-command-caveat>', '', text, flags=re.DOTALL)
    # Remove <command-*>...</command-*> blocks
    text = re.sub(r'<command-\w+>.*?</command-\w+>', '', text, flags=re.DOTALL)
    # Remove <available-deferred-tools>...</available-deferred-tools>
    text = re.sub(r'<available-deferred-tools>.*?</available-deferred-tools>', '', text, flags=re.DOTALL)
    # Remove any remaining XML-like tags
    text = re.sub(r'<[a-z_-]+>.*?</[a-z_-]+>', '', text, flags=re.DOTALL)
    # Clean up excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


@router.get("/{agent_id}/last-prompt")
async def agent_last_prompt(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get the last user message from an agent's chat history."""
    session_info = await get_agent_session_info(db, agent_id)
    if session_info is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        messages = parse_chat_history(session_info, expand=False)
        # Find the last human/user message
        last_human = None
        for m in messages:
            if m.role == "user" and m.content:
                last_human = m

        if last_human is None:
            return {"content": None, "timestamp": None}

        # Strip system tags and task notifications
        content = _clean_prompt(last_human.content)
        truncated = len(content) > 500
        if truncated:
            content = content[:500]

        return {
            "content": content,
            "timestamp": last_human.timestamp,
            "truncated": truncated,
        }
    except Exception as e:
        logger.error(f"Failed to get last prompt for agent {agent_id}: {e}")
        return {"content": None, "timestamp": None}


@router.get("/{agent_id}/artifacts")
async def get_agent_artifacts(agent_id: str):
    return {"artifacts": []}


@router.get("/{agent_id}/artifact-content")
async def get_artifact_content(agent_id: str, path: str, raw: bool = False):
    """Read file content for an artifact. Path must be under allowed directories.

    If raw=true, returns plain text content directly (for opening in new tab).
    """
    from pathlib import Path as P
    from starlette.responses import Response

    resolved = P(path).expanduser().resolve()
    # Security: only allow paths under known safe directories
    home = P.home()
    allowed_prefixes = [
        home / "claude",
        home / "code",
        home / "workspaces",
        home / "tools",
    ]
    if not any(str(resolved).startswith(str(p)) for p in allowed_prefixes):
        raise HTTPException(403, "Path not in allowed directory")
    if not resolved.exists():
        raise HTTPException(404, "File not found")
    if not resolved.is_file():
        raise HTTPException(400, "Path is not a file")

    try:
        content = resolved.read_text(errors="replace")
    except Exception as e:
        raise HTTPException(500, f"Failed to read file: {e}")

    if raw:
        return Response(content=content, media_type="text/plain; charset=utf-8")

    suffix = resolved.suffix.lower()
    return {
        "path": str(resolved),
        "filename": resolved.name,
        "content": content,
        "language": suffix.lstrip(".") if suffix else "txt",
        "size": resolved.stat().st_size,
    }


@router.get("/{agent_id}/context-queue")
async def get_context_queue_status(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get pending context queue count for an agent."""
    from app.services.agent_context_queue import AgentContextQueueService
    service = AgentContextQueueService(db)
    count = await service.peek(agent_id)
    return {"pending_count": count, "agent_id": agent_id}


# --- Phase 3 agent actions ---


class SpawnAgentRequest(BaseModel):
    working_directory: str | None = None
    project: str | None = None
    initial_prompt: str | None = None
    jira_key: str | None = None
    worktree_path: str | None = None
    worktree_branch: str | None = None
    model: str | None = None
    source: str | None = None
    # Context source fields — tell the backend what the user was looking at
    mr_project: str | None = None
    mr_iid: int | None = None
    slack_channel: str | None = None
    slack_thread_ts: str | None = None
    slack_messages: list[dict] | None = None


@router.post("")
async def spawn_agent(request: SpawnAgentRequest, db: AsyncSession = Depends(get_db)):
    """Spawn a new Claude Code agent managed by the dashboard.

    Handles worktree creation automatically:
    - If worktree_path is set, uses it as working directory
    - If jira_key is set but no worktree, creates a worktree for the ticket
    - If neither, creates a randomly named worktree
    - working_directory override takes precedence over all above
    """
    import uuid
    from app.api.worktrees import PROJECT_REPO_MAP, CreateWorktreeRequest, create_worktree

    working_dir = request.working_directory
    git_branch = request.worktree_branch
    worktree_display = request.worktree_path

    # Auto-create worktree if no explicit working dir and project supports it
    if not working_dir and request.project and request.project in PROJECT_REPO_MAP:
        if request.worktree_path:
            # Selected an existing worktree - resolve ~ to home
            working_dir = request.worktree_path.replace("~", str(Path.home()))
        else:
            # Create a new worktree (named after JIRA key or random)
            wt_request = CreateWorktreeRequest(
                project=request.project,
                jira_key=request.jira_key,
                checkout_branch=request.worktree_branch,
            )
            wt_result = await create_worktree(wt_request)
            worktree_display = wt_result["path"]
            git_branch = wt_result["branch"]
            working_dir = worktree_display.replace("~", str(Path.home()))

    # Generate new session ID
    session_id = str(uuid.uuid4())

    # Build rich context preamble from all available sources
    initial_prompt = request.initial_prompt
    if initial_prompt:
        from app.services.context_packs import build_context_preamble
        from app.database import async_session
        async with async_session() as ctx_db:
            context_preamble = await build_context_preamble(
                project_key=request.project,
                jira_key=request.jira_key,
                mr_project=request.mr_project,
                mr_iid=request.mr_iid,
                slack_channel=request.slack_channel,
                slack_thread_ts=request.slack_thread_ts,
                slack_messages=request.slack_messages,
                source=request.source,
                db=ctx_db,
            )
        agent_stub = {"project": request.project or "unknown"}
        initial_prompt = _inject_commander_context(initial_prompt, agent_stub, request.source)
        if context_preamble:
            initial_prompt = context_preamble + "\n" + initial_prompt

    # Spawn agent session (initial_prompt runs as background task)
    try:
        agent_session = await process_manager.spawn(
            session_id=session_id,
            working_directory=working_dir,
            resume=False,
            initial_prompt=initial_prompt,
            model=request.model,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to spawn agent: {str(e)}")

    # Register in database as dashboard-managed
    from app.models.agent import Agent as AgentModel
    new_agent = AgentModel(
        claude_session_id=session_id,
        status="live",
        managed_by="dashboard",
        working_directory=agent_session.working_directory,
        title=(request.initial_prompt or "(dashboard agent)")[:120],
        first_prompt=request.initial_prompt,
        project=request.project,
        git_branch=git_branch,
        worktree_path=worktree_display,
        created_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc),
    )
    db.add(new_agent)
    await db.commit()
    await db.refresh(new_agent)

    # Backfill context if JIRA key provided
    if request.jira_key:
        try:
            from app.services.agent_context_queue import AgentContextQueueService
            queue_service = AgentContextQueueService(db)
            count = await queue_service.backfill_agent_context(str(new_agent.id))
            await db.commit()
            logger.info(f"Backfilled {count} context items for new agent {new_agent.id}")
        except Exception as e:
            logger.warning(f"Backfill failed for new agent: {e}")

    return {
        "id": str(new_agent.id),
        "session_id": session_id,
        "pid": agent_session.pid,
        "status": "live",
        "managed_by": "dashboard",
        "working_directory": agent_session.working_directory,
        "worktree_path": worktree_display,
        "git_branch": git_branch,
    }


class CartLaunchRequest(BaseModel):
    source_agent_ids: list[str]
    project: str = "general"
    initial_prompt: str | None = None
    jira_key: str | None = None
    worktree_path: str | None = None
    worktree_branch: str | None = None
    model: str | None = None
    context_preamble: str | None = None


@router.post("/cart-launch")
async def cart_launch(request: CartLaunchRequest, db: AsyncSession = Depends(get_db)):
    """Launch a new agent from merged context of multiple source agents.

    Creates EntityLinks (DERIVED_FROM) connecting the new agent to all sources,
    creates a MERGED WorkContext, and backfills the context queue.
    """
    import uuid as uuid_mod
    from app.api.worktrees import PROJECT_REPO_MAP, CreateWorktreeRequest, create_worktree
    from app.models.agent import Agent as AgentModel
    from app.models.entity_link import EntityLink, LinkType, LinkSourceType, LinkStatus

    # Validate source agents exist
    source_agents = []
    for aid in request.source_agent_ids:
        agent_dict = await get_agent_by_id(db, aid)
        if agent_dict is None:
            raise HTTPException(status_code=404, detail=f"Source agent {aid} not found")
        source_agents.append(agent_dict)

    # Build context preamble from summaries if not provided
    preamble = request.context_preamble
    if not preamble:
        parts = [f"You are continuing work from {len(source_agents)} previous agent sessions.\n"]
        for sa in source_agents:
            cached = _summary_cache.get(sa["id"])
            parts.append(f"## Session: {sa.get('title', 'Untitled')}")
            if cached and cached.get("short"):
                parts.append(cached["short"])
            elif cached and cached.get("phrase"):
                parts.append(cached["phrase"])
            else:
                parts.append("(No summary available)")
            if sa.get("jira_key"):
                parts.append(f"JIRA: {sa['jira_key']}")
            if sa.get("git_branch") and sa["git_branch"] != "HEAD":
                parts.append(f"Branch: {sa['git_branch']}")
            parts.append("")
        if request.initial_prompt:
            parts.append("## Your Task")
            parts.append(request.initial_prompt)
        preamble = "\n".join(parts)

    # Handle worktree
    working_dir = None
    git_branch = request.worktree_branch
    worktree_display = request.worktree_path

    if request.worktree_path:
        working_dir = request.worktree_path.replace("~", str(Path.home()))
    elif request.project and request.project in PROJECT_REPO_MAP:
        wt_request = CreateWorktreeRequest(
            project=request.project,
            jira_key=request.jira_key,
            checkout_branch=request.worktree_branch,
        )
        wt_result = await create_worktree(wt_request)
        worktree_display = wt_result["path"]
        git_branch = wt_result["branch"]
        working_dir = worktree_display.replace("~", str(Path.home()))

    # Spawn agent
    session_id = str(uuid_mod.uuid4())
    try:
        agent_session = await process_manager.spawn(
            session_id=session_id,
            working_directory=working_dir,
            resume=False,
            initial_prompt=preamble,
            model=request.model,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to spawn agent: {str(e)}")

    # Register in database
    title = f"Merged: {', '.join(sa.get('title', '?')[:30] for sa in source_agents[:3])}"
    if len(source_agents) > 3:
        title += f" +{len(source_agents) - 3}"
    new_agent = AgentModel(
        claude_session_id=session_id,
        status="live",
        managed_by="dashboard",
        working_directory=agent_session.working_directory,
        jira_key=request.jira_key,
        title=title[:120],
        first_prompt=preamble,
        project=request.project,
        git_branch=git_branch,
        worktree_path=worktree_display,
        created_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc),
    )
    db.add(new_agent)
    await db.flush()

    # Create EntityLinks: source agents -> new agent (DERIVED_FROM)
    links_created = 0
    for sa in source_agents:
        link = EntityLink(
            from_type="chat",
            from_id=sa["id"],
            to_type="chat",
            to_id=str(new_agent.id),
            link_type=LinkType.DERIVED_FROM,
            source_type=LinkSourceType.MANUAL,
            confidence_score=1.0,
            status=LinkStatus.CONFIRMED,
            link_metadata={"source": "context_cart", "cart_size": len(source_agents)},
        )
        db.add(link)
        links_created += 1

    await db.commit()
    await db.refresh(new_agent)

    # Backfill context queue
    backfill_count = 0
    if request.jira_key:
        try:
            from app.services.agent_context_queue import AgentContextQueueService
            queue_service = AgentContextQueueService(db)
            backfill_count = await queue_service.backfill_agent_context(str(new_agent.id))
            await db.commit()
            logger.info(f"Cart-launch: backfilled {backfill_count} items for agent {new_agent.id}")
        except Exception as e:
            logger.warning(f"Cart-launch: backfill failed for agent {new_agent.id}: {e}")

    logger.info(
        f"Cart-launch: spawned agent {new_agent.id} from {len(source_agents)} sources, "
        f"{links_created} links, {backfill_count} backfill items"
    )

    return {
        "id": str(new_agent.id),
        "session_id": session_id,
        "pid": agent_session.pid,
        "status": "live",
        "managed_by": "dashboard",
        "working_directory": agent_session.working_directory,
        "worktree_path": worktree_display,
        "git_branch": git_branch,
        "source_agent_count": len(source_agents),
        "entity_links_created": links_created,
    }


@router.delete("/{agent_id}")
async def kill_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Kill an agent session immediately."""
    agent = await get_agent_by_id(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    session_id = agent["claude_session_id"]
    if not session_id:
        raise HTTPException(status_code=400, detail="Agent has no session ID")

    session = process_manager.get(session_id)
    if not session:
        return {"status": "not_running", "message": "Agent is not running"}

    await process_manager.terminate(session_id)
    await sync_agents(db)

    return {"status": "killed", "session_id": session_id}


@router.post("/{agent_id}/stop")
async def stop_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Gracefully stop an agent process (SIGTERM with 5s timeout, then SIGKILL)."""
    agent = await get_agent_by_id(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    session_id = agent["claude_session_id"]
    if not session_id:
        raise HTTPException(status_code=400, detail="Agent has no session ID")

    session = process_manager.get(session_id)
    if not session:
        return {"status": "not_running", "message": "Agent is not running"}

    await process_manager.terminate(session_id)
    await sync_agents(db)

    return {"status": "stopped", "session_id": session_id}


@router.post("/{agent_id}/resume")
async def resume_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Resume a dead Claude Code session.

    Spawns a new Claude process with --resume flag to continue from where it left off.
    """
    # Get agent details
    agent = await get_agent_by_id(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    session_id = agent["claude_session_id"]
    if not session_id:
        raise HTTPException(status_code=400, detail="Agent has no session ID")

    # Check if already running
    existing = process_manager.get(session_id)
    if existing:
        return {
            "status": "already_running",
            "pid": existing.pid,
            "message": "Agent is already running",
        }

    # Resume the session (registers it, no process spawned until a message is sent)
    try:
        agent_session = await process_manager.spawn(
            session_id=session_id,
            working_directory=agent.get("working_directory"),
            resume=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume agent: {str(e)}")

    # Update agent to dashboard-managed
    from app.models.agent import Agent as AgentModel
    result = await db.execute(
        select(AgentModel).where(AgentModel.claude_session_id == session_id)
    )
    db_agent = result.scalar_one_or_none()
    if db_agent:
        db_agent.managed_by = "dashboard"
        db_agent.status = "live"
        await db.commit()

    return {
        "status": "resumed",
        "pid": agent_session.pid,
        "session_id": session_id,
        "managed_by": "dashboard",
    }


@router.post("/{agent_id}/chat")
async def chat_with_agent(
    agent_id: str,
    msg: ChatMessage,
    db: AsyncSession = Depends(get_db),
):
    """Send a message to a live Claude Code agent.

    For dashboard-managed agents (spawned via POST /agents), this sends messages
    directly via stdin pipe. For VS Code-managed agents, returns error.
    """
    # Verify agent exists
    agent = await get_agent_by_id(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    session_id = agent["claude_session_id"]
    if not session_id:
        raise HTTPException(status_code=400, detail="Agent has no session ID")

    # Get the managed session
    agent_session = process_manager.get(session_id)

    if not agent_session:
        # Auto-takeover: register the session so we can send messages via --resume
        try:
            agent_session = await process_manager.spawn(
                session_id=session_id,
                working_directory=agent.get("working_directory"),
                resume=True,
            )
            # Mark as dashboard-managed
            from app.models.agent import Agent as AgentModel
            result = await db.execute(
                select(AgentModel).where(AgentModel.claude_session_id == session_id)
            )
            db_agent = result.scalar_one_or_none()
            if db_agent:
                db_agent.managed_by = "dashboard"
                db_agent.status = "live"
                await db.commit()
            logger.info(f"Auto-takeover of session {session_id} for chat")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to take over session: {str(e)}")

    # Check if already processing
    if agent_session.is_processing:
        return {
            "sent": False,
            "pid": agent_session.pid,
            "session_id": session_id,
            "message": "Agent is currently processing a previous message. Please wait.",
        }

    # Inject Commander, JIRA, and Slack context
    message_with_context = _inject_commander_context(msg.message, agent, msg.source)
    message_with_context = _inject_jira_context(message_with_context, agent)
    message_with_context = await _inject_slack_context(message_with_context, agent, db)

    # Send message (spawns a per-turn process in background)
    success = await process_manager.send_message(session_id, message_with_context, model=msg.model)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to send message to agent")

    return {
        "sent": True,
        "pid": agent_session.pid,
        "session_id": session_id,
    }


@router.post("/{agent_id}/hide")
async def hide_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Hide an agent from the default list view."""
    from uuid import UUID
    from app.models.agent import Agent as AgentModel

    try:
        uid = UUID(agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent ID")

    result = await db.execute(select(AgentModel).where(AgentModel.id == uid))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.hidden_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "hidden", "agent_id": agent_id}


@router.post("/{agent_id}/unhide")
async def unhide_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Unhide an agent, making it visible in the default list again."""
    from uuid import UUID
    from app.models.agent import Agent as AgentModel

    try:
        uid = UUID(agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent ID")

    result = await db.execute(select(AgentModel).where(AgentModel.id == uid))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.hidden_at = None
    await db.commit()
    return {"status": "unhidden", "agent_id": agent_id}


class UpdateAgentRequest(BaseModel):
    jira_key: str | None = None
    project: str | None = None
    title: str | None = None
    worktree_path: str | None = None
    git_branch: str | None = None


@router.patch("/{agent_id}")
async def update_agent(
    agent_id: str,
    updates: UpdateAgentRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update agent metadata (JIRA key, project, title, etc)."""
    from uuid import UUID
    from app.models.agent import Agent as AgentModel

    try:
        uid = UUID(agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent ID")

    result = await db.execute(select(AgentModel).where(AgentModel.id == uid))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Update fields if provided
    if updates.jira_key is not None:
        agent.jira_key = updates.jira_key
    if updates.project is not None:
        agent.project = updates.project
    if updates.title is not None:
        agent.title = updates.title
    if updates.worktree_path is not None:
        agent.worktree_path = updates.worktree_path
    if updates.git_branch is not None:
        agent.git_branch = updates.git_branch

    await db.commit()
    await db.refresh(agent)

    # Backfill context queue if key fields changed
    updates_dict = updates.model_dump(exclude_unset=True)
    if "jira_key" in updates_dict or "git_branch" in updates_dict:
        try:
            from app.services.agent_context_queue import AgentContextQueueService
            queue_service = AgentContextQueueService(db)
            count = await queue_service.backfill_agent_context(agent_id)
            await db.commit()
            logger.info(f"Backfilled {count} context items for agent {agent_id}")
        except Exception as e:
            logger.warning(f"Backfill failed for agent {agent_id}: {e}")

    # Return updated agent
    updated = await get_agent_by_id(db, agent_id)
    return updated


@router.patch("/self")
async def update_self(
    updates: UpdateAgentRequest,
    session_id: str = Query(..., alias="session_id"),
    db: AsyncSession = Depends(get_db)
):
    """Allow agents to update their own metadata using session ID.

    This endpoint enables agents to self-register JIRA tickets and update their context.

    Usage from within an agent:
        curl -X PATCH "http://backend:9000/api/agents/self?session_id=$CLAUDE_SESSION_ID" \\
             -H "Content-Type: application/json" \\
             -d '{"jira_key": "COMPUTE-2152"}'
    """
    from app.models.agent import Agent as AgentModel

    # Find agent by session ID
    result = await db.execute(
        select(AgentModel).where(AgentModel.claude_session_id == session_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found for this session")

    # Update fields if provided
    if updates.jira_key is not None:
        agent.jira_key = updates.jira_key
    if updates.project is not None:
        agent.project = updates.project
    if updates.title is not None:
        agent.title = updates.title
    if updates.worktree_path is not None:
        agent.worktree_path = updates.worktree_path
    if updates.git_branch is not None:
        agent.git_branch = updates.git_branch

    await db.commit()
    await db.refresh(agent)

    # Backfill context queue if key fields changed
    updates_dict = updates.model_dump(exclude_unset=True)
    if "jira_key" in updates_dict or "git_branch" in updates_dict:
        try:
            from app.services.agent_context_queue import AgentContextQueueService
            queue_service = AgentContextQueueService(db)
            count = await queue_service.backfill_agent_context(str(agent.id))
            await db.commit()
            logger.info(f"Backfilled {count} context items for self-update agent {agent.id}")
        except Exception as e:
            logger.warning(f"Backfill failed for self-update agent {agent.id}: {e}")

    # Return updated agent
    updated = await get_agent_by_id(db, str(agent.id))
    return updated


# --- Agent Summary ---

# In-memory cache: agent_id -> {phrase, short, detailed, generated_at}
_summary_cache: dict[str, dict] = {}
# Track in-progress summarizations
_summary_in_progress: set[str] = set()


@router.get("/{agent_id}/summary")
async def get_agent_summary(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get cached summary for an agent, or return status."""
    if agent_id in _summary_in_progress:
        return {"status": "in_progress", "agent_id": agent_id}
    cached = _summary_cache.get(agent_id)
    if cached:
        return {"status": "ready", **cached}
    return {"status": "none", "agent_id": agent_id}


@router.post("/{agent_id}/summarize")
async def summarize_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Generate a 3-tier summary (phrase, short paragraph, detailed paragraph) of agent chat."""
    session_info = await get_agent_session_info(db, agent_id)
    if session_info is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    messages = parse_chat_history(session_info, expand=False)
    if not messages:
        return {
            "status": "ready",
            "agent_id": agent_id,
            "phrase": "Empty session",
            "short": "No messages in this session.",
            "detailed": "This agent session contains no messages.",
        }

    # Build conversation text for the prompt
    convo_parts = []
    for m in messages:
        if m.role == "user":
            convo_parts.append(f"User: {m.content or ''}")
        else:
            text = m.summary or ""
            if m.tool_call_count:
                text += f" [{m.tool_call_count} tool calls]"
            convo_parts.append(f"Assistant: {text}")

    convo_text = "\n".join(convo_parts)
    # Truncate to avoid context overflow
    max_chars = 80_000
    if len(convo_text) > max_chars:
        convo_text = convo_text[:max_chars] + "\n\n[... truncated ...]"

    prompt = (
        "Summarize the following Claude Code agent conversation at three levels of detail.\n\n"
        "Return your response as valid JSON with exactly these three keys:\n"
        '- "phrase": A single descriptive phrase (5-10 words max)\n'
        '- "short": A concise paragraph (2-3 sentences)\n'
        '- "detailed": A detailed paragraph (5-8 sentences covering key decisions, tools used, and outcomes)\n\n'
        "Return ONLY the JSON object, no markdown code fences.\n\n"
        "---\n\n"
        f"{convo_text}"
    )

    _summary_in_progress.add(agent_id)
    summary_session_id = str(uuid.uuid4())

    captured_parts: list[str] = []

    async def capture_broadcast(json_str: str):
        try:
            data = json.loads(json_str)
            if data.get("type") == "response" and data.get("content"):
                captured_parts.append(data["content"])
        except Exception:
            pass

    try:
        session = await process_manager.spawn(
            session_id=summary_session_id,
            initial_prompt=prompt,
        )
        session.subscribe_stdout(capture_broadcast)
    except Exception as e:
        _summary_in_progress.discard(agent_id)
        raise HTTPException(status_code=500, detail=f"Failed to spawn summarizer: {e}")

    # Wait for completion (max 60s)
    for _ in range(120):
        await asyncio.sleep(0.5)
        if not session.is_processing:
            break

    session.unsubscribe_stdout(capture_broadcast)
    _summary_in_progress.discard(agent_id)

    raw_text = "\n".join(captured_parts).strip()

    # Parse the JSON response
    result = {"phrase": "Summary unavailable", "short": "", "detailed": ""}
    if raw_text:
        # Try to extract JSON from the response
        try:
            # Handle potential markdown code fences
            cleaned = raw_text
            if "```" in cleaned:
                # Extract between code fences
                parts = cleaned.split("```")
                for part in parts:
                    stripped = part.strip()
                    if stripped.startswith("json"):
                        stripped = stripped[4:].strip()
                    if stripped.startswith("{"):
                        cleaned = stripped
                        break
            parsed = json.loads(cleaned)
            result = {
                "phrase": parsed.get("phrase", "Summary unavailable"),
                "short": parsed.get("short", ""),
                "detailed": parsed.get("detailed", ""),
            }
        except json.JSONDecodeError:
            # If JSON parsing fails, use the raw text as the detailed summary
            result["detailed"] = raw_text
            # Try to extract a phrase from the first line
            first_line = raw_text.split("\n")[0].strip()
            if len(first_line) < 80:
                result["phrase"] = first_line

    result["agent_id"] = agent_id
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    result["status"] = "ready"

    _summary_cache[agent_id] = result
    return result


@router.post("/{agent_id}/extract-urls")
async def extract_urls_from_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Extract URLs from chat messages and create EntityLinks on-demand."""
    from app.jobs.url_extraction import extract_urls_from_chat

    try:
        result = await extract_urls_from_chat(agent_id)
        return {
            "status": "success",
            "agent_id": agent_id,
            **result
        }
    except Exception as e:
        logger.error(f"Failed to extract URLs from agent {agent_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"URL extraction failed: {str(e)}"
        )


@router.post("/{agent_id}/labels")
async def update_agent_labels(agent_id: str):
    return {"status": "not implemented"}


@router.post("/{agent_id}/command")
async def send_agent_command(agent_id: str):
    return {"status": "not implemented"}


@router.delete("/{agent_id}/worktree")
async def delete_agent_worktree(agent_id: str):
    return {"status": "not implemented"}


# --- WebSocket for real-time chat ---


@router.websocket("/{agent_id}/ws")
async def agent_chat_websocket(websocket: WebSocket, agent_id: str):
    """WebSocket endpoint for real-time chat with a Claude Code agent.

    Client sends:
        {"type": "message", "content": "user message"}

    Server sends (JSON-encoded strings from process_manager broadcasts):
        {"type": "response", "content": "assistant text"}
        {"type": "status", "status": "processing|idle"}
        {"type": "error", "message": "error details"}
    """
    await websocket.accept()

    # Get agent session ID
    async with async_session() as db:
        agent = await get_agent_by_id(db, agent_id)
        if not agent:
            await websocket.send_json({"type": "error", "message": "Agent not found"})
            await websocket.close()
            return

        session_id = agent["claude_session_id"]
        if not session_id:
            await websocket.send_json({"type": "error", "message": "Agent has no session ID"})
            await websocket.close()
            return

    # Get the managed session (or spawn it if it's dashboard-managed but not active)
    agent_session = process_manager.get(session_id)

    if not agent_session:
        # If this is a dashboard-managed agent, auto-spawn the session
        if agent.get("managed_by") == "dashboard":
            try:
                agent_session = await process_manager.spawn(
                    session_id=session_id,
                    working_directory=agent.get("working_directory"),
                    resume=True,
                )
                logger.info(f"Auto-spawned dashboard session {session_id} for WebSocket")
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Failed to start session: {str(e)}",
                })
                await websocket.close()
                return
        else:
            await websocket.send_json({
                "type": "error",
                "message": "Agent is not under dashboard control. Use Resume to start it.",
            })
            await websocket.close()
            return

    # Send initial status
    status = "processing" if agent_session.is_processing else "idle"
    await websocket.send_json({"type": "status", "status": status})

    # Callback: process_manager broadcasts JSON-encoded strings
    async def on_broadcast(json_str: str):
        """Forward broadcast from process_manager to WebSocket client."""
        try:
            # The broadcast is already a JSON string, parse and forward
            data = json.loads(json_str)
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f"Error sending to WebSocket: {e}")

    agent_session.subscribe_stdout(on_broadcast)

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "message":
                message = data.get("content", "")
                source = data.get("source")  # UI view: sidebar, amv, mr-review, agents
                if message:
                    # Inject Commander, JIRA, and Slack context
                    message_with_context = _inject_commander_context(message, agent, source)
                    message_with_context = _inject_jira_context(message_with_context, agent)
                    async with async_session() as ws_db:
                        message_with_context = await _inject_slack_context(message_with_context, agent, ws_db)
                    success = await process_manager.send_message(session_id, message_with_context)
                    if not success:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Agent is busy or not available. Try again shortly.",
                        })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for agent {agent_id}")
    except Exception as e:
        logger.error(f"WebSocket error for agent {agent_id}: {e}")
    finally:
        agent_session.unsubscribe_stdout(on_broadcast)
