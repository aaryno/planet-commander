"""Slack API endpoints.

Provides team/channel metadata, message content, sync triggers,
and Claude-powered summarization with server-side caching.
"""

import asyncio
import uuid
import logging
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.slack_service import (
    TEAM_CHANNELS,
    get_message_stats,
    get_team_messages,
    get_teams,
    sync_channels,
    sync_channels_streaming,
    get_channel_messages,
    _channel_dir,
    _date_files_in_range,
)
from app.services.process_manager import process_manager

router = APIRouter()
logger = logging.getLogger(__name__)

# Server-side summary cache: key = f"{team}:{days}", value = {summary, timestamp, session_id}
_summary_cache: dict[str, dict] = {}


@router.get("/teams")
async def list_teams():
    """List all teams with their channel info."""
    teams = get_teams()
    return {"teams": teams}


@router.get("/messages")
async def get_messages(
    team: str = Query(..., description="Team ID (e.g. compute, wx, g4)"),
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
):
    """Get raw message content and stats for a team's channels."""
    if team not in TEAM_CHANNELS:
        raise HTTPException(status_code=404, detail=f"Unknown team: {team}")

    content = get_team_messages(team, days)
    stats = get_message_stats(team, days)
    return {"content": content, "stats": stats}


@router.get("/channel/{channel}/messages")
async def get_channel_messages_endpoint(
    channel: str,
    days: int = Query(7, ge=1, le=90),
):
    """Get messages for a single channel."""
    content = get_channel_messages(channel, days)
    if not content:
        raise HTTPException(status_code=404, detail=f"Channel not found or no messages: {channel}")
    return {"channel": channel, "content": content, "days": days}


@router.get("/channel/{channel}/details")
async def get_channel_details(channel: str):
    """Get detailed stats for a channel: earliest/latest messages, message counts."""
    import re

    channel_dir = _channel_dir(channel)
    if not channel_dir:
        raise HTTPException(status_code=404, detail=f"Channel not found: {channel}")

    # Get all message files
    all_files = sorted(channel_dir.glob("*.md"))
    if not all_files:
        return {
            "channel": channel,
            "earliest_date": None,
            "latest_date": None,
            "total_messages": 0,
            "last_day_count": 0,
            "last_week_avg": 0,
        }

    # Extract dates from filenames
    earliest_date = None
    latest_date = None

    for f in all_files:
        match = re.match(r"(\d{8})\.md$", f.name)
        if match:
            date_str = match.group(1)
            formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            if not earliest_date:
                earliest_date = formatted
            latest_date = formatted  # Since sorted, last one is latest

    # Count messages in last day
    last_day_count = 0
    if all_files:
        last_file = all_files[-1]
        content = last_file.read_text(errors="replace")
        msg_matches = re.findall(r"\*\*[^*]+\*\*\s+`\d{2}:\d{2}:\d{2}`", content)
        last_day_count = len(msg_matches)

    # Count messages in last week and calculate average
    last_week_files = _date_files_in_range(channel_dir, 7)
    last_week_count = 0
    for f in last_week_files:
        content = f.read_text(errors="replace")
        msg_matches = re.findall(r"\*\*[^*]+\*\*\s+`\d{2}:\d{2}:\d{2}`", content)
        last_week_count += len(msg_matches)

    last_week_avg = round(last_week_count / 7, 1) if last_week_files else 0

    # Total messages across all files
    total_messages = 0
    for f in all_files:
        content = f.read_text(errors="replace")
        msg_matches = re.findall(r"\*\*[^*]+\*\*\s+`\d{2}:\d{2}:\d{2}`", content)
        total_messages += len(msg_matches)

    return {
        "channel": channel,
        "earliest_date": earliest_date,
        "latest_date": latest_date,
        "total_messages": total_messages,
        "last_day_count": last_day_count,
        "last_week_avg": last_week_avg,
        "total_files": len(all_files),
    }


class SyncRequest(BaseModel):
    team: str


@router.post("/sync")
async def sync_team(request: SyncRequest):
    """Trigger sync-channel.py for all channels in a team."""
    if request.team not in TEAM_CHANNELS:
        raise HTTPException(status_code=404, detail=f"Unknown team: {request.team}")

    channels = TEAM_CHANNELS[request.team]["channels"]
    result = await sync_channels(channels)
    return result


