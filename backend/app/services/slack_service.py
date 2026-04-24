"""Slack message service.

Reads pre-synced markdown files from ~/tools/slack/data/messages/{channel}/YYYYMMDD.md
and provides team/channel metadata, message content, and sync capabilities.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SLACK_DATA_DIR = Path.home() / "tools/slack/data/messages"
SYNC_SCRIPT = Path.home() / "tools/slack/sync-channel.py"

# Use system python3 (not venv) for running slack tools that need slack_sdk
import shutil
_SYSTEM_PYTHON = shutil.which("python3", path="/opt/homebrew/bin:/usr/local/bin:/usr/bin") or "python3"

# Team-channel mapping derived from teams.md + hot-channels.json
TEAM_CHANNELS: dict[str, dict] = {
    "compute": {
        "label": "Compute",
        "channels": ["compute-platform", "compute-platform-info", "compute-platform-warn"],
        "project": None,
    },
    "wx": {
        "label": "WX",
        "channels": ["wx-users", "wx-dev"],
        "project": "wx",
    },
    "g4": {
        "label": "G4",
        "channels": ["g4-users"],
        "project": "g4",
    },
    "jobs": {
        "label": "Jobs",
        "channels": ["jobs-users"],
        "project": "jobs",
    },
    "temporal": {
        "label": "Temporal",
        "channels": ["temporal-users", "temporal-dev"],
        "project": "temporal",
    },
    "dnd": {
        "label": "Discovery & Delivery",
        "channels": ["discovery-and-delivery"],
        "project": None,
    },
    "datapipeline": {
        "label": "Data Pipeline",
        "channels": ["datapipeline"],
        "project": None,
    },
    "hobbes": {
        "label": "Hobbes",
        "channels": ["hobbes"],
        "project": None,
    },
    "delta": {
        "label": "Delta",
        "channels": ["delta-engineering", "delta-updates", "delta-warn", "an-delta-public"],
        "project": None,
    },
    "mosaics": {
        "label": "Mosaics",
        "channels": ["mosaics"],
        "project": None,
    },
}


def get_teams() -> list[dict]:
    """Return team metadata with channel info."""
    teams = []
    for team_id, info in TEAM_CHANNELS.items():
        teams.append({
            "id": team_id,
            "label": info["label"],
            "channels": info["channels"],
            "project": info["project"],
        })
    return teams


def _channel_dir(channel: str) -> Path | None:
    """Find the message directory for a channel (handles name-only and name-ID variants)."""
    direct = SLACK_DATA_DIR / channel
    if direct.is_dir():
        return direct
    # Try name-with-ID variants
    for d in SLACK_DATA_DIR.iterdir():
        if d.is_dir() and d.name.startswith(channel + "-"):
            return d
    return None


def _date_files_in_range(channel_dir: Path, days: int) -> list[Path]:
    """Get .md files within the date range (most recent `days` days)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y%m%d")

    files = []
    for f in sorted(channel_dir.glob("*.md")):
        # Extract YYYYMMDD from filename
        match = re.match(r"(\d{8})\.md$", f.name)
        if match and match.group(1) >= cutoff_str:
            files.append(f)
    return files


def get_channel_messages(channel: str, days: int) -> str:
    """Read markdown message files for a channel within the date range.

    Returns concatenated markdown content.
    """
    channel_dir = _channel_dir(channel)
    if not channel_dir:
        return ""

    files = _date_files_in_range(channel_dir, days)
    if not files:
        return ""

    parts = []
    for f in files:
        content = f.read_text(errors="replace").strip()
        if content:
            parts.append(content)

    return "\n\n---\n\n".join(parts)


def get_team_messages(team_id: str, days: int) -> str:
    """Get concatenated messages for all channels in a team."""
    info = TEAM_CHANNELS.get(team_id)
    if not info:
        return f"Unknown team: {team_id}"

    parts = []
    for channel in info["channels"]:
        content = get_channel_messages(channel, days)
        if content and not content.startswith("No "):
            parts.append(content)

    if not parts:
        return ""

    return "\n\n".join(parts)


def get_message_stats(team_id: str, days: int) -> dict:
    """Get per-channel message stats for a team."""
    info = TEAM_CHANNELS.get(team_id)
    if not info:
        return {"channels": [], "total": 0}

    channels = []
    total = 0

    for channel in info["channels"]:
        channel_dir = _channel_dir(channel)
        if not channel_dir:
            channels.append({"name": channel, "count": 0, "last_activity": None})
            continue

        files = _date_files_in_range(channel_dir, days)
        count = 0
        last_activity = None

        for f in files:
            # Count messages by counting timestamp patterns (e.g., "**User** `HH:MM:SS`")
            content = f.read_text(errors="replace")
            msg_matches = re.findall(r"\*\*[^*]+\*\*\s+`\d{2}:\d{2}:\d{2}`", content)
            count += len(msg_matches)

            if not last_activity:
                # Use file date as last activity
                match = re.match(r"(\d{8})\.md$", f.name)
                if match:
                    last_activity = f"{match.group(1)[:4]}-{match.group(1)[4:6]}-{match.group(1)[6:8]}"

        # Use the most recent file for last_activity
        if files:
            match = re.match(r"(\d{8})\.md$", files[-1].name)
            if match:
                d = match.group(1)
                last_activity = f"{d[:4]}-{d[4:6]}-{d[6:8]}"

        channels.append({"name": channel, "count": count, "last_activity": last_activity})
        total += count

    return {"channels": channels, "total": total}


