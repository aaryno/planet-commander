"""
Warning Monitoring Background Job

Polls Slack warning channels for new warnings and processes them.
Runs every 1-5 minutes to detect warnings in near-real-time.
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

from app.database import async_session
from app.services.warning_monitor import WarningMonitorService

logger = logging.getLogger(__name__)

# Slack message data directory
SLACK_DATA_DIR = Path.home() / "tools/slack/data/messages"


async def monitor_warning_channels() -> dict:
    """
    Monitor warning channels for new warnings.

    Reads recent messages from Slack data directory and processes new warnings.

    Returns:
        Statistics: messages scanned, warnings detected, etc.
    """
    try:
        async with async_session() as db:
            monitor_service = WarningMonitorService(db)

            logger.info("Starting warning channel monitoring")

            stats = {
                "channels_scanned": 0,
                "messages_scanned": 0,
                "warnings_created": 0,
                "warnings_updated": 0,
                "errors": [],
            }

            # Monitor compute-platform-warn channel
            channel_name = "compute-platform-warn"
            channel_dir = _get_channel_dir(channel_name)

            if not channel_dir:
                logger.warning(
                    f"Channel directory not found for {channel_name}, "
                    f"skipping. Run: python ~/tools/slack/sync-channel.py {channel_name}"
                )
                return stats

            stats["channels_scanned"] += 1

            # Read messages from today
            today = datetime.now(timezone.utc).strftime("%Y%m%d")
            message_file = channel_dir / f"{today}.md"

            if not message_file.exists():
                logger.info(
                    f"No messages for {channel_name} today ({message_file}), skipping"
                )
                return stats

            # Parse messages from markdown file
            messages = _parse_messages_from_file(message_file)
            stats["messages_scanned"] += len(messages)

            logger.info(
                f"Found {len(messages)} messages in {channel_name} for {today}"
            )

            # Process each message
            for msg in messages:
                try:
                    # Skip old messages (only process last 2 hours)
                    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
                    if msg["timestamp"] < cutoff:
                        continue

                    # Process message
                    warning = await monitor_service.process_message(
                        message_text=msg["text"],
                        channel_id=msg["channel_id"],
                        channel_name=channel_name,
                        message_ts=msg["ts"],
                        thread_ts=msg.get("thread_ts"),
                    )

                    if warning:
                        if warning.created_at == warning.updated_at:
                            stats["warnings_created"] += 1
                        else:
                            stats["warnings_updated"] += 1

                except Exception as e:
                    error_msg = f"Error processing message {msg.get('ts')}: {e}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)

            # Auto-clear stale warnings (warnings > 24 hours old)
            cleared = await monitor_service.auto_clear_stale_warnings(stale_hours=24)
            logger.info(f"Auto-cleared {len(cleared)} stale warnings")

            logger.info(
                f"Warning monitoring complete: {stats['messages_scanned']} messages scanned, "
                f"{stats['warnings_created']} warnings created, "
                f"{stats['warnings_updated']} warnings updated"
            )

            return stats

    except Exception as e:
        logger.error(f"Error in warning monitoring: {e}", exc_info=True)
        return {
            "channels_scanned": 0,
            "messages_scanned": 0,
            "warnings_created": 0,
            "warnings_updated": 0,
            "errors": [str(e)],
        }


def _get_channel_dir(channel_name: str) -> Path | None:
    """
    Find the message directory for a channel.

    Args:
        channel_name: Channel name (e.g., "compute-platform-warn")

    Returns:
        Path to channel directory or None
    """
    # Try exact match
    direct = SLACK_DATA_DIR / channel_name
    if direct.is_dir():
        return direct

    # Try name-with-ID variants (e.g., "compute-platform-warn-C123ABC")
    for d in SLACK_DATA_DIR.iterdir():
        if d.is_dir() and d.name.startswith(channel_name + "-"):
            return d

    return None


def _parse_messages_from_file(file_path: Path) -> list[dict]:
    """
    Parse messages from markdown file.

    Args:
        file_path: Path to markdown file

    Returns:
        List of message dicts
    """
    messages = []

    with open(file_path, "r") as f:
        content = f.read()

    # Parse markdown format:
    # ### 14:23:45 @user (ts: 1234567890.123456)
    # Message text here
    # (blank line)

    # Regex to match message header
    header_pattern = re.compile(
        r'^### (\d{2}:\d{2}:\d{2}) @(\S+)(?: \(ts: ([\d.]+)\))?',
        re.MULTILINE
    )

    # Split by headers
    parts = header_pattern.split(content)

    # parts[0] is before first header (ignore)
    # parts[1::4] = times, parts[2::4] = users, parts[3::4] = timestamps, parts[4::4] = texts
    for i in range(1, len(parts), 4):
        if i + 3 >= len(parts):
            break

        time_str = parts[i]
        user = parts[i + 1]
        ts = parts[i + 2]
        text = parts[i + 3].strip()

        # Skip if no text
        if not text:
            continue

        # Parse timestamp
        try:
            today = datetime.now(timezone.utc).date()
            hour, minute, second = map(int, time_str.split(":"))
            timestamp = datetime.combine(
                today, datetime.min.time().replace(hour=hour, minute=minute, second=second)
            ).replace(tzinfo=timezone.utc)
        except Exception as e:
            logger.warning(f"Failed to parse timestamp {time_str}: {e}")
            timestamp = datetime.now(timezone.utc)

        messages.append({
            "text": text,
            "user": user,
            "ts": ts or f"{timestamp.timestamp()}",
            "thread_ts": None,  # TODO: Parse thread info from markdown
            "timestamp": timestamp,
            "channel_id": "C123ABC",  # TODO: Get actual channel ID
        })

    return messages