@router.get("/sync-stream")
async def sync_team_stream(team: str = Query(...)):
    """Stream sync progress updates via Server-Sent Events."""
    if team not in TEAM_CHANNELS:
        raise HTTPException(status_code=404, detail=f"Unknown team: {team}")

    channels = TEAM_CHANNELS[team]["channels"]

    async def event_generator():
        """Generate SSE events for sync progress."""
        try:
            async for update in sync_channels_streaming(channels):
                # SSE format: "data: {json}\n\n"
                yield f"data: {json.dumps(update)}\n\n"
                await asyncio.sleep(0.1)  # Small delay for client processing
        except Exception as e:
            logger.error(f"Sync stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


class SummarizeRequest(BaseModel):
    team: str
    days: int = 7


@router.get("/latest-summary")
async def get_latest_summary(
    team: str = Query(...),
    days: int = Query(7, ge=1, le=90),
):
    """Return cached summary for a team if available."""
    cache_key = f"{team}:{days}"
    cached = _summary_cache.get(cache_key)
    if cached:
        return {
            "summary": cached["summary"],
            "session_id": cached.get("session_id"),
            "team": team,
            "days": days,
            "cached_at": cached["timestamp"],
            "status": "ready",
        }
    # Check if a summarization is in progress for this team
    in_progress_key = f"_in_progress:{team}:{days}"
    if _summary_cache.get(in_progress_key):
        return {"status": "in_progress", "team": team, "days": days}
    return {"status": "none", "team": team, "days": days}


@router.post("/summarize")
async def summarize_team(request: SummarizeRequest):
    """Spawn a Claude agent to summarize Slack messages.

    Reads messages, builds a prompt, runs claude -p, waits for completion,
    caches the result, and returns the summary text.
    """
    if request.team not in TEAM_CHANNELS:
        raise HTTPException(status_code=404, detail=f"Unknown team: {request.team}")

    team_info = TEAM_CHANNELS[request.team]

    try:
        content = get_team_messages(request.team, request.days)
    except Exception as e:
        logger.error(f"Failed to get team messages for {request.team}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to read messages: {str(e)}")

    cache_key = f"{request.team}:{request.days}"
    in_progress_key = f"_in_progress:{request.team}:{request.days}"

    if not content.strip():
        day_label = "day" if request.days == 1 else f"{request.days} days"
        return {
            "summary": f"No messages found for {team_info['label']} in the past {day_label}. Try a wider time range or sync new messages.",
            "session_id": None,
            "team": request.team,
            "days": request.days,
        }

    # Mark as in-progress
    _summary_cache[in_progress_key] = True

    # Truncate to avoid exceeding context limits (~100K chars ≈ ~25K tokens)
    max_chars = 100_000
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n[... truncated due to length ...]"

    prompt = (
        f"Summarize the following Slack messages from the {team_info['label']} team channels "
        f"over the past {request.days} day(s).\n\n"
        "Group by channel. For each channel, highlight:\n"
        "- Key topics and discussions\n"
        "- Decisions made\n"
        "- Action items or follow-ups\n"
        "- Notable announcements or alerts\n\n"
        "Be concise but comprehensive. Use markdown formatting with channel names as headers.\n"
        "Skip bot messages that are purely automated notifications unless they indicate something important.\n\n"
        "---\n\n"
        f"{content}"
    )

    session_id = str(uuid.uuid4())

    # Capture the summary from the broadcast
    captured_parts: list[str] = []

    async def capture_broadcast(json_str: str):
        import json
        try:
            data = json.loads(json_str)
            if data.get("type") == "response" and data.get("content"):
                captured_parts.append(data["content"])
        except Exception as e:
            logger.warning(f"Failed to parse broadcast JSON: {e}")

    try:
        session = await process_manager.spawn(
            session_id=session_id,
            initial_prompt=prompt,
        )
        # Subscribe to capture the response
        session.subscribe_stdout(capture_broadcast)
    except Exception as e:
        _summary_cache.pop(in_progress_key, None)
        logger.error(f"Failed to spawn summarize agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to spawn summarizer: {e}")

    # Wait for the turn to complete (with extended timeout for large summaries)
    max_wait_seconds = 120  # 2 minutes
    iterations = max_wait_seconds * 2  # 0.5s per iteration
    for i in range(iterations):
        await asyncio.sleep(0.5)
        if not session.is_processing:
            logger.info(f"Summarization completed after {i * 0.5}s")
            break
        if i % 20 == 0:  # Log every 10 seconds
            logger.info(f"Summarization still in progress... {i * 0.5}s elapsed")
    else:
        # Timed out
        logger.warning(f"Summarization timed out after {max_wait_seconds}s")
        _summary_cache.pop(in_progress_key, None)
        session.unsubscribe_stdout(capture_broadcast)
        raise HTTPException(
            status_code=504,
            detail=f"Summarization timed out after {max_wait_seconds}s. Try reducing the number of days or syncing fewer channels."
        )

    session.unsubscribe_stdout(capture_broadcast)

    summary_text = "\n\n".join(captured_parts) if captured_parts else None

    # Fallback: read from JSONL if broadcast capture failed
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

    # Cache the result
    _summary_cache[cache_key] = {
        "summary": summary_text,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _summary_cache.pop(in_progress_key, None)

    # Clean up
    try:
        await process_manager.terminate(session_id)
    except Exception as e:
        logger.warning(f"Failed to terminate session {session_id}: {e}")

    return {
        "summary": summary_text,
        "session_id": session_id,
        "team": request.team,
        "days": request.days,
    }


@router.get("/stats")
async def get_stats(
    team: str = Query(...),
    days: int = Query(7, ge=1, le=90),
):
    """Get message stats for a team without the full content."""
    if team not in TEAM_CHANNELS:
        raise HTTPException(status_code=404, detail=f"Unknown team: {team}")
    return get_message_stats(team, days)


# Legacy endpoints
@router.get("/summary")
async def get_slack_summary():
    teams = get_teams()
    channels = []
    for team in teams:
        if team.get("project"):
            for ch in team["channels"]:
                channels.append({"name": f"#{ch}", "unread": 0, "sentiment": "neutral", "last_activity": None})
    return {"channels": channels, "summary": "Use /api/slack/summarize for AI-powered summaries."}


@router.get("/channels/{channel}/recent")
async def get_channel_recent(channel: str, limit: int = 20):
    from app.services.slack_service import get_channel_messages
    content = get_channel_messages(channel, days=1)
    return {"messages": content, "channel": channel}