async def sync_channels(channels: list[str]) -> dict:
    """Run sync-channel.py for each channel to fetch new messages.

    Returns summary of sync results.
    """
    if not SYNC_SCRIPT.exists():
        return {"error": f"Sync script not found: {SYNC_SCRIPT}", "synced": 0}

    results = {}
    for channel in channels:
        try:
            proc = await asyncio.create_subprocess_exec(
                _SYSTEM_PYTHON, str(SYNC_SCRIPT), channel,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(SYNC_SCRIPT.parent),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

            stderr_text = stderr.decode("utf-8", errors="replace").strip()[:500]
            results[channel] = {
                "success": proc.returncode == 0,
                "output": stdout.decode("utf-8", errors="replace").strip()[:200],
                "error": stderr_text if proc.returncode != 0 else None,
            }
            if proc.returncode != 0:
                logger.warning(f"Sync failed for {channel} (rc={proc.returncode}): {stderr_text}")
        except asyncio.TimeoutError:
            results[channel] = {"success": False, "output": "Sync timed out (60s)"}
        except Exception as e:
            results[channel] = {"success": False, "output": str(e)}

    synced = sum(1 for r in results.values() if r["success"])
    return {"synced": synced, "total": len(channels), "channels": results}


async def sync_channels_streaming(channels: list[str]):
    """Generator that yields sync progress updates for SSE.

    Yields dicts with:
    - status: "syncing" | "complete" | "error"
    - channel: current channel name
    - channel_index: progress (1-based)
    - total_channels: total count
    - messages_synced: cumulative message count (estimated)
    - last_message_time: timestamp of most recent message
    - last_message_age: relative time string (e.g., "13m")
    """
    if not SYNC_SCRIPT.exists():
        yield {
            "status": "error",
            "error": f"Sync script not found: {SYNC_SCRIPT}",
        }
        return

    total_messages = 0
    for idx, channel in enumerate(channels, start=1):
        yield {
            "status": "syncing",
            "channel": channel,
            "channel_index": idx,
            "total_channels": len(channels),
            "messages_synced": total_messages,
        }

        try:
            proc = await asyncio.create_subprocess_exec(
                _SYSTEM_PYTHON, str(SYNC_SCRIPT), channel,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(SYNC_SCRIPT.parent),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

            # Parse output for message count (look for "Synced X messages" or similar)
            output = stdout.decode("utf-8", errors="replace").strip()
            msg_match = re.search(r"(\d+)\s+messages?", output, re.IGNORECASE)
            if msg_match:
                total_messages += int(msg_match.group(1))

            # Check latest message timestamp by parsing the file content
            channel_dir = _channel_dir(channel)
            last_msg_time = None
            last_msg_age = None
            if channel_dir:
                files = sorted(channel_dir.glob("*.md"))
                if files:
                    latest_file = files[-1]
                    # Parse the actual message timestamps from the file
                    try:
                        content = latest_file.read_text(errors="replace")
                        # Find all message timestamps: **Username** `HH:MM:SS`
                        # Most recent is usually at the bottom
                        timestamp_matches = list(re.finditer(r"`(\d{2}):(\d{2}):(\d{2})`", content))

                        if timestamp_matches:
                            # Get last timestamp in file
                            last_match = timestamp_matches[-1]
                            hour = int(last_match.group(1))
                            minute = int(last_match.group(2))
                            second = int(last_match.group(3))

                            # Parse date from filename YYYYMMDD.md
                            match = re.match(r"(\d{8})\.md$", latest_file.name)
                            if match:
                                date_str = match.group(1)
                                file_date = datetime.strptime(date_str, "%Y%m%d")

                                # Combine date and time
                                msg_datetime = file_date.replace(hour=hour, minute=minute, second=second)
                                now = datetime.now()
                                delta = now - msg_datetime

                                # Calculate relative age
                                total_minutes = delta.total_seconds() / 60

                                if total_minutes < 60:
                                    last_msg_age = f"{int(total_minutes)}m"
                                elif total_minutes < 1440:  # < 24 hours
                                    last_msg_age = f"{int(total_minutes / 60)}h"
                                else:
                                    last_msg_age = f"{int(total_minutes / 1440)}d"

                                last_msg_time = msg_datetime.strftime("%Y-%m-%d %H:%M")
                    except Exception as e:
                        logger.debug(f"Could not parse message time for {channel}: {e}")

        except asyncio.TimeoutError:
            logger.warning(f"Sync timeout for {channel}")
        except Exception as e:
            logger.error(f"Sync error for {channel}: {e}")

    # Final complete message
    yield {
        "status": "complete",
        "total_channels": len(channels),
        "messages_synced": total_messages,
        "last_message_time": last_msg_time,
        "last_message_age": last_msg_age,
    }
