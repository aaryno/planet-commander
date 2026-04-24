#!/usr/bin/env python3
"""
Backfill warning events from Slack + PagerDuty historical data.

Data sources:
1. Slack messages from warning/alert channels
2. PagerDuty incidents (9,349 incidents over 90 days)
3. Grafana alert definitions (107 rules)
4. Alert channel mappings

Strategy:
1. Parse all Slack warning/alert messages
2. Extract alert names, timestamps, systems
3. Match to PagerDuty incidents by time + alert name + channel
4. Assign escalation probability (baseline or pattern-based)
5. Generate synthetic feedback based on escalation outcome
6. Detect lagged correlations (info → warn within 30 min)
7. Calculate DEFCON levels based on multi-channel activity
"""

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from sqlalchemy import select
from app.database import async_session, engine
from app.models import Base, WarningEvent, WarningFeedback, FeedbackType


# Data directories
SLACK_DATA_DIR = Path.home() / "tools/slack/data"
MESSAGES_DIR = SLACK_DATA_DIR / "messages"
PD_DB = SLACK_DATA_DIR / "pagerduty-incidents-db.json"
GRAFANA_DB = SLACK_DATA_DIR / "grafana-alerts-db.json"
ALERT_CHANNELS_DB = SLACK_DATA_DIR / "alert-channels-db.json"


# Channel classifications
WARNING_CHANNELS = [
    "compute-platform-warn",
    "delta-warn",
    "discovery-and-delivery-warn",
    "hobbes-warnings",
    "orbits-warnings",
    "applied-ml-warn",
    "dii-notifications-warn",
]

INFO_CHANNELS = [
    "compute-platform-info",  # Deployment notifications, lagged signals
]

ALERT_CHANNELS = [
    # Too many to list - will auto-discover from messages
]


# Alert name extraction patterns
ALERT_PATTERNS = [
    # Grafana-style: "🚨 **alert-name** (System)"
    r'🚨\s+\*\*([a-zA-Z0-9-_]+)\*\*\s+\(([^)]+)\)',

    # PagerDuty-style: "FIRING: alert-name"
    r'FIRING:\s+([a-zA-Z0-9-_]+)',

    # Simple: "alert-name is firing"
    r'([a-zA-Z0-9-_]+)\s+is\s+(firing|alerting|down|degraded)',

    # Jobs-style: "Low runs for jobs-scheduler"
    r'(jobs-[a-zA-Z0-9-_]+)',
]


def load_pagerduty_incidents() -> dict[str, Any]:
    """Load PagerDuty incidents database."""
    with open(PD_DB) as f:
        data = json.load(f)
    return data["incidents"]


def load_grafana_alerts() -> dict[str, Any]:
    """Load Grafana alert definitions."""
    with open(GRAFANA_DB) as f:
        data = json.load(f)
    return data["alerts"]


def load_alert_channels() -> dict[str, Any]:
    """Load alert channel mappings."""
    with open(ALERT_CHANNELS_DB) as f:
        data = json.load(f)
    return data["channels"]


def parse_slack_message(text: str, channel: str) -> dict[str, Any] | None:
    """Extract alert information from Slack message.

    Returns:
        {
            "alert_name": str,
            "system": str | None,
            "raw_text": str,
        }
        or None if not an alert
    """
    for pattern in ALERT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            return {
                "alert_name": groups[0],
                "system": groups[1] if len(groups) > 1 else None,
                "raw_text": text,
            }

    return None


