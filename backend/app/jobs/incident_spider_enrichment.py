"""Background job for spidering PagerDuty incidents → JIRA → Slack/GitLab/Grafana.

Enrichment flow:
  PD incident title → extract JIRA keys (e.g. PRODISSUE-1417)
  → look up JIRA ticket description
  → extract Slack thread URLs, related JIRA keys, GitLab MR refs, Grafana dashboard links
  → create EntityLinks for each discovered reference

This enables the service health modal to show all related context
for any PD incident without query-time lookups.
"""

import logging
import re
from typing import Dict

from sqlalchemy import select, text

from app.database import async_session
from app.models import EntityLink, LinkType, LinkSourceType, LinkStatus

logger = logging.getLogger(__name__)

# Regex patterns for reference extraction
JIRA_KEY_RE = re.compile(r"\b([A-Z]{2,}-\d+)\b")
SLACK_URL_RE = re.compile(r"(https?://planetlabs\.slack\.com/archives/[^\s\]>)\"]+)")
GITLAB_MR_RE = re.compile(r"(https?://hello\.planet\.com/code/[^\s\]>)\"]+/-/merge_requests/\d+)")
GITLAB_URL_RE = re.compile(r"(https?://hello\.planet\.com/code/[^\s\]>)\"]+)")
GRAFANA_URL_RE = re.compile(r"(https?://planet\.grafana\.net/[^\s\]>)\"]+)")
PD_URL_RE = re.compile(r"(https?://planetlabs\.pagerduty\.com/incidents/[^\s\]>)\"]+)")


def _extract_all_refs(text: str) -> dict:
    """Extract all reference types from text."""
    if not text:
        return {"jira_keys": [], "slack_urls": [], "gitlab_urls": [], "grafana_urls": [], "pd_urls": []}

    return {
        "jira_keys": list(dict.fromkeys(JIRA_KEY_RE.findall(text))),
        "slack_urls": list(dict.fromkeys(SLACK_URL_RE.findall(text))),
        "gitlab_urls": list(dict.fromkeys(GITLAB_URL_RE.findall(text))),
        "grafana_urls": list(dict.fromkeys(GRAFANA_URL_RE.findall(text))),
        "pd_urls": list(dict.fromkeys(PD_URL_RE.findall(text))),
    }


