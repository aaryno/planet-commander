"""Temporal Slack service.

Parses pre-synced Slack markdown files to find unanswered questions
and compute sentiment in Temporal channels.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SLACK_DATA_DIR = Path.home() / "tools/slack/data/messages"

# Current Slack channel names (channels were renamed)
TEMPORAL_CHANNELS = ["temporal-dev", "temporal-users"]

# Map current names → old directory names for reading historical data
_CHANNEL_ALIASES: dict[str, list[str]] = {
    "temporal-dev": ["temporalio-cloud"],
    "temporal-users": ["temporal"],
}

# Sentiment keyword lists
POSITIVE_WORDS = {
    "thanks", "thank", "worked", "works", "working", "great", "solved",
    "perfect", "awesome", "excellent", "nice", "good", "helpful", "resolved",
    "fixed", "love", "appreciate",
}
NEGATIVE_WORDS = {
    "broken", "not working", "error", "failed", "failing", "help",
    "urgent", "blocked", "issue", "problem", "bug", "wrong", "stuck",
    "frustrated", "confused", "unclear", "down", "outage", "broken",
}

# Bot name patterns to exclude
BOT_PATTERNS = re.compile(r"(bot|integration|webhook|app|slackbot|gitlab|jira|pagerduty|datadog|github)", re.IGNORECASE)

# Message pattern: **Username** `HH:MM:SS`
MSG_PATTERN = re.compile(r"^\*\*([^*]+)\*\*\s+`(\d{2}:\d{2}:\d{2})`\s*(.*)", re.MULTILINE)


def _channel_dir(channel: str) -> Path | None:
    """Find the message directory for a channel.

    Checks current name, old alias names, and ID-suffixed variants.
    """
    # Check current name first
    direct = SLACK_DATA_DIR / channel
    if direct.is_dir():
        return direct
    # Check ID-suffixed variant (e.g. temporal-dev-C08G2TZ8EJZ)
    for d in SLACK_DATA_DIR.iterdir():
        if d.is_dir() and d.name.startswith(channel + "-"):
            return d
    # Check old alias names (channels that were renamed)
    for alias in _CHANNEL_ALIASES.get(channel, []):
        alias_dir = SLACK_DATA_DIR / alias
        if alias_dir.is_dir():
            return alias_dir
        for d in SLACK_DATA_DIR.iterdir():
            if d.is_dir() and d.name.startswith(alias + "-"):
                return d
    return None


def _date_files_in_range(channel_dir: Path, days: int) -> list[Path]:
    """Get .md files within the date range."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y%m%d")

    files = []
    for f in sorted(channel_dir.glob("*.md")):
        match = re.match(r"(\d{8})\.md$", f.name)
        if match and match.group(1) >= cutoff_str:
            files.append(f)
    return files


def _get_latest_file_date(channel_dir: Path) -> str | None:
    """Get the date string of the most recent .md file in a channel dir."""
    latest = None
    for f in channel_dir.glob("*.md"):
        match = re.match(r"(\d{8})\.md$", f.name)
        if match:
            d = match.group(1)
            if latest is None or d > latest:
                latest = d
    return latest


def _get_data_freshness() -> dict:
    """Check how fresh the Slack data is across all channels."""
    freshness = {}
    for channel in TEMPORAL_CHANNELS:
        channel_dir = _channel_dir(channel)
        if not channel_dir:
            freshness[channel] = {"latest_date": None, "stale": True, "days_old": None}
            continue
        latest = _get_latest_file_date(channel_dir)
        if latest:
            latest_dt = datetime.strptime(latest, "%Y%m%d").replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - latest_dt).days
            freshness[channel] = {
                "latest_date": f"{latest[:4]}-{latest[4:6]}-{latest[6:8]}",
                "stale": age_days > 2,
                "days_old": age_days,
            }
        else:
            freshness[channel] = {"latest_date": None, "stale": True, "days_old": None}
    return freshness


