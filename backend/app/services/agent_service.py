"""Agent lifecycle management - process detection, sync, status."""

import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent import Agent
from app.models.label import Label
from app.services.session_reader import SessionEntry, discover_sessions, get_session_stats, map_project
from app.services.process_cache import process_cache

logger = logging.getLogger(__name__)

# In-memory stats cache: key = (session_id, last_active_at_iso), value = stats dict
_stats_cache: dict[tuple[str, str], dict] = {}

# JIRA ticket pattern — matches all known Planet JIRA projects
_JIRA_RE = re.compile(
    r"\b((?:COMPUTE|PLTFRMOPS|PRODISSUE|PE|EXPLORER|MOSAIC|IMAGERY|DATA|INFRA|OPS|PLATFORM)-\d+)\b",
    re.IGNORECASE,
)


async def update_agent_statuses_from_processes(db: AsyncSession) -> int:
    """Update agent statuses based on running Claude Code processes.

    Live = has running process with matching session ID
    Dead = no running process (or time-based fallback if modified recently)

    Note: Process information comes from process_cache, populated by
    a host-side script (since Docker can't see macOS host processes).
    """
    processes = process_cache.get_all()
    session_to_pid = {p.session_id: p.pid for p in processes}

    # Get all agents
    result = await db.execute(select(Agent))
    agents = result.scalars().all()

    updated = 0
    for agent in agents:
        if not agent.claude_session_id:
            continue

        old_status = agent.status
        has_process = agent.claude_session_id in session_to_pid

        if has_process:
            # Has running process = live
            new_status = "live"
        else:
            # No process - check last activity for idle vs dead
            new_status = _infer_status(agent.last_active_at)

        if new_status != old_status:
            agent.status = new_status
            updated += 1

    if updated > 0:
        await db.commit()

    logger.info(
        "Updated %d agent statuses (%d live processes found)",
        updated,
        len(processes),
    )
    return updated


async def sync_agents(db: AsyncSession) -> dict:
    """Discover all Claude Code sessions and upsert into the database."""
    sessions = discover_sessions()
    new_count = 0
    updated_count = 0

    # Get project labels for auto-labeling
    project_labels = {}
    label_result = await db.execute(
        select(Label).where(Label.category == "project")
    )
    for label in label_result.scalars():
        project_labels[label.name] = label

    for session in sessions:
        if session.is_sidechain:
            continue

        project = map_project(session.project_dir_name)

        # Check if agent already exists
        result = await db.execute(
            select(Agent).where(Agent.claude_session_id == session.session_id)
        )
        agent = result.scalar_one_or_none()

        # Parse timestamps
        created_at = _parse_ts(session.created)
        modified_at = _parse_ts(session.modified)

        # Clean up first_prompt for display
        title = _clean_title(session.first_prompt)

        # Infer status from last activity (simple heuristic until we have process detection)
        status = _infer_status(modified_at)

        # Extract JIRA key from prompt, title, and branch
        jira_key = _extract_jira_key(session.first_prompt, session.git_branch)

        if agent is None:
            agent = Agent(
                claude_session_id=session.session_id,
                claude_project_path=session.project_dir_name,
                project=project,
                status=status,
                title=title,
                first_prompt=session.first_prompt,
                working_directory=session.project_path,
                git_branch=session.git_branch or None,
                message_count=session.message_count,
                created_at=created_at,
                last_active_at=modified_at,
                jira_key=jira_key,
            )
            db.add(agent)
            new_count += 1
        else:
            if agent.managed_by != "dashboard":
                agent.title = title
            agent.first_prompt = session.first_prompt
            agent.message_count = session.message_count
            agent.last_active_at = modified_at
            agent.git_branch = session.git_branch or agent.git_branch
            agent.working_directory = session.project_path or agent.working_directory
            agent.status = status
            # Backfill JIRA key if not already set
            if not agent.jira_key and jira_key:
                agent.jira_key = jira_key
            # Backfill files_changed from session JSONL
            if not agent.files_changed:
                from app.services.session_reader import extract_files_changed
                files = extract_files_changed(session)
                if files:
                    agent.files_changed = files
            # Backfill MR references from session JSONL
            if not agent.mr_references:
                from app.services.session_reader import extract_mr_references
                mrs = extract_mr_references(session)
                if mrs:
                    agent.mr_references = mrs
            updated_count += 1

    await db.commit()

    # Enrichment pass: backfill JIRA keys from MR references for agents that still have no key
    enriched = await _enrich_jira_keys_from_mrs(db)
    if enriched > 0:
        await db.commit()

    total = new_count + updated_count
    logger.info("Agent sync complete: %d total (%d new, %d updated, %d enriched)", total, new_count, updated_count, enriched)
    return {"synced": total, "new": new_count, "updated": updated_count, "enriched": enriched}