async def spider_incident_references() -> Dict:
    """Spider from PD incidents outward through JIRA to find all related context.

    Level 0: PD incident title/description → extract JIRA keys
    Level 1: JIRA ticket description → extract Slack, GitLab, Grafana, more JIRA
    Level 2: Related JIRA tickets → extract more Slack/GitLab (one hop only)

    Creates EntityLinks:
        pagerduty_incident → references → jira_issue
        pagerduty_incident → references → slack_thread (via JIRA)
        jira_issue → references → jira_issue (related tickets)
    """
    try:
        async with async_session() as db:
            stats = {
                "pd_scanned": 0,
                "jira_looked_up": 0,
                "slack_refs_found": 0,
                "gitlab_refs_found": 0,
                "grafana_refs_found": 0,
                "jira_refs_found": 0,
                "links_created": 0,
                "errors": [],
            }

            logger.info("Starting incident spider enrichment")

            # Get active + recent PD incidents
            result = await db.execute(text("""
                SELECT id, external_incident_id, title, description, service_name
                FROM pagerduty_incidents
                WHERE status IN ('triggered', 'acknowledged')
                   OR triggered_at >= NOW() - INTERVAL '7 days'
                ORDER BY triggered_at DESC
                LIMIT 200
            """))
            incidents = result.fetchall()
            stats["pd_scanned"] = len(incidents)

            for inc in incidents:
                inc_id = str(inc.id)
                combined_text = f"{inc.title or ''} {inc.description or ''}"

                # Level 0: Extract JIRA keys from PD incident
                refs = _extract_all_refs(combined_text)
                jira_keys = refs["jira_keys"]

                if not jira_keys:
                    continue

                # Create PD → JIRA links
                for jira_key in jira_keys:
                    jira_result = await db.execute(text(
                        "SELECT id, description FROM jira_issues WHERE external_key = :key"
                    ), {"key": jira_key})
                    jira_row = jira_result.first()

                    if not jira_row:
                        continue

                    stats["jira_looked_up"] += 1
                    jira_id = str(jira_row.id)

                    # Link PD → JIRA
                    await _create_link_if_new(db, stats,
                        from_type="pagerduty_incident", from_id=inc_id,
                        to_type="jira_issue", to_id=jira_id,
                        link_type=LinkType.REFERENCES)

                    # Level 1: Spider JIRA description
                    jira_desc = jira_row.description or ""
                    jira_refs = _extract_all_refs(jira_desc)

                    # Slack refs from JIRA
                    for slack_url in jira_refs["slack_urls"]:
                        stats["slack_refs_found"] += 1
                        # Store as metadata on the PD → JIRA link (or create a direct ref)
                        # For now, store slack URLs as entity links from the JIRA issue
                        # Look up slack thread by URL
                        slack_result = await db.execute(text(
                            "SELECT id FROM slack_threads WHERE permalink LIKE :url_prefix LIMIT 1"
                        ), {"url_prefix": f"%{slack_url.split('/')[-1]}%"})
                        slack_row = slack_result.first()
                        if slack_row:
                            await _create_link_if_new(db, stats,
                                from_type="jira_issue", from_id=jira_id,
                                to_type="slack_thread", to_id=str(slack_row.id),
                                link_type=LinkType.DISCUSSED_IN)

                    # GitLab refs from JIRA
                    for gitlab_url in jira_refs["gitlab_urls"]:
                        stats["gitlab_refs_found"] += 1
                        # Try to match to a synced MR
                        mr_match = re.search(r"merge_requests/(\d+)", gitlab_url)
                        if mr_match:
                            mr_result = await db.execute(text(
                                "SELECT id FROM gitlab_merge_requests WHERE web_url LIKE :url LIMIT 1"
                            ), {"url": f"%{gitlab_url}%"})
                            mr_row = mr_result.first()
                            if mr_row:
                                await _create_link_if_new(db, stats,
                                    from_type="jira_issue", from_id=jira_id,
                                    to_type="gitlab_merge_request", to_id=str(mr_row.id),
                                    link_type=LinkType.REFERENCES)

                    # Grafana refs from JIRA
                    for grafana_url in jira_refs["grafana_urls"]:
                        stats["grafana_refs_found"] += 1
                        # Try to match to a synced alert definition
                        dash_match = re.search(r"/d/([^/?]+)", grafana_url)
                        if dash_match:
                            alert_result = await db.execute(text(
                                "SELECT id FROM grafana_alert_definitions LIMIT 0"
                            ))
                            # Grafana dashboard links are stored as metadata, not entity links
                            # TODO: create a grafana_dashboard entity type

                    # Level 1.5: Related JIRA keys from JIRA description
                    for related_key in jira_refs["jira_keys"]:
                        if related_key == jira_key:
                            continue
                        stats["jira_refs_found"] += 1

                        related_result = await db.execute(text(
                            "SELECT id, description FROM jira_issues WHERE external_key = :key"
                        ), {"key": related_key})
                        related_row = related_result.first()

                        if not related_row:
                            continue

                        related_id = str(related_row.id)

                        # Link JIRA → related JIRA
                        await _create_link_if_new(db, stats,
                            from_type="jira_issue", from_id=jira_id,
                            to_type="jira_issue", to_id=related_id,
                            link_type=LinkType.REFERENCES)

                        # Level 2: Spider related JIRA for more Slack refs
                        related_desc = related_row.description or ""
                        related_refs = _extract_all_refs(related_desc)

                        for slack_url in related_refs["slack_urls"]:
                            stats["slack_refs_found"] += 1
                            slack_result = await db.execute(text(
                                "SELECT id FROM slack_threads WHERE permalink LIKE :url_prefix LIMIT 1"
                            ), {"url_prefix": f"%{slack_url.split('/')[-1]}%"})
                            slack_row = slack_result.first()
                            if slack_row:
                                await _create_link_if_new(db, stats,
                                    from_type="jira_issue", from_id=related_id,
                                    to_type="slack_thread", to_id=str(slack_row.id),
                                    link_type=LinkType.DISCUSSED_IN)

            await db.commit()

            logger.info(
                f"Incident spider complete: {stats['pd_scanned']} PD scanned, "
                f"{stats['jira_looked_up']} JIRA looked up, "
                f"{stats['slack_refs_found']} Slack + {stats['gitlab_refs_found']} GitLab + "
                f"{stats['grafana_refs_found']} Grafana refs found, "
                f"{stats['links_created']} links created"
            )
            return stats

    except Exception as e:
        logger.error(f"Error in incident spider enrichment: {e}", exc_info=True)
        return {"errors": [str(e)]}


async def _create_link_if_new(db, stats, from_type, from_id, to_type, to_id, link_type):
    """Create an EntityLink if it doesn't already exist."""
    existing = await db.execute(text("""
        SELECT id FROM entity_links
        WHERE from_type = :ft AND from_id = :fi AND to_type = :tt AND to_id = :ti
        LIMIT 1
    """), {"ft": from_type, "fi": from_id, "tt": to_type, "ti": to_id})

    if existing.first():
        return False

    import uuid
    await db.execute(text("""
        INSERT INTO entity_links (id, from_type, from_id, to_type, to_id, link_type, source_type, confidence_score, status)
        VALUES (:id, :ft, :fi, :tt, :ti, :lt, :st, :cs, :status)
    """), {
        "id": str(uuid.uuid4()),
        "ft": from_type, "fi": from_id,
        "tt": to_type, "ti": to_id,
        "lt": link_type.value if hasattr(link_type, 'value') else str(link_type),
        "st": "inferred",
        "cs": 0.9,
        "status": "active",
    })
    stats["links_created"] += 1
    return True
