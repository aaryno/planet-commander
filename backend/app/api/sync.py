"""Sync status and trigger API — shows data source staleness and allows manual sync."""

import asyncio
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])

TOOLS_DB_DIR = Path.home() / "tools" / "db"
TOOLS_SLACK_DIR = Path.home() / "tools" / "slack"
LOGS_DIR = TOOLS_DB_DIR / "logs"

# Map source names to sync commands
SYNC_COMMANDS: dict[str, list[str]] = {
    "pagerduty": ["python3", str(TOOLS_SLACK_DIR / "sync-pagerduty-alerts.py")],
    "slack_fast": [str(TOOLS_DB_DIR / "sync-slack-fast.sh")],
    "slack_full": ["python3", str(TOOLS_SLACK_DIR / "sync-channels-prioritized.py"), "-p", "4", "--include-others"],
    "jira_issues": ["python3", str(TOOLS_DB_DIR / "sync-all-to-db.py"), "--jira"],
    "jira_changes": ["python3", str(Path.home() / "tools" / "slack" / "harvest-jira-changes.py")],
    "jira_projects": ["python3", str(TOOLS_DB_DIR / "sync-all-to-db.py"), "--jira"],
    "grafana_alerts": ["python3", str(TOOLS_DB_DIR / "sync-all-to-db.py"), "--grafana"],
    "google_drive": ["python3", str(TOOLS_DB_DIR / "sync-all-to-db.py"), "--gdrive"],
    "wiki": ["python3", str(TOOLS_DB_DIR / "sync-all-to-db.py"), "--wiki"],
    "full_sync": [str(TOOLS_DB_DIR / "sync-cron.sh")],
}

# Track running sync processes
_running_syncs: dict[str, subprocess.Popen] = {}


class SyncSourceStatus(BaseModel):
    source_name: str
    last_sync: Optional[str] = None
    last_sync_relative: Optional[str] = None
    record_count: Optional[int] = None
    status: str = "unknown"  # "green", "yellow", "red", "unknown"
    staleness_seconds: Optional[float] = None
    sync_metadata: Optional[dict] = None
    is_syncing: bool = False


class SyncStatusResponse(BaseModel):
    sources: list[SyncSourceStatus]
    timestamp: str


class SyncTriggerResponse(BaseModel):
    source: str
    status: str  # "started", "already_running", "error"
    message: str


class SyncLogEntry(BaseModel):
    timestamp: str
    line: str


class SyncLogsResponse(BaseModel):
    source: str
    logs: list[str]
    log_file: Optional[str] = None


def _relative_time(dt: datetime) -> str:
    """Convert datetime to relative time string."""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    seconds = diff.total_seconds()

    if seconds < 60:
        return f"{int(seconds)}s ago"
    elif seconds < 3600:
        return f"{int(seconds / 60)}m ago"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1f}h ago"
    else:
        days = seconds / 86400
        return f"{days:.1f}d ago"


def _staleness_status(seconds: Optional[float]) -> str:
    """Determine status color based on staleness."""
    if seconds is None:
        return "unknown"
    if seconds < 3600:  # < 1 hour
        return "green"
    elif seconds < 86400:  # < 24 hours
        return "yellow"
    else:
        return "red"