async def get_agents(
    db: AsyncSession,
    project: str | None = None,
    status: str | None = None,
    include_hidden: bool = False,
) -> list[dict]:
    """List agents with optional filters, ordered by last active."""
    query = select(Agent).order_by(Agent.last_active_at.desc().nullslast())

    if not include_hidden:
        query = query.where(Agent.hidden_at.is_(None))
    if project:
        query = query.where(Agent.project == project)
    if status:
        query = query.where(Agent.status == status)

    result = await db.execute(query)
    agents = result.scalars().all()

    return [_agent_to_dict(a) for a in agents]


async def get_agent_by_id(db: AsyncSession, agent_id: str) -> dict | None:
    """Get a single agent by UUID."""
    from uuid import UUID
    try:
        uid = UUID(agent_id)
    except ValueError:
        return None

    result = await db.execute(select(Agent).where(Agent.id == uid))
    agent = result.scalar_one_or_none()
    if agent is None:
        return None
    return _agent_to_dict(agent)


async def get_agent_session_info(db: AsyncSession, agent_id: str) -> SessionEntry | None:
    """Get the SessionEntry info needed to read chat history."""
    from uuid import UUID
    try:
        uid = UUID(agent_id)
    except ValueError:
        return None

    result = await db.execute(select(Agent).where(Agent.id == uid))
    agent = result.scalar_one_or_none()
    if agent is None:
        return None

    return SessionEntry(
        session_id=agent.claude_session_id or "",
        full_path="",
        first_prompt=agent.first_prompt or "",
        message_count=agent.message_count,
        created=agent.created_at.isoformat() if agent.created_at else "",
        modified=agent.last_active_at.isoformat() if agent.last_active_at else "",
        git_branch=agent.git_branch or "",
        project_path=agent.working_directory or "",
        project_dir_name=agent.claude_project_path or "",
    )


def _agent_to_dict(agent: Agent) -> dict:
    """Convert Agent model to API response dict."""
    # Get cached stats or compute
    stats = _get_cached_stats(agent)

    # Use stored JIRA key if available, otherwise extract from first_prompt or git_branch
    jira_key = agent.jira_key or _extract_jira_key(agent.first_prompt, agent.git_branch)

    return {
        "id": str(agent.id),
        "claude_session_id": agent.claude_session_id,
        "project": agent.project,
        "status": agent.status,
        "title": agent.title,
        "first_prompt": agent.first_prompt,
        "git_branch": agent.git_branch if agent.git_branch not in (None, "", "HEAD", "main", "master") else None,
        "worktree_path": agent.worktree_path,
        "dev_env_url": agent.dev_env_url,
        "message_count": agent.message_count,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "last_active_at": agent.last_active_at.isoformat() if agent.last_active_at else None,
        "working_directory": agent.working_directory,
        "managed_by": agent.managed_by,
        "hidden_at": agent.hidden_at.isoformat() if agent.hidden_at else None,
        "total_tokens": stats.get("total_tokens", 0),
        "num_prompts": stats.get("num_prompts", 0),
        "jira_key": jira_key,
        "labels": [],  # TODO: eager load labels in Phase 3
        "artifacts": [],  # TODO: eager load artifacts
        "files_changed": agent.files_changed or {},
        "mr_references": agent.mr_references or [],
    }


def _get_cached_stats(agent: Agent) -> dict:
    """Get token stats with caching based on session_id + last_active_at."""
    if not agent.claude_session_id:
        return {"total_tokens": 0, "num_prompts": 0}

    last_active_key = agent.last_active_at.isoformat() if agent.last_active_at else ""
    cache_key = (agent.claude_session_id, last_active_key)

    if cache_key in _stats_cache:
        return _stats_cache[cache_key]

    session_entry = SessionEntry(
        session_id=agent.claude_session_id,
        full_path="",
        first_prompt=agent.first_prompt or "",
        message_count=agent.message_count,
        created=agent.created_at.isoformat() if agent.created_at else "",
        modified=last_active_key,
        git_branch=agent.git_branch or "",
        project_path=agent.working_directory or "",
        project_dir_name=agent.claude_project_path or "",
    )

    stats = get_session_stats(session_entry)
    _stats_cache[cache_key] = stats
    return stats


_MR_IID_RE = re.compile(r"MR\s*!(\d+)", re.IGNORECASE)


