"""Service Health Dashboard API — Green/Yellow/Orange/Red alerting status by service."""

import logging
import re
import subprocess
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/service-health", tags=["service-health"])


# --- Team → Service mapping ---
# Maps PagerDuty service names to team groups, with a display name for each service.
# Services not in this map are grouped under "Other".

TEAM_SERVICES: dict[str, list[dict[str, str]]] = {
    "Compute": [
        {"pd_service": "G4", "display": "G4"},
        {"pd_service": "Jobs", "display": "Jobs"},
        {"pd_service": "WorkExchange", "display": "Work Exchange"},
        {"pd_service": "Temporal", "display": "Temporal"},
    ],
    "Hobbes": [
        {"pd_service": "Hobbes Pager", "display": "Hobbes Pager"},
        {"pd_service": "Hobbes High Urgency", "display": "Hobbes High"},
        {"pd_service": "Hobbes Low Urgency", "display": "Hobbes Low"},
        {"pd_service": "Hobbes Low Urgency via StackDriver", "display": "Hobbes StackDriver"},
    ],
    "Data Pipeline": [
        {"pd_service": "Data Pipeline", "display": "Data Pipeline"},
        {"pd_service": "Data Layer Registry", "display": "Data Layer Registry"},
        {"pd_service": "Pipeline Storage email", "display": "Pipeline Storage"},
        {"pd_service": "Pelican Pipeline", "display": "Pelican Pipeline"},
    ],
    "Discovery & Delivery": [
        {"pd_service": "Discovery and Delivery Catch All", "display": "DnD Catch All"},
        {"pd_service": "Iris Subscriptions - Discovery and Delivery", "display": "Iris Subscriptions"},
        {"pd_service": "Ordersv2 - Discovery and Delivery", "display": "OrdersV2"},
        {"pd_service": "Ordersv2 - Low Urgency", "display": "OrdersV2 Low"},
        {"pd_service": "Destinations Manager", "display": "Destinations Manager"},
        {"pd_service": "Subscriptions API Low Urgency", "display": "Subscriptions API"},
        {"pd_service": "fair-queue", "display": "Fair Queue"},
    ],
    "Ground Stations": [
        {"pd_service": "Ground Stations Icinga High", "display": "GS Icinga High"},
        {"pd_service": "Ground Stations Low Priority", "display": "GS Low Priority"},
    ],
    "SatOps / Missions": [
        {"pd_service": "Wake up, SatOps!", "display": "SatOps"},
        {"pd_service": "Datadog-Missions-Fix-Now", "display": "Missions Fix Now"},
        {"pd_service": "Datadog-Missions-Fix-Tomorrow", "display": "Missions Fix Tomorrow"},
        {"pd_service": "SuperDove MissionOps Latency", "display": "MissionOps Latency"},
    ],
    "SkySat": [
        {"pd_service": "SkySat Autobot", "display": "SkySat Autobot"},
        {"pd_service": "SkySat Nox Critical", "display": "SkySat Critical"},
        {"pd_service": "SkySat Nox Major", "display": "SkySat Major"},
        {"pd_service": "SkySat Nox Minor", "display": "SkySat Minor"},
    ],
    "Orbits": [
        {"pd_service": "Datadog-Orbits-Fix-Now", "display": "Orbits Fix Now"},
        {"pd_service": "Orbits wake up on-call", "display": "Orbits On-Call"},
        {"pd_service": "Flock Conjunction Response", "display": "Flock Conjunction"},
    ],
    "Fusion / Tardis": [
        {"pd_service": "Fusion Production Error", "display": "Fusion"},
    ],
    "Planetary Variables": [
        {"pd_service": "PV - Matcher", "display": "PV Matcher"},
        {"pd_service": "PV - Sentinel Processing", "display": "PV Sentinel"},
        {"pd_service": "Tile-based", "display": "Tile-based"},
        {"pd_service": "Field-based", "display": "Field-based"},
        {"pd_service": "Crop Biomass", "display": "Crop Biomass"},
    ],
    "DII / CDP": [
        {"pd_service": "planet-cdp - Fix Now", "display": "CDP Fix Now"},
        {"pd_service": "planet-cdp - Fix Later", "display": "CDP Fix Later"},
        {"pd_service": "planet-cdp - Customer Support", "display": "CDP Support"},
    ],
    "Tasking": [
        {"pd_service": "Tasking API", "display": "Tasking API"},
        {"pd_service": "Grafana integration Tasking team", "display": "Tasking Grafana"},
    ],
    "Security": [
        {"pd_service": "Security - Critical Incident", "display": "Security Critical"},
        {"pd_service": "Security - High incident", "display": "Security High"},
    ],
    "CorpEng": [
        {"pd_service": "CORPENG - Critical", "display": "CorpEng Critical"},
        {"pd_service": "SignalFX - Infra - High Priority", "display": "SignalFX High"},
        {"pd_service": "SignalFX - Infra - Low Priority", "display": "SignalFX Low"},
    ],
    "CSS": [
        {"pd_service": "CSS team", "display": "CSS"},
        {"pd_service": "Account", "display": "Account"},
        {"pd_service": "AdminV3", "display": "AdminV3"},
        {"pd_service": "Reports API", "display": "Reports API"},
    ],
    "SIF / Applied ML": [
        {"pd_service": "SIF", "display": "SIF"},
        {"pd_service": "SIF - Applied ML", "display": "Applied ML"},
        {"pd_service": "SIF - Low Urgency", "display": "SIF Low"},
    ],
    "Retention / RET": [
        {"pd_service": "RET Airflow", "display": "RET Airflow"},
        {"pd_service": "RET PU Processor", "display": "RET PU Processor"},
        {"pd_service": "RET PUDB", "display": "RET PUDB"},
    ],
    "Pelican / Tanager": [
        {"pd_service": "Pelican Shutter Control", "display": "Pelican Shutter"},
    ],
}