def parse_channel_messages(channel_dir: Path, days: int = 30) -> list[dict]:
    """Parse messages from a Slack channel directory.

    Args:
        channel_dir: Path to channel directory (e.g., messages/compute-platform-warn/)
        days: Number of days to look back

    Returns:
        List of parsed alert events
    """
    events = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Iterate through daily message files
    for date_file in sorted(channel_dir.glob("????????.md")):
        # Parse date from filename (YYYYMMDD.md)
        date_str = date_file.stem
        try:
            file_date = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        if file_date < cutoff:
            continue

        # Parse messages from file
        with open(date_file) as f:
            content = f.read()

        # Regex to match message headers:
        # ### 14:23:45 @user (ts: 1234567890.123456)
        header_pattern = re.compile(
            r'^### (\d{2}:\d{2}:\d{2}) @(\S+)(?: \(ts: ([\d.]+)\))?',
            re.MULTILINE
        )

        parts = header_pattern.split(content)

        # Parse each message
        for i in range(1, len(parts), 4):
            if i + 3 >= len(parts):
                break

            time_str = parts[i]
            user = parts[i + 1]
            ts = parts[i + 2]
            text = parts[i + 3].strip()

            if not text:
                continue

            # Parse timestamp
            try:
                hour, minute, second = map(int, time_str.split(":"))
                timestamp = file_date.replace(hour=hour, minute=minute, second=second)
            except Exception:
                timestamp = file_date

            # Extract alert info
            alert = parse_slack_message(text, channel_dir.name)
            if not alert:
                continue

            events.append({
                "channel": channel_dir.name.split("-")[0] if "-" in channel_dir.name else channel_dir.name,
                "channel_full": channel_dir.name,
                "alert_name": alert["alert_name"],
                "system": alert["system"],
                "timestamp": timestamp,
                "slack_ts": ts or f"{timestamp.timestamp()}",
                "user": user,
                "raw_text": text,
            })

    return events


def match_to_pagerduty(
    events: list[dict],
    pd_incidents: dict[str, Any]
) -> None:
    """Match Slack events to PagerDuty incidents.

    Modifies events in-place, adding 'escalated' and 'pd_incident_id' fields.

    Matching criteria:
    1. Time: PD incident created within ±5 minutes of Slack message
    2. Alert name: PD title contains Slack alert name
    3. Channel: PD slack_channels contains Slack channel
    """
    for event in events:
        event["escalated"] = False
        event["pd_incident_id"] = None

        for pd_id, incident in pd_incidents.items():
            # Check time window (±5 minutes)
            pd_time = datetime.fromisoformat(incident["created_at"].replace("Z", "+00:00"))
            time_diff = abs((event["timestamp"] - pd_time).total_seconds())

            if time_diff > 5 * 60:  # 5 minutes
                continue

            # Check alert name match
            if event["alert_name"].lower() not in incident["title"].lower():
                continue

            # Check channel match (if available)
            if "slack_channels" in incident and incident["slack_channels"]:
                # Extract base channel name (e.g., "compute-platform-warn" from "compute-platform-warn-C01C392C9BM")
                base_channel = event["channel_full"].split("-C0")[0]
                if base_channel not in incident["slack_channels"]:
                    continue

            # Match found!
            event["escalated"] = True
            event["pd_incident_id"] = pd_id
            break


def detect_lagged_correlations(events: list[dict]) -> None:
    """Detect lagged correlations between info signals and warnings.

    Adds 'lagged_signal_id' and 'lag_minutes' to warning events.
    """
    # Separate info signals and warnings
    info_signals = [e for e in events if e["channel"] == "compute-platform"]
    warnings = [e for e in events if e["channel"] in WARNING_CHANNELS]

    for warning in warnings:
        for info in info_signals:
            time_diff = (warning["timestamp"] - info["timestamp"]).total_seconds()

            # Check if within lag window (5-30 minutes after info signal)
            if not (5 * 60 <= time_diff <= 30 * 60):
                continue

            # Check for shared entities (crude: check if alert names share keywords)
            warning_keywords = set(warning["alert_name"].split("-"))
            info_keywords = set(info.get("alert_name", "").split("-"))

            if warning_keywords & info_keywords:
                warning["lagged_signal_id"] = info.get("id")
                warning["lag_minutes"] = time_diff / 60
                break


def assign_escalation_probability(
    event: dict,
    grafana_alerts: dict[str, Any]
) -> float:
    """Assign initial escalation probability to an event.

    Strategy:
    1. Check Grafana alert severity (if matched)
    2. Use historical pattern (if known)
    3. Default to baseline (0.5)
    """
    # Try to match Grafana alert
    for alert_name, alert in grafana_alerts.items():
        if alert["name"] == event["alert_name"]:
            # Use severity to set baseline
            severities = alert.get("severities", [])
            if "critical" in severities:
                return 0.8
            elif "high" in severities:
                return 0.65
            elif "medium" in severities:
                return 0.5
            elif "low" in severities:
                return 0.3
            break

    # Default baseline
    return 0.5