def _parse_messages(content: str, date_str: str) -> list[dict]:
    """Parse a day's markdown content into structured messages."""
    messages = []
    lines = content.split("\n")
    current_msg = None

    for line in lines:
        msg_match = MSG_PATTERN.match(line)
        if msg_match:
            if current_msg:
                messages.append(current_msg)
            user = msg_match.group(1).strip()
            time_str = msg_match.group(2)
            text = msg_match.group(3).strip()
            current_msg = {
                "user": user,
                "time": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}T{time_str}Z",
                "text": text,
                "replies": 0,
                "is_bot": bool(BOT_PATTERNS.search(user)),
            }
        elif line.startswith("  ") and current_msg:
            # Thread reply (indented)
            current_msg["replies"] += 1
            # Append text to capture full context
            reply_text = line.strip()
            if reply_text:
                current_msg["text"] += " " + reply_text
        elif current_msg and line.strip():
            # Continuation of message text
            current_msg["text"] += " " + line.strip()

    if current_msg:
        messages.append(current_msg)

    return messages


def get_channel_summary(days: int = 7) -> dict:
    """Get per-channel summary with message counts and active users.

    If no data is found within the requested range, automatically expands
    to cover the most recent data available.
    """
    freshness = _get_data_freshness()
    channels_data = []
    actual_days = days

    # If data is stale, auto-expand range to include latest available data
    max_stale_days = max(
        (f["days_old"] for f in freshness.values() if f["days_old"] is not None),
        default=0,
    )
    if max_stale_days >= days:
        actual_days = max_stale_days + 7  # include a week of data from the latest file

    for channel in TEMPORAL_CHANNELS:
        channel_dir = _channel_dir(channel)
        if not channel_dir:
            channels_data.append({
                "channel": channel,
                "message_count": 0,
                "active_users": [],
                "unanswered_count": 0,
            })
            continue

        files = _date_files_in_range(channel_dir, actual_days)
        user_counts: dict[str, int] = {}
        msg_count = 0
        unanswered_count = 0

        for f in files:
            date_match = re.match(r"(\d{8})\.md$", f.name)
            if not date_match:
                continue
            date_str = date_match.group(1)

            content = f.read_text(errors="replace")
            messages = _parse_messages(content, date_str)

            for msg in messages:
                if msg["is_bot"]:
                    continue
                msg_count += 1
                user = msg["user"]
                user_counts[user] = user_counts.get(user, 0) + 1

                if msg["replies"] == 0 and "?" in msg["text"]:
                    unanswered_count += 1

        # Sort users by message count
        active_users = [
            {"name": name, "messages": count}
            for name, count in sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        channels_data.append({
            "channel": channel,
            "message_count": msg_count,
            "active_users": active_users,
            "unanswered_count": unanswered_count,
        })

    return {
        "channels": channels_data,
        "days": days,
        "actual_days": actual_days,
        "total_messages": sum(c["message_count"] for c in channels_data),
        "freshness": freshness,
    }


def get_unanswered(days: int = 7, channels: list[str] | None = None) -> dict:
    """Find unanswered questions in Temporal Slack channels."""
    now = datetime.now(timezone.utc)
    unanswered = []
    check_channels = channels if channels else TEMPORAL_CHANNELS
    freshness = _get_data_freshness()
    actual_days = days

    # Auto-expand if data is stale
    max_stale_days = max(
        (f["days_old"] for f in freshness.values() if f["days_old"] is not None),
        default=0,
    )
    if max_stale_days >= days:
        actual_days = max_stale_days + 7

    for channel in check_channels:
        channel_dir = _channel_dir(channel)
        if not channel_dir:
            continue

        files = _date_files_in_range(channel_dir, actual_days)
        for f in files:
            date_match = re.match(r"(\d{8})\.md$", f.name)
            if not date_match:
                continue
            date_str = date_match.group(1)

            content = f.read_text(errors="replace")
            messages = _parse_messages(content, date_str)

            for msg in messages:
                if msg["is_bot"]:
                    continue
                if msg["replies"] > 0:
                    continue
                if "?" not in msg["text"]:
                    continue

                # Calculate age
                try:
                    msg_time = datetime.fromisoformat(msg["time"].replace("Z", "+00:00"))
                    age_hours = (now - msg_time).total_seconds() / 3600
                except (ValueError, TypeError):
                    age_hours = 0

                # Truncate text for display
                display_text = msg["text"][:200]
                if len(msg["text"]) > 200:
                    display_text += "..."

                unanswered.append({
                    "channel": channel,
                    "user": msg["user"],
                    "time": msg["time"],
                    "text": display_text,
                    "age_hours": round(age_hours, 1),
                })

    # Sort by age descending (oldest first)
    unanswered.sort(key=lambda m: m["age_hours"], reverse=True)

    return {
        "unanswered": unanswered,
        "total": len(unanswered),
        "channels_checked": check_channels,
        "actual_days": actual_days,
        "freshness": freshness,
    }


def get_raw_messages(days: int = 7, channels: list[str] | None = None) -> str:
    """Get raw markdown content for Temporal channels, with auto-expand for stale data.

    Returns concatenated markdown suitable for feeding to an LLM summarizer.
    """
    freshness = _get_data_freshness()
    actual_days = days

    max_stale_days = max(
        (f["days_old"] for f in freshness.values() if f["days_old"] is not None),
        default=0,
    )
    if max_stale_days >= days:
        actual_days = max_stale_days + 7

    check_channels = channels if channels else TEMPORAL_CHANNELS
    parts = []

    for channel in check_channels:
        channel_dir = _channel_dir(channel)
        if not channel_dir:
            continue

        files = _date_files_in_range(channel_dir, actual_days)
        if not files:
            continue

        channel_parts = [f"## #{channel}\n"]
        for f in files:
            content = f.read_text(errors="replace").strip()
            if content:
                date_str = f.stem
                formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                channel_parts.append(f"### {formatted}\n{content}\n")

        if len(channel_parts) > 1:  # more than just the header
            parts.append("\n".join(channel_parts))

    return "\n\n".join(parts)


def get_sentiment(days: int = 7) -> dict:
    """Compute keyword-based sentiment for Temporal Slack channels."""
    positive = 0
    negative = 0
    neutral = 0
    total = 0
    frustrated_samples = []
    freshness = _get_data_freshness()
    actual_days = days

    # Auto-expand if data is stale
    max_stale_days = max(
        (f["days_old"] for f in freshness.values() if f["days_old"] is not None),
        default=0,
    )
    if max_stale_days >= days:
        actual_days = max_stale_days + 7

    for channel in TEMPORAL_CHANNELS:
        channel_dir = _channel_dir(channel)
        if not channel_dir:
            continue

        files = _date_files_in_range(channel_dir, actual_days)
        for f in files:
            date_match = re.match(r"(\d{8})\.md$", f.name)
            if not date_match:
                continue
            date_str = date_match.group(1)

            content = f.read_text(errors="replace")
            messages = _parse_messages(content, date_str)

            for msg in messages:
                if msg["is_bot"]:
                    continue
                total += 1
                text_lower = msg["text"].lower()

                has_positive = any(w in text_lower for w in POSITIVE_WORDS)
                has_negative = any(w in text_lower for w in NEGATIVE_WORDS)

                if has_negative and not has_positive:
                    negative += 1
                    if len(frustrated_samples) < 5:
                        sample_text = msg["text"][:100]
                        frustrated_samples.append(f"#{channel} @{msg['user']}: {sample_text}")
                elif has_positive and not has_negative:
                    positive += 1
                else:
                    neutral += 1

    if total == 0:
        return {
            "positive": 0, "neutral": 0, "frustrated": 0,
            "positive_pct": 0, "neutral_pct": 0, "frustrated_pct": 0,
            "total_messages": 0,
            "sample_frustrated": [],
            "days": days,
        }

    return {
        "positive": positive,
        "neutral": neutral,
        "frustrated": negative,
        "positive_pct": round(positive / total * 100),
        "neutral_pct": round(neutral / total * 100),
        "frustrated_pct": round(negative / total * 100),
        "total_messages": total,
        "sample_frustrated": frustrated_samples,
        "days": days,
    }