class ServiceStatus(BaseModel):
    service_name: str
    display_name: str
    team: str
    # Counts
    total_alerts: int = 0         # total defined alert rules for this service
    green_count: int = 0          # not firing (resolved within lookback)
    yellow_count: int = 0         # low urgency, resolved or acknowledged
    orange_count: int = 0         # high urgency acknowledged (not triggered)
    red_count: int = 0            # high urgency triggered (active incident)
    # Status
    status: str = "green"         # green/yellow/orange/red
    prodissue: Optional[str] = None  # active PRODISSUE key if any
    prodissue_title: Optional[str] = None
    # On-call (from active incidents)
    assigned_to: Optional[str] = None  # current assignee name


class TeamGroup(BaseModel):
    team: str
    status: str = "green"         # worst status of any service in team
    services: list[ServiceStatus] = []


class ServiceHealthResponse(BaseModel):
    timestamp: str
    overall_status: str = "green"
    teams: list[TeamGroup] = []
    active_prodissues: list[dict] = []
    summary: dict = {}


def _build_service_lookup() -> dict[str, tuple[str, str]]:
    """Build pd_service_name -> (team, display_name) lookup."""
    lookup = {}
    for team, services in TEAM_SERVICES.items():
        for svc in services:
            lookup[svc["pd_service"]] = (team, svc["display"])
    return lookup


STATUS_RANK = {"green": 0, "yellow": 1, "orange": 2, "red": 3}


def _worst_status(*statuses: str) -> str:
    return max(statuses, key=lambda s: STATUS_RANK.get(s, 0))


class SlackContext(BaseModel):
    """Rich context extracted from related Slack threads."""
    url: str
    channel: Optional[str] = None
    participant_count: int = 0
    message_count: int = 0
    participants: list[str] = []
    title: Optional[str] = None
    summary: Optional[str] = None
    has_working_plan: bool = False
    has_impact_assessment: bool = False
    has_resolution_eta: bool = False
    related_jira_keys: list[str] = []
    related_channels: list[str] = []


class IncidentDetail(BaseModel):
    incident_id: str
    title: str
    description: Optional[str] = None
    status: str
    urgency: str
    priority: Optional[str] = None
    triggered_at: str
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    duration_seconds: int = 0
    assigned_to: Optional[str] = None
    acknowledged_by: Optional[str] = None
    pd_url: Optional[str] = None
    # Extracted references (populated by incident_spider_enrichment + fallback)
    prodissue_key: Optional[str] = None  # e.g. PRODISSUE-1417
    jira_keys: list[str] = []
    slack_refs: list[str] = []
    slack_contexts: list[SlackContext] = []  # rich slack thread data
    gitlab_refs: list[str] = []
    grafana_refs: list[str] = []


class ServiceDetailResponse(BaseModel):
    service_name: str
    display_name: str
    team: str
    status: str
    incidents: list[IncidentDetail] = []
    summary: dict = {}


