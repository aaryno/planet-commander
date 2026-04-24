"""Temporal Command Center API router.

Aggregates data from Slack, JIRA, GitLab, Grafana, and key inventory
into a unified dashboard view.
"""

import asyncio
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.services.temporal_keys_service import get_key_health
from app.services.temporal_slack_service import (
    get_unanswered, get_sentiment, get_channel_summary, get_raw_messages,
    TEMPORAL_CHANNELS,
)
from app.services.temporal_jira_service import get_temporal_tickets
from app.services.temporal_gitlab_service import get_open_mrs
from app.services.temporal_metrics_service import get_performance, get_usage
from app.services.temporal_tenants_service import get_tenants
from app.services.process_manager import process_manager
from app.services.slack_service import sync_channels

router = APIRouter()
logger = logging.getLogger(__name__)

# Server-side summary cache for temporal slack
_summary_cache: dict[str, dict] = {}


@router.get("/keys")
async def key_health():
    """API key expiration status for all tenants."""
    return get_key_health()


@router.get("/slack/unanswered")
async def unanswered_slack(days: int = 7, channels: str | None = None):
    """Unanswered questions in Temporal Slack channels."""
    channel_list = channels.split(",") if channels else None
    return get_unanswered(days, channel_list)


@router.get("/slack/summary")
async def slack_summary(days: int = 7):
    """Per-channel summary with message counts and active users."""
    return get_channel_summary(days)


@router.get("/slack/sentiment")
async def slack_sentiment(days: int = 7):
    """Keyword-based sentiment analysis for Temporal Slack channels."""
    return get_sentiment(days)


@router.get("/jira/tickets")
async def jira_tickets():
    """Open Temporal-related JIRA tickets."""
    return await get_temporal_tickets()


@router.get("/mrs")
async def open_mrs():
    """Open MRs and pipeline status for temporalio-cloud."""
    return await get_open_mrs()


@router.get("/metrics/performance")
async def performance_metrics():
    """Temporal Cloud performance metrics."""
    return await get_performance()


@router.get("/metrics/usage")
async def usage_metrics(period: str = "30d"):
    """Temporal Cloud usage and cost metrics."""
    return await get_usage(period)


@router.get("/tenants")
async def tenants():
    """Tenant/team data with users, namespaces, and metadata."""
    return get_tenants()


@router.post("/slack/sync")
async def temporal_slack_sync():
    """Sync Temporal Slack channels (temporal-dev, temporal-users)."""
    result = await sync_channels(TEMPORAL_CHANNELS)
    return result


class TemporalSummarizeRequest(BaseModel):
    days: int = 7
    channels: list[str] | None = None


@router.get("/slack/ai-summary")
async def get_cached_summary(
    channels: str | None = None,
):
    """Return cached AI summary if available."""
    channel_list = channels.split(",") if channels else None
    cache_key = _summary_key(channel_list)
    cached = _summary_cache.get(cache_key)
    if cached:
        return {
            "summary": cached["summary"],
            "channels": cached.get("channels"),
            "status": "ready",
            "cached_at": cached["timestamp"],
        }
    in_progress_key = f"_in_progress:{cache_key}"
    if _summary_cache.get(in_progress_key):
        return {"status": "in_progress", "channels": channel_list or TEMPORAL_CHANNELS}
    return {"status": "none", "channels": channel_list or TEMPORAL_CHANNELS}


@router.post("/slack/ai-summary")
async def summarize_temporal_slack(request: TemporalSummarizeRequest):
    """Generate an AI summary of Temporal Slack channels using Claude.

    Uses auto-expanded date range so stale data still gets summarized.
    Respects channel filter (one or both channels).
    """
    channel_list = request.channels
    cache_key = _summary_key(channel_list)
    in_progress_key = f"_in_progress:{cache_key}"

    content = get_raw_messages(request.days, channel_list)
    if not content.strip():
        return {
            "summary": "No messages found in the selected channels. Try syncing first.",
            "status": "ready",
            "channels": channel_list or TEMPORAL_CHANNELS,
        }

    _summary_cache[in_progress_key] = True

    # Truncate to avoid exceeding context limits
    max_chars = 100_000
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n[... truncated due to length ...]"

    selected = ", ".join(f"#{c}" for c in (channel_list or TEMPORAL_CHANNELS))
    prompt = (
        f"Summarize the following Slack messages from the Temporal channels ({selected}).\n\n"
        "Group by channel. For each channel, highlight:\n"
        "- Key topics and discussions\n"
        "- Questions asked and whether they were answered\n"
        "- Decisions made\n"
        "- Action items or follow-ups\n"
        "- Notable announcements or alerts\n\n"
        "Be concise but comprehensive. Use markdown formatting with channel names as headers.\n"
        "Skip bot messages that are purely automated notifications unless they indicate something important.\n\n"
        "---\n\n"
        f"{content}"
    )

    session_id = str(uuid.uuid4())
    captured_parts: list[str] = []

    async def capture_broadcast(json_str: str):
        import json
        try:
            data = json.loads(json_str)
            if data.get("type") == "response" and data.get("content"):
                captured_parts.append(data["content"])
        except Exception:
            pass

    try:
        session = await process_manager.spawn(
            session_id=session_id,
            initial_prompt=prompt,
        )
        session.subscribe_stdout(capture_broadcast)
    except Exception as e:
        _summary_cache.pop(in_progress_key, None)
        logger.error(f"Failed to spawn summarize agent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to spawn summarizer: {e}")

    # Wait for the turn to complete (max 60s)
    for _ in range(120):
        await asyncio.sleep(0.5)
        if not session.is_processing:
            break

    session.unsubscribe_stdout(capture_broadcast)

    summary_text = "\n\n".join(captured_parts) if captured_parts else None

    # Fallback: read from JSONL
    if not summary_text:
        from app.services.session_reader import parse_chat_history, SessionEntry
        from app.config import settings

        for project_dir in settings.claude_projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            candidate = project_dir / f"{session_id}.jsonl"
            if candidate.exists() and candidate.is_file():
                entry = SessionEntry(
                    session_id=session_id,
                    project_dir_name=project_dir.name,
                    full_path=str(candidate),
                )
                messages = parse_chat_history(entry, expand=False)
                for msg in reversed(messages):
                    if msg.role == "assistant":
                        summary_text = msg.summary or msg.content
                        break
                break

    if not summary_text:
        summary_text = "Summary generation completed but no output was captured."

    used_channels = channel_list or TEMPORAL_CHANNELS
    _summary_cache[cache_key] = {
        "summary": summary_text,
        "channels": used_channels,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _summary_cache.pop(in_progress_key, None)

    await process_manager.terminate(session_id)

    return {
        "summary": summary_text,
        "channels": used_channels,
        "status": "ready",
    }


def _summary_key(channels: list[str] | None) -> str:
    """Generate a cache key for a channel combination."""
    if not channels:
        return "all"
    return ",".join(sorted(channels))