# Sources that bypass sync_state — check actual data freshness instead
# Maps display name → SQL query returning (last_sync, record_count)
LIVE_FRESHNESS_SOURCES: dict[str, tuple[str, str, int]] = {
    "slack_fast": (
        "Slack (fast — P1/P2)",
        "SELECT MAX(fetched_at) as last_sync, COUNT(*) as cnt FROM slack_threads WHERE channel_name IN ('compute-platform','compute-platform-warn','compute-platform-info','wx-dev','temporal-dev','temporalio-cloud','wx-users','g4-users','jobs-users','temporal','temporal-users','sig-compute')",
        600,  # expected interval: 10 min
    ),
    "slack_full": (
        "Slack (full — all channels)",
        "SELECT MAX(fetched_at) as last_sync, COUNT(*) as cnt FROM slack_threads",
        86400,  # expected interval: 24h
    ),
    "pagerduty_live": (
        "PagerDuty (live)",
        "SELECT MAX(fetched_at) as last_sync, COUNT(*) as cnt FROM pagerduty_incidents",
        1800,  # heartbeat collector updates ~every 30 min
    ),
}


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(db: AsyncSession = Depends(get_db)):
    """Get status of all sync sources — combines sync_state table with live data freshness checks."""
    result = await db.execute(text("""
        SELECT source_name, last_sync, record_count, sync_metadata, updated_at
        FROM sync_state
        ORDER BY source_name
    """))
    rows = result.fetchall()

    now = datetime.now(timezone.utc)
    sources = []

    for row in rows:
        last_sync = row.last_sync
        staleness = None
        relative = None

        if last_sync:
            if last_sync.tzinfo is None:
                last_sync = last_sync.replace(tzinfo=timezone.utc)
            staleness = (now - last_sync).total_seconds()
            relative = _relative_time(last_sync)

        source_name = row.source_name
        is_syncing = source_name in _running_syncs and _running_syncs[source_name].poll() is None

        sources.append(SyncSourceStatus(
            source_name=source_name,
            last_sync=last_sync.isoformat() if last_sync else None,
            last_sync_relative=relative,
            record_count=row.record_count,
            status=_staleness_status(staleness),
            staleness_seconds=staleness,
            sync_metadata=row.sync_metadata if row.sync_metadata else None,
            is_syncing=is_syncing,
        ))

    # Add live freshness sources that bypass sync_state
    for key, (display_name, query, expected_interval) in LIVE_FRESHNESS_SOURCES.items():
        try:
            result = await db.execute(text(query))
            row = result.fetchone()
            if row and row.last_sync:
                last_sync = row.last_sync
                if last_sync.tzinfo is None:
                    last_sync = last_sync.replace(tzinfo=timezone.utc)
                staleness = (now - last_sync).total_seconds()
                is_syncing = key in _running_syncs and _running_syncs[key].poll() is None
                sources.append(SyncSourceStatus(
                    source_name=display_name,
                    last_sync=last_sync.isoformat(),
                    last_sync_relative=_relative_time(last_sync),
                    record_count=row.cnt,
                    status="green" if staleness < expected_interval * 2 else _staleness_status(staleness),
                    staleness_seconds=staleness,
                    is_syncing=is_syncing,
                ))
        except Exception as e:
            logger.warning(f"Failed to check live freshness for {key}: {e}")

    # Sort: live sources first (they're most actionable), then sync_state sources
    sources.sort(key=lambda s: (s.staleness_seconds or 0))

    return SyncStatusResponse(
        sources=sources,
        timestamp=now.isoformat(),
    )


@router.post("/trigger/{source}", response_model=SyncTriggerResponse)
async def trigger_sync(source: str):
    """Trigger a sync for the given source. Runs in background."""
    # Clean up completed processes
    for key in list(_running_syncs.keys()):
        if _running_syncs[key].poll() is not None:
            del _running_syncs[key]

    # Check if already running
    if source in _running_syncs and _running_syncs[source].poll() is None:
        return SyncTriggerResponse(
            source=source,
            status="already_running",
            message=f"Sync for {source} is already running (pid {_running_syncs[source].pid})",
        )

    # Find the command
    cmd = SYNC_COMMANDS.get(source)
    if not cmd:
        return SyncTriggerResponse(
            source=source,
            status="error",
            message=f"Unknown sync source: {source}. Valid: {', '.join(SYNC_COMMANDS.keys())}",
        )

    # Ensure log directory exists
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"sync-{source}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"

    try:
        with open(log_file, "w") as lf:
            proc = subprocess.Popen(
                cmd,
                stdout=lf,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                start_new_session=True,
            )
        _running_syncs[source] = proc
        logger.info(f"Started sync for {source}: pid={proc.pid}, log={log_file}")
        return SyncTriggerResponse(
            source=source,
            status="started",
            message=f"Sync started (pid {proc.pid}), logging to {log_file.name}",
        )
    except Exception as e:
        logger.error(f"Failed to start sync for {source}: {e}")
        return SyncTriggerResponse(
            source=source,
            status="error",
            message=f"Failed to start sync: {str(e)}",
        )


@router.get("/logs/{source}", response_model=SyncLogsResponse)
async def get_sync_logs(source: str, lines: int = 100):
    """Get recent sync logs for a source from the logs directory."""
    log_files = sorted(LOGS_DIR.glob(f"sync-{source}-*.log"), reverse=True)

    # Also check for known log file patterns
    alt_patterns = {
        "slack_fast": ["slack-fast.log"],
        "full_sync": ["sync-*.log"],
    }
    if source in alt_patterns:
        for pattern in alt_patterns[source]:
            alt_files = sorted(LOGS_DIR.glob(pattern), reverse=True)
            log_files = list(log_files) + list(alt_files)

    if not log_files:
        return SyncLogsResponse(source=source, logs=["No log files found."])

    # Read the most recent log file
    latest = log_files[0]
    try:
        content = latest.read_text(encoding="utf-8", errors="replace")
        log_lines = content.strip().split("\n")
        # Return last N lines
        return SyncLogsResponse(
            source=source,
            logs=log_lines[-lines:],
            log_file=latest.name,
        )
    except Exception as e:
        return SyncLogsResponse(
            source=source,
            logs=[f"Error reading log: {str(e)}"],
            log_file=str(latest),
        )