def _extract_name_from_jsonb(data) -> Optional[str]:
    """Extract a human-readable name from PD assigned_to / acknowledgements JSONB."""
    if not data:
        return None
    if isinstance(data, str):
        import json as _json
        try:
            data = _json.loads(data)
        except Exception:
            return None
    if isinstance(data, list) and len(data) > 0:
        first = data[0]
        if isinstance(first, dict):
            # Try acknowledgements format: {acknowledger: {summary: "Name"}}
            for key in ("acknowledger", "assignee"):
                obj = first.get(key, {})
                if isinstance(obj, dict):
                    name = obj.get("summary") or obj.get("name")
                    if name:
                        return name
            # Flat format
            return first.get("summary") or first.get("name") or first.get("id")
    if isinstance(data, dict):
        return data.get("summary") or data.get("name") or data.get("id")
    return None


def _extract_references(title: str, description: str = "") -> dict:
    """Extract JIRA keys, PRODISSUE keys, and slack refs from incident text."""
    import re
    text = f"{title} {description or ''}"
    prodissue = None
    jira_keys = []
    slack_refs = []
    prodissue_match = re.search(r"(PRODISSUE-\d+)", text)
    if prodissue_match:
        prodissue = prodissue_match.group(1)
    jira_matches = re.findall(r"([A-Z]{2,}-\d+)", text)
    jira_keys = list(dict.fromkeys(k for k in jira_matches if k != prodissue))
    slack_matches = re.findall(r"(https?://planetlabs\.slack\.com/[^\s\]>)]+)", text)
    slack_refs = list(dict.fromkeys(slack_matches))
    return {"prodissue_key": prodissue, "jira_keys": jira_keys, "slack_refs": slack_refs}


async def _resolve_channel_name(db, channel_id: str) -> str:
    """Resolve a Slack channel ID to its name."""
    result = await db.execute(text(
        "SELECT channel_name FROM alert_channels WHERE channel_id = :cid LIMIT 1"
    ), {"cid": channel_id})
    row = result.first()
    if row:
        return row.channel_name
    # Fallback: check slack_threads
    result = await db.execute(text(
        "SELECT DISTINCT channel_name FROM slack_threads WHERE channel_id = :cid LIMIT 1"
    ), {"cid": channel_id})
    row = result.first()
    return row.channel_name if row else channel_id


async def _enrich_slack_context(db, slack_urls: list[str]) -> list[dict]:
    """Look up Slack threads by URL and extract rich context."""
    contexts = []
    for url in slack_urls:
        import re
        ts_match = re.search(r"/p(\d{10})(\d+)", url)
        channel_match = re.search(r"/archives/([A-Z0-9]+)/", url)

        # Resolve channel name
        channel_name = None
        if channel_match:
            channel_name = await _resolve_channel_name(db, channel_match.group(1))

        if not ts_match:
            contexts.append({"url": url, "channel": channel_name})
            continue

        raw_ts = ts_match.group(1) + "." + ts_match.group(2)

        result = await db.execute(text("""
            SELECT channel_name, title, summary_text, participant_count, message_count,
                   participants, jira_keys, cross_channel_refs, messages
            FROM slack_threads
            WHERE thread_ts = :ts OR thread_ts LIKE :ts_prefix
            LIMIT 1
        """), {"ts": raw_ts, "ts_prefix": f"{ts_match.group(1)}%"})
        row = result.first()

        ctx: dict = {"url": url, "channel": channel_name}

        if row:
            ctx["channel"] = row.channel_name
            ctx["title"] = row.title[:200] if row.title else None
            ctx["summary"] = row.summary_text[:500] if row.summary_text else None
            ctx["participant_count"] = row.participant_count or 0
            ctx["message_count"] = row.message_count or 0

            # Participants
            participants = row.participants
            if isinstance(participants, str):
                import json as _json
                try:
                    participants = _json.loads(participants)
                except Exception:
                    participants = []
            ctx["participants"] = participants if isinstance(participants, list) else []

            # Related JIRA keys from thread
            jira_keys = row.jira_keys
            if isinstance(jira_keys, str):
                try:
                    jira_keys = _json.loads(jira_keys)
                except Exception:
                    jira_keys = []
            ctx["related_jira_keys"] = jira_keys if isinstance(jira_keys, list) else []

            # Cross-channel refs
            cross_refs = row.cross_channel_refs
            if isinstance(cross_refs, str):
                try:
                    cross_refs = _json.loads(cross_refs)
                except Exception:
                    cross_refs = []
            ctx["related_channels"] = cross_refs if isinstance(cross_refs, list) else []

            # Scan messages for plan/impact/ETA signals
            messages_text = ""
            if row.messages:
                msgs = row.messages
                if isinstance(msgs, str):
                    try:
                        msgs = _json.loads(msgs)
                    except Exception:
                        msgs = []
                if isinstance(msgs, list):
                    messages_text = " ".join(
                        m.get("text", "") if isinstance(m, dict) else str(m) for m in msgs
                    ).lower()

            combined_text = f"{ctx.get('summary', '') or ''} {messages_text}".lower()
            ctx["has_working_plan"] = any(kw in combined_text for kw in [
                "plan is", "working on", "fix is", "deploying", "rolling out",
                "workaround", "mitigation", "next steps", "action items",
            ])
            ctx["has_impact_assessment"] = any(kw in combined_text for kw in [
                "impact", "affected", "customers impacted", "blast radius",
                "severity", "customer impact", "revenue impact",
            ])
            ctx["has_resolution_eta"] = any(kw in combined_text for kw in [
                "eta", "expected", "should be resolved", "will be fixed",
                "timeline", "by eod", "by end of", "hours to fix",
            ])

        contexts.append(ctx)

    return contexts