async def _enrich_jira_keys_from_mrs(db: AsyncSession) -> int:
    """Backfill JIRA keys for agents that reference MRs but have no JIRA key.

    Looks for patterns like 'MR !1271' in the title/first_prompt, then looks up
    the MR's jira_keys or source_branch to extract the JIRA key.
    """
    from app.models.gitlab_merge_request import GitLabMergeRequest as GitLabMR

    # Find agents without JIRA keys
    result = await db.execute(
        select(Agent).where(Agent.jira_key.is_(None))
    )
    agents_without_jira = result.scalars().all()
    enriched = 0

    for agent in agents_without_jira:
        # Check if title or prompt mentions an MR
        for text in (agent.title, agent.first_prompt):
            if not text:
                continue
            mr_match = _MR_IID_RE.search(text)
            if mr_match:
                mr_iid = int(mr_match.group(1))
                # Look up the MR in the database
                mr_result = await db.execute(
                    select(GitLabMR).where(GitLabMR.external_mr_id == mr_iid)
                )
                mr = mr_result.scalar_one_or_none()
                if mr:
                    # Try jira_keys field first
                    if mr.jira_keys and isinstance(mr.jira_keys, list) and len(mr.jira_keys) > 0:
                        agent.jira_key = mr.jira_keys[0]
                        enriched += 1
                        break
                    # Fall back to extracting from source branch
                    jira_key = _extract_jira_key(mr.source_branch, mr.title)
                    if jira_key:
                        agent.jira_key = jira_key
                        enriched += 1
                        break

    if enriched:
        logger.info("Enriched %d agents with JIRA keys from MR references", enriched)
    return enriched


def _extract_jira_key(first_prompt: str | None, git_branch: str | None) -> str | None:
    """Extract JIRA ticket key from first prompt or git branch."""
    for text in (first_prompt, git_branch):
        if text:
            match = _JIRA_RE.search(text)
            if match:
                return match.group(1).upper()
    return None


def _clean_title(first_prompt: str, max_len: int = 120) -> str:
    """Clean up first prompt for use as a title."""
    if not first_prompt:
        return "(empty session)"

    import re

    text = first_prompt

    # Strip Commander context preambles (may be truncated without closing ])
    text = re.sub(r"\[Commander:[^\]]*\]?\s*", "", text, flags=re.DOTALL)
    text = re.sub(r"\[Project Context:[^\]]*\]?\s*", "", text, flags=re.DOTALL)
    text = re.sub(r"\[JIRA Ticket:[^\]]*\]?\s*", "", text, flags=re.DOTALL)
    text = re.sub(r"\[MR Context:[^\]]*\]?\s*", "", text, flags=re.DOTALL)
    text = re.sub(r"\[Slack Context:[^\]]*\]?\s*", "", text, flags=re.DOTALL)
    text = re.sub(r"\[Context:[^\]]*\]?\s*", "", text, flags=re.DOTALL)

    # Strip all XML-style tags and truncation markers
    text = re.sub(r"<[^>]*>?", " ", text)  # handles <tag> and truncated <…

    # Strip Claude Code IDE-injected context sentences
    text = re.sub(r"The user opened the file\s+\S+\s*(in the IDE\.)?\s*", "", text)
    text = re.sub(r"The user is currently viewing\s+.*?(?:\.\s*|$)", "", text)
    text = re.sub(r"The user selected.*?in the IDE\.\s*", "", text)
    text = re.sub(r"This is the context.*?(?:\.\s*|$)", "", text)
    text = re.sub(r"This may or may not be related to the current task\.?\s*", "", text)
    text = re.sub(r"tool output\s*\(\w+\)\s*(in the IDE\.)?\s*", "", text)
    text = re.sub(r"output\s*\(\w+\)\s*(in the IDE\.)?\s*", "", text)
    text = re.sub(r"/temp/readonly/\S+\s*", "", text)
    text = re.sub(r"Bash\s+", "", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Take first line
    text = text.split("\n")[0].strip()

    if not text:
        return "(IDE action)"

    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def _infer_status(last_active: datetime | None) -> str:
    """Infer agent status from last activity time.

    Simple heuristic until we have process detection:
    - live: active within last 5 minutes
    - idle: active within last hour
    - dead: older than 1 hour
    """
    if not last_active:
        return "dead"

    now = datetime.now(timezone.utc)
    delta = now - last_active

    if delta.total_seconds() < 300:  # 5 minutes
        return "live"
    elif delta.total_seconds() < 3600:  # 1 hour
        return "idle"
    else:
        return "dead"


def _parse_ts(ts_str: str) -> datetime | None:
    """Parse an ISO timestamp string."""
    if not ts_str:
        return None
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None