async def backfill(days: int = 30, dry_run: bool = False):
    """Backfill warning events from historical data.

    Args:
        days: Number of days to backfill
        dry_run: If True, don't insert into database
    """
    print(f"🔄 Starting backfill for last {days} days...")

    # Load external data
    print("📥 Loading PagerDuty incidents...")
    pd_incidents = load_pagerduty_incidents()
    print(f"   Loaded {len(pd_incidents)} incidents")

    print("📥 Loading Grafana alerts...")
    grafana_alerts = load_grafana_alerts()
    print(f"   Loaded {len(grafana_alerts)} alert rules")

    # Parse Slack messages
    print("📥 Parsing Slack messages...")
    all_events = []

    for channel_name in WARNING_CHANNELS + INFO_CHANNELS:
        channel_dir = MESSAGES_DIR / channel_name
        if not channel_dir.exists():
            print(f"   ⚠️  Channel directory not found: {channel_name}")
            continue

        events = parse_channel_messages(channel_dir, days)
        print(f"   {channel_name}: {len(events)} events")
        all_events.extend(events)

    print(f"   Total events parsed: {len(all_events)}")

    # Match to PagerDuty
    print("🔗 Matching to PagerDuty incidents...")
    match_to_pagerduty(all_events, pd_incidents)
    escalated_count = sum(1 for e in all_events if e["escalated"])
    print(f"   Matched {escalated_count}/{len(all_events)} events to PD incidents")

    # Detect lagged correlations
    print("🔍 Detecting lagged correlations...")
    detect_lagged_correlations(all_events)
    lagged_count = sum(1 for e in all_events if "lagged_signal_id" in e)
    print(f"   Found {lagged_count} lagged correlations")

    # Assign probabilities
    print("📊 Assigning escalation probabilities...")
    for event in all_events:
        event["escalation_probability"] = assign_escalation_probability(event, grafana_alerts)

    if dry_run:
        print("\n✅ Dry run complete. Sample events:")
        for event in all_events[:5]:
            print(f"   {event['timestamp']} - {event['alert_name']} - "
                  f"escalated={event['escalated']} - prob={event['escalation_probability']}")
        print(f"\nWould insert {len(all_events)} events into database.")
        return

    # Insert into database
    print("💾 Inserting into database...")
    async with async_session() as db:
        # Create tables if not exist
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        inserted_events = 0
        inserted_feedback = 0

        for event in all_events:
            # Create warning event
            warning_event = WarningEvent(
                alert_name=event["alert_name"],
                system=event["system"] or "Unknown",
                channel=event["channel_full"],
                escalation_probability=event["escalation_probability"],
                escalated=event["escalated"],
                first_seen=event["timestamp"],
                last_seen=event["timestamp"],
                slack_thread_ts=event["slack_ts"],
            )

            db.add(warning_event)
            await db.flush()  # Get ID
            inserted_events += 1

            # Generate synthetic feedback
            predicted_escalation = event["escalation_probability"] > 0.5
            actual_escalation = event["escalated"]
            prediction_correct = (predicted_escalation == actual_escalation)

            feedback = WarningFeedback(
                warning_event_id=warning_event.id,
                feedback_type=FeedbackType.PREDICTION_ACCURACY,
                prediction_was_correct=prediction_correct,
                actual_escalated=actual_escalation,
                predicted_probability=event["escalation_probability"],
                submitted_by="backfill-script",
                comment=f"Synthetic feedback from historical data (PD incident: {event['pd_incident_id']})" if event["pd_incident_id"] else "Synthetic feedback from historical data",
            )

            db.add(feedback)
            inserted_feedback += 1

        await db.commit()
        print(f"   Inserted {inserted_events} warning events")
        print(f"   Inserted {inserted_feedback} feedback records")

    print("\n✅ Backfill complete!")
    print(f"\nSummary:")
    print(f"  Total events: {len(all_events)}")
    print(f"  Escalated: {escalated_count} ({escalated_count/len(all_events)*100:.1f}%)")
    print(f"  Lagged correlations: {lagged_count}")
    print(f"  Channels processed: {len(WARNING_CHANNELS + INFO_CHANNELS)}")
    print(f"\n🎯 Learning system now has baseline data!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill warning events from Slack + PagerDuty")
    parser.add_argument("--days", type=int, default=30, help="Number of days to backfill")
    parser.add_argument("--dry-run", action="store_true", help="Parse data but don't insert")

    args = parser.parse_args()

    asyncio.run(backfill(days=args.days, dry_run=args.dry_run))