async def _enrich_from_jira(db, prodissue_key: str) -> dict:
    """Look up PRODISSUE in JIRA and extract refs from its description."""
    if not prodissue_key:
        return {"jira_keys": [], "slack_refs": [], "jira_description": None}
    result = await db.execute(text(
        "SELECT description FROM jira_issues WHERE external_key = :key"
    ), {"key": prodissue_key})
    row = result.first()
    if not row or not row.description:
        return {"jira_keys": [], "slack_refs": [], "jira_description": None}
    refs = _extract_references("", row.description)
    return {
        "jira_keys": refs["jira_keys"],
        "slack_refs": refs["slack_refs"],
        "jira_description": row.description[:500] if row.description else None,
    }


@router.get("/service/{service_name}", response_model=ServiceDetailResponse)
async def get_service_detail(
    service_name: str,
    hours: int = Query(default=24, le=168),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed incident list for a specific PagerDuty service."""
    now = datetime.utcnow()
    lookback = now - timedelta(hours=hours)
    service_lookup = _build_service_lookup()

    team, display = service_lookup.get(service_name, ("Other", service_name))

    result = await db.execute(text("""
        SELECT
            id,
            external_incident_id,
            title,
            description,
            status,
            urgency,
            priority,
            triggered_at,
            acknowledged_at,
            resolved_at,
            assigned_to,
            acknowledgements,
            pd_url
        FROM pagerduty_incidents
        WHERE service_name = :svc
          AND (triggered_at >= :lookback OR status IN ('triggered', 'acknowledged'))
        ORDER BY
            CASE status
                WHEN 'triggered' THEN 0
                WHEN 'acknowledged' THEN 1
                ELSE 2
            END,
            triggered_at DESC
    """), {"svc": service_name, "lookback": lookback})
    rows = result.fetchall()

    incidents: list[IncidentDetail] = []
    for r in rows:
        triggered = r.triggered_at
        end_time = r.resolved_at or now
        if hasattr(triggered, "timestamp") and hasattr(end_time, "timestamp"):
            duration = int(end_time.timestamp() - triggered.timestamp())
        else:
            duration = 0

        acked_by = _extract_name_from_jsonb(r.acknowledgements)
        assigned = _extract_name_from_jsonb(r.assigned_to)
        refs = _extract_references(r.title or "", r.description or "")

        # Enrich from EntityLinks (populated by incident_spider_enrichment job)
        jira_keys = refs.get("jira_keys", [])
        slack_refs = refs.get("slack_refs", [])
        gitlab_refs = []
        grafana_refs = []

        # Look up EntityLinks from this PD incident
        link_result = await db.execute(text("""
            SELECT to_type, to_id FROM entity_links
            WHERE from_type = 'pagerduty_incident' AND from_id = :pd_id
        """), {"pd_id": str(r.id) if r.id else ""})

        # EntityLinks are sparse until spider runs — currently just check for them
        # (links will be populated by incident_spider_enrichment background job)
        for link in link_result.fetchall():
            pass  # Future: resolve to_id → display values

        # Fallback: always do query-time enrichment from JIRA for now
        if refs.get("prodissue_key"):
            jira_enrichment = await _enrich_from_jira(db, refs["prodissue_key"])
            jira_keys = list(dict.fromkeys(jira_keys + jira_enrichment.get("jira_keys", [])))
            slack_refs = list(dict.fromkeys(slack_refs + jira_enrichment.get("slack_refs", [])))

        # Enrich Slack refs with thread context
        slack_contexts = []
        if slack_refs:
            slack_contexts_raw = await _enrich_slack_context(db, slack_refs)
            slack_contexts = [SlackContext(**ctx) for ctx in slack_contexts_raw]

        incidents.append(IncidentDetail(
            incident_id=r.external_incident_id or "",
            title=r.title or "",
            description=r.description if r.description and r.description != r.title else None,
            status=r.status or "unknown",
            urgency=r.urgency or "low",
            priority=r.priority if r.priority else None,
            triggered_at=r.triggered_at.isoformat() if r.triggered_at else "",
            acknowledged_at=r.acknowledged_at.isoformat() if r.acknowledged_at else None,
            resolved_at=r.resolved_at.isoformat() if r.resolved_at else None,
            duration_seconds=max(0, duration),
            assigned_to=assigned,
            acknowledged_by=acked_by,
            pd_url=r.pd_url,
            prodissue_key=refs.get("prodissue_key"),
            jira_keys=jira_keys,
            slack_refs=slack_refs,
            slack_contexts=slack_contexts,
            gitlab_refs=gitlab_refs,
            grafana_refs=grafana_refs,
        ))

    # Summary
    active = [i for i in incidents if i.status in ("triggered", "acknowledged")]
    resolved = [i for i in incidents if i.status == "resolved"]
    p1 = sum(1 for i in incidents if i.priority and i.priority.startswith("P1"))
    p2 = sum(1 for i in incidents if i.priority and i.priority.startswith("P2"))
    p3 = sum(1 for i in incidents if i.priority and i.priority.startswith("P3"))
    high = sum(1 for i in incidents if i.urgency == "high")
    low = sum(1 for i in incidents if i.urgency == "low")

    svc_status = "green"
    if any(i.status == "triggered" and i.urgency == "high" for i in incidents):
        svc_status = "red"
    elif any(i.status == "acknowledged" and i.urgency == "high" for i in incidents):
        svc_status = "orange"
    elif any(i.status in ("triggered", "acknowledged") for i in incidents):
        svc_status = "yellow"

    return ServiceDetailResponse(
        service_name=service_name,
        display_name=display,
        team=team,
        status=svc_status,
        incidents=incidents,
        summary={
            "total": len(incidents),
            "active": len(active),
            "resolved": len(resolved),
            "triggered": sum(1 for i in active if i.status == "triggered"),
            "acknowledged": sum(1 for i in active if i.status == "acknowledged"),
            "high_urgency": high,
            "low_urgency": low,
            "p1": p1,
            "p2": p2,
            "p3": p3,
        },
    )


@router.get("", response_model=ServiceHealthResponse)
async def get_service_health(
    hours: int = Query(default=24, le=168, description="Lookback window in hours"),
    db: AsyncSession = Depends(get_db),
):
    """Get service health matrix with green/yellow/orange/red grading."""
    now = datetime.utcnow()
    lookback = now - timedelta(hours=hours)
    service_lookup = _build_service_lookup()

    # 1. Get PagerDuty incident counts by service, status, urgency
    result = await db.execute(text("""
        SELECT
            service_name,
            status,
            urgency,
            COUNT(*) as cnt
        FROM pagerduty_incidents
        WHERE triggered_at >= :lookback
           OR status IN ('triggered', 'acknowledged')
        GROUP BY service_name, status, urgency
        ORDER BY service_name
    """), {"lookback": lookback})
    pd_rows = result.fetchall()

    # 1b. Get current assignees for active incidents (for on-call display)
    result = await db.execute(text("""
        SELECT service_name, assigned_to
        FROM pagerduty_incidents
        WHERE status IN ('triggered', 'acknowledged')
          AND assigned_to IS NOT NULL
        ORDER BY triggered_at DESC
    """))
    active_assignees: dict[str, str] = {}
    for row in result.fetchall():
        if row.service_name not in active_assignees:
            name = _extract_name_from_jsonb(row.assigned_to)
            if name:
                active_assignees[row.service_name] = name

    # 2. Get Grafana alert definition counts by team (for total alert counts)
    result = await db.execute(text("""
        SELECT
            COALESCE(team, 'unknown') as team,
            COUNT(*) as cnt
        FROM grafana_alert_definitions
        GROUP BY team
    """))
    grafana_counts = {row.team: row.cnt for row in result.fetchall()}

    # 3. Get active PRODISSUEs
    result = await db.execute(text("""
        SELECT external_key, title, status
        FROM jira_issues
        WHERE external_key LIKE 'PRODISSUE%%'
          AND status NOT IN ('Closed', 'Done', 'Resolved')
        ORDER BY created_at DESC
    """))
    prodissue_rows = result.fetchall()
    active_prodissues = [
        {"key": r.external_key, "title": r.title, "status": r.status}
        for r in prodissue_rows
    ]

    # Build per-service incident aggregation
    service_incidents: dict[str, dict] = {}
    for row in pd_rows:
        svc = row.service_name
        if svc not in service_incidents:
            service_incidents[svc] = {
                "triggered_high": 0,
                "triggered_low": 0,
                "acknowledged_high": 0,
                "acknowledged_low": 0,
                "resolved_high": 0,
                "resolved_low": 0,
                "total": 0,
            }
        key = f"{row.status}_{row.urgency}"
        service_incidents[svc][key] = service_incidents[svc].get(key, 0) + row.cnt
        service_incidents[svc]["total"] += row.cnt

    # Build team → services structure
    team_map: dict[str, list[ServiceStatus]] = {}

    # Process known services
    for pd_name, (team, display) in service_lookup.items():
        incidents = service_incidents.get(pd_name, {})
        total = incidents.get("total", 0)

        red = incidents.get("triggered_high", 0)
        orange = incidents.get("acknowledged_high", 0)
        yellow = (
            incidents.get("triggered_low", 0)
            + incidents.get("acknowledged_low", 0)
            + incidents.get("resolved_low", 0)
        )
        green = total - red - orange - yellow
        if green < 0:
            green = 0

        if red > 0:
            status = "red"
        elif orange > 0:
            status = "orange"
        elif yellow > 0:
            status = "yellow"
        else:
            status = "green"

        svc_status = ServiceStatus(
            service_name=pd_name,
            display_name=display,
            team=team,
            total_alerts=total,
            green_count=green,
            yellow_count=yellow,
            orange_count=orange,
            red_count=red,
            status=status,
            assigned_to=active_assignees.get(pd_name),
        )

        if team not in team_map:
            team_map[team] = []
        team_map[team].append(svc_status)

    # Add any unknown services under "Other"
    for svc, incidents in service_incidents.items():
        if svc not in service_lookup:
            total = incidents.get("total", 0)
            red = incidents.get("triggered_high", 0)
            orange = incidents.get("acknowledged_high", 0)
            yellow = (
                incidents.get("triggered_low", 0)
                + incidents.get("acknowledged_low", 0)
                + incidents.get("resolved_low", 0)
            )
            green = max(0, total - red - orange - yellow)

            if red > 0:
                status = "red"
            elif orange > 0:
                status = "orange"
            elif yellow > 0:
                status = "yellow"
            else:
                status = "green"

            svc_status = ServiceStatus(
                service_name=svc,
                display_name=svc,
                team="Other",
                total_alerts=total,
                green_count=green,
                yellow_count=yellow,
                orange_count=orange,
                red_count=red,
                status=status,
            )
            if "Other" not in team_map:
                team_map["Other"] = []
            team_map["Other"].append(svc_status)

    # Build team groups
    # Define team ordering (Compute first, then upstream, downstream, other)
    team_order = [
        "Compute", "Hobbes", "Data Pipeline", "Ground Stations",
        "SatOps / Missions", "Orbits", "SkySat", "Tasking",
        "Discovery & Delivery", "DII / CDP", "Planetary Variables",
        "Fusion / Tardis", "SIF / Applied ML", "Pelican / Tanager",
        "Retention / RET", "CorpEng", "Security", "CSS", "Other",
    ]

    teams: list[TeamGroup] = []
    for team_name in team_order:
        services = team_map.get(team_name, [])
        if not services:
            continue
        # Sort services within team by status severity (worst first)
        services.sort(key=lambda s: -STATUS_RANK.get(s.status, 0))
        team_status = "green"
        for s in services:
            team_status = _worst_status(team_status, s.status)
        teams.append(TeamGroup(
            team=team_name,
            status=team_status,
            services=services,
        ))

    # Add any teams not in the order list
    for team_name, services in team_map.items():
        if team_name not in team_order:
            services.sort(key=lambda s: -STATUS_RANK.get(s.status, 0))
            team_status = "green"
            for s in services:
                team_status = _worst_status(team_status, s.status)
            teams.append(TeamGroup(
                team=team_name,
                status=team_status,
                services=services,
            ))

    overall = "green"
    for t in teams:
        overall = _worst_status(overall, t.status)

    # Summary stats
    total_services = sum(len(t.services) for t in teams)
    total_green = sum(1 for t in teams for s in t.services if s.status == "green")
    total_yellow = sum(1 for t in teams for s in t.services if s.status == "yellow")
    total_orange = sum(1 for t in teams for s in t.services if s.status == "orange")
    total_red = sum(1 for t in teams for s in t.services if s.status == "red")

    return ServiceHealthResponse(
        timestamp=now.isoformat(),
        overall_status=overall,
        teams=teams,
        active_prodissues=active_prodissues,
        summary={
            "total_services": total_services,
            "green": total_green,
            "yellow": total_yellow,
            "orange": total_orange,
            "red": total_red,
            "active_prodissues": len(active_prodissues),
            "grafana_alert_definitions": sum(grafana_counts.values()),
            "lookback_hours": hours,
        },
    )


# ── Real-time Slack thread analysis ──

class SlackThreadAnalysis(BaseModel):
    """Lazy-loaded analysis of a Slack thread."""
    url: str
    channel: str = ""
    messages: list[dict] = []
    participants: list[str] = []
    participant_count: int = 0
    message_count: int = 0
    jira_keys: list[str] = []
    slack_refs: list[str] = []
    has_working_plan: bool = False
    has_impact_assessment: bool = False
    has_resolution_eta: bool = False
    plan_snippets: list[str] = []
    impact_snippets: list[str] = []
    eta_snippets: list[str] = []
    error: Optional[str] = None


def _get_slack_token() -> Optional[str]:
    """Load Slack token from Keychain."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "slack-api-token", "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    # Fallback to config file
    try:
        import json as _json
        from pathlib import Path
        with open(Path.home() / "tools" / "slack" / "slack-config.json") as f:
            return _json.loads(f.read()).get("token")
    except Exception:
        return None


@router.get("/slack-thread-analysis")
async def analyze_slack_thread(url: str = Query(...), db: AsyncSession = Depends(get_db)):
    """Fetch and analyze a Slack thread in real-time.

    Extracts: participants, JIRA keys, plan/impact/ETA signals with snippets.
    """
    import json as _json

    # Parse URL
    channel_match = re.search(r"/archives/([A-Z0-9]+)/", url)
    ts_match = re.search(r"/p(\d{10})(\d+)", url)

    if not channel_match or not ts_match:
        return SlackThreadAnalysis(url=url, error="Could not parse Slack URL")

    channel_id = channel_match.group(1)
    thread_ts = f"{ts_match.group(1)}.{ts_match.group(2)}"

    # Resolve channel name
    channel_name = await _resolve_channel_name(db, channel_id)

    # Fetch thread from Slack API
    token = _get_slack_token()
    if not token:
        return SlackThreadAnalysis(url=url, channel=channel_name, error="No Slack token")

    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://slack.com/api/conversations.replies?channel={channel_id}&ts={thread_ts}&limit=100",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read())

        if not data.get("ok"):
            return SlackThreadAnalysis(url=url, channel=channel_name, error=data.get("error", "API error"))

        messages = data.get("messages", [])

    except Exception as e:
        logger.warning(f"Slack API error for {url}: {e}")
        return SlackThreadAnalysis(url=url, channel=channel_name, error=str(e))

    # Extract participants
    user_ids = list(dict.fromkeys(m.get("user", "") for m in messages if m.get("user")))

    # Resolve user names (batch lookup)
    user_names = []
    for uid in user_ids[:20]:
        try:
            req = urllib.request.Request(
                f"https://slack.com/api/users.info?user={uid}",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                udata = _json.loads(resp.read())
            if udata.get("ok"):
                profile = udata["user"].get("profile", {})
                name = profile.get("real_name") or udata["user"].get("name", uid)
                user_names.append(name)
        except Exception:
            user_names.append(uid)

    # Combine message text
    all_text = "\n".join(m.get("text", "") for m in messages)
    all_text_lower = all_text.lower()

    # Extract references
    jira_keys = list(dict.fromkeys(re.findall(r"\b([A-Z]{2,}-\d+)\b", all_text)))
    slack_links = list(dict.fromkeys(re.findall(r"(https?://planetlabs\.slack\.com/[^\s>]+)", all_text)))

    # Signal detection with snippet extraction
    plan_keywords = ["plan is", "working on", "fix is", "deploying", "rolling out",
                     "workaround", "mitigation", "next steps", "action items", "will deploy"]
    impact_keywords = ["impact", "affected", "customers impacted", "blast radius",
                       "customer impact", "revenue impact", "users affected", "outage"]
    eta_keywords = ["eta", "expected", "should be resolved", "will be fixed",
                    "timeline", "by eod", "by end of", "hours to fix", "minutes to"]

    def _extract_summaries(keywords: list[str], label: str) -> list[str]:
        """Extract full sentences containing keywords, cleaned into summaries."""
        summaries = []
        for msg_text in (m.get("text", "") for m in messages):
            msg_lower = msg_text.lower()
            for kw in keywords:
                if kw in msg_lower:
                    # Find the sentence containing the keyword
                    idx = msg_lower.index(kw)
                    # Walk back to sentence start (. ! ? or start of message)
                    start = idx
                    while start > 0 and msg_text[start - 1] not in ".!?\n":
                        start -= 1
                    # Walk forward to sentence end
                    end = idx + len(kw)
                    while end < len(msg_text) and msg_text[end] not in ".!?\n":
                        end += 1
                    sentence = msg_text[start:end + 1].strip().strip("•-*> ")
                    # Clean up Slack formatting
                    sentence = re.sub(r"<[^>]+\|([^>]+)>", r"\1", sentence)  # <url|text> → text
                    sentence = re.sub(r"<[^>]+>", "", sentence)  # <url> → ""
                    sentence = re.sub(r"[*_~`]", "", sentence)  # bold/italic
                    sentence = sentence.strip()
                    if len(sentence) > 15 and sentence not in summaries:
                        # Truncate long sentences cleanly
                        if len(sentence) > 150:
                            sentence = sentence[:147].rsplit(" ", 1)[0] + "..."
                        summaries.append(sentence)
                        if len(summaries) >= 2:
                            return summaries
        return summaries

    has_plan = any(kw in all_text_lower for kw in plan_keywords)
    has_impact = any(kw in all_text_lower for kw in impact_keywords)
    has_eta = any(kw in all_text_lower for kw in eta_keywords)

    # AI-generated one-line summaries
    plan_summary = ""
    impact_summary = ""
    eta_summary = ""

    try:
        from anthropic import AnthropicVertex
        ai = AnthropicVertex(project_id="compute-meta", region="us-east5")

        # Build a concise thread summary for the LLM (last 30 messages, 3K chars max)
        thread_text = "\n".join(
            f"{user_names[user_ids.index(m['user'])] if m.get('user') in user_ids and user_ids.index(m['user']) < len(user_names) else '?'}: {m.get('text', '')[:200]}"
            for m in messages[-30:]
        )[:3000]

        resp = ai.messages.create(
            model="claude-3-5-haiku@20241022",
            max_tokens=200,
            messages=[{"role": "user", "content": f"""Analyze this incident Slack thread and give exactly 3 one-line assessments. Be specific and concise (under 15 words each). If info is missing, say "Not documented".

PLAN (what's being done to fix it):
IMPACT (who/what is affected):
ETA (when will it be resolved):

Thread:
{thread_text}"""}],
        )
        ai_text = resp.content[0].text
        for line in ai_text.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("PLAN"):
                plan_summary = line.split(":", 1)[-1].strip()
            elif line.upper().startswith("IMPACT"):
                impact_summary = line.split(":", 1)[-1].strip()
            elif line.upper().startswith("ETA"):
                eta_summary = line.split(":", 1)[-1].strip()
    except Exception as e:
        logger.warning(f"AI summarization failed: {e}")
        # Fall back to extracted sentences
        plan_summary = (_extract_summaries(plan_keywords, "plan") or ["Not documented"])[0]
        impact_summary = (_extract_summaries(impact_keywords, "impact") or ["Not documented"])[0]
        eta_summary = (_extract_summaries(eta_keywords, "eta") or ["Not documented"])[0]

    return SlackThreadAnalysis(
        url=url,
        channel=channel_name,
        messages=[{"user": user_names[user_ids.index(m["user"])] if m.get("user") in user_ids and user_ids.index(m["user"]) < len(user_names) else m.get("user", "?"),
                   "text": m.get("text", "")[:300],
                   "ts": m.get("ts", "")} for m in messages[:20]],
        participants=user_names,
        participant_count=len(user_names),
        message_count=len(messages),
        jira_keys=jira_keys,
        slack_refs=slack_links,
        has_working_plan=has_plan or bool(plan_summary and plan_summary != "Not documented"),
        has_impact_assessment=has_impact or bool(impact_summary and impact_summary != "Not documented"),
        has_resolution_eta=has_eta or bool(eta_summary and eta_summary != "Not documented"),
        plan_snippets=[plan_summary] if plan_summary else [],
        impact_snippets=[impact_summary] if impact_summary else [],
        eta_snippets=[eta_summary] if eta_summary else [],
    )
