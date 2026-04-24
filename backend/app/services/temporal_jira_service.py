"""Temporal JIRA service.

Wraps the existing jira_service to query Temporal-related tickets.
"""

import logging

from app.services.jira_service import search_tickets

logger = logging.getLogger(__name__)

TEMPORAL_JQL = (
    'project = COMPUTE AND '
    '(labels = temporal OR summary ~ "temporal" OR summary ~ "temporalio" '
    'OR summary ~ "Temporal") '
    "AND status in ('To Do', 'In Progress', 'In Review') "
    "ORDER BY priority DESC, updated DESC"
)


async def get_temporal_tickets() -> dict:
    """Get open Temporal-related JIRA tickets."""
    try:
        tickets = await search_tickets(query="", project="COMPUTE", limit=30)
        # The generic search returns recent in-progress tickets when query is empty.
        # We need a Temporal-specific query instead. Use the JIRA service directly
        # with custom JQL by doing a text search for "temporal".
        temporal_tickets = await search_tickets(query="temporal", project="COMPUTE", limit=30)
    except Exception as e:
        logger.error("Failed to fetch Temporal JIRA tickets: %s", e)
        return {"tickets": [], "by_status": {}, "total": 0, "error": str(e)}

    # Deduplicate and count by status
    seen = set()
    unique = []
    by_status: dict[str, int] = {}

    for ticket in temporal_tickets:
        if ticket["key"] in seen:
            continue
        seen.add(ticket["key"])
        # Only include open tickets
        status = ticket.get("status", "")
        if status in ("Done", "Closed", "Resolved"):
            continue
        unique.append(ticket)
        by_status[status] = by_status.get(status, 0) + 1

    return {
        "tickets": unique,
        "by_status": by_status,
        "total": len(unique),
    }
