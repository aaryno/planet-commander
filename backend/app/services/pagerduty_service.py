"""PagerDuty incident service with MCP integration."""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pagerduty_incident import PagerDutyIncident

logger = logging.getLogger(__name__)


class PagerDutyService:
    """Service for PagerDuty incident management via MCP."""

    # Compute Team escalation policy ID from PagerDuty
    COMPUTE_TEAM_ESCALATION_POLICY_ID = "PIGJRDR"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def fetch_incident_from_mcp(self, incident_id: str) -> Optional[Dict]:
        """Fetch a single incident from PagerDuty via MCP.

        Args:
            incident_id: PagerDuty incident ID (e.g., "Q123ABC456")

        Returns:
            Incident data dict or None if not found

        Note:
            Uses mcp_pagerduty-mcp_list_incidents with ID filter.
            In production, would call MCP function here.
            For now, returns None - will be implemented when MCP integration is wired.
        """
        # TODO: Wire up MCP function call when MCP integration is available
        # incidents = mcp_pagerduty_mcp_list_incidents(
        #     query_model={"incident_ids": [incident_id]}
        # )
        # return incidents[0] if incidents else None
        logger.warning(f"MCP integration not yet wired - fetch_incident_from_mcp({incident_id}) returning None")
        return None

    async def fetch_recent_incidents(
        self,
        statuses: List[str] = None,
        team_ids: List[str] = None,
        since: datetime = None,
        until: datetime = None,
        limit: int = 100
    ) -> List[Dict]:
        """Fetch recent incidents from PagerDuty via MCP.

        Args:
            statuses: List of statuses to filter (triggered, acknowledged, resolved)
            team_ids: List of escalation policy IDs to filter
            since: Start date for incident search
            until: End date for incident search
            limit: Max number of incidents to return

        Returns:
            List of incident data dicts

        Note:
            In production, would call MCP function here.
        """
        # TODO: Wire up MCP function call
        # query_model = {}
        # if statuses:
        #     query_model["statuses"] = statuses
        # if team_ids:
        #     query_model["escalation_policy_ids"] = team_ids
        # if since:
        #     query_model["since"] = since.isoformat()
        # if until:
        #     query_model["until"] = until.isoformat()
        # query_model["limit"] = limit
        #
        # incidents = mcp_pagerduty_mcp_list_incidents(query_model=query_model)
        # return incidents
        logger.warning("MCP integration not yet wired - fetch_recent_incidents returning empty list")
        return []

    async def sync_incident(self, incident_data: Dict) -> PagerDutyIncident:
        """Sync a single incident to database.

        Inserts if new, updates if exists.

        Args:
            incident_data: Incident data from PagerDuty API

        Returns:
            Synced PagerDutyIncident model

        Expected incident_data structure (from PagerDuty API):
        {
            "id": "Q123ABC456",
            "incident_number": 12345,
            "title": "Incident title",
            "status": "triggered",  # triggered, acknowledged, resolved
            "urgency": "high",
            "service": {"id": "...", "name": "Service Name"},
            "escalation_policy": {"id": "...", "name": "Policy Name"},
            "assignments": [{
                "assignee": {"id": "...", "email": "...", "name": "..."}
            }],
            "teams": [{"id": "...", "name": "..."}],
            "created_at": "2026-03-19T14:00:00Z",
            "acknowledgements": [...],
            "last_status_change_at": "2026-03-19T14:05:00Z",
            "html_url": "https://planet-labs.pagerduty.com/incidents/...",
            "incident_key": "...",
            "description": "...",
            "priority": {"id": "...", "summary": "P1"},
            "alerts": [...],
            "log_entries": [...]
        }
        """
        external_id = incident_data["id"]

        # Check if incident already exists
        result = await self.db.execute(
            select(PagerDutyIncident).where(
                PagerDutyIncident.external_incident_id == external_id
            )
        )
        incident = result.scalar_one_or_none()

        # Parse timestamps
        triggered_at = self._parse_timestamp(incident_data.get("created_at"))
        acknowledged_at = None
        resolved_at = None
        
        # Check for acknowledgements
        acknowledgements = incident_data.get("acknowledgements", [])
        if acknowledgements:
            ack_times = [self._parse_timestamp(ack.get("at")) for ack in acknowledgements if ack.get("at")]
            if ack_times:
                acknowledged_at = min(ack_times)  # First acknowledgement

        # Check if resolved
        if incident_data.get("status") == "resolved":
            # Use last_status_change_at if available, otherwise now
            resolved_at = self._parse_timestamp(
                incident_data.get("last_status_change_at")
            ) or datetime.utcnow()

        # Parse service
        service = incident_data.get("service", {})
        service_id = service.get("id")
        service_name = service.get("summary") or service.get("name")

        # Parse escalation policy
        escalation_policy = incident_data.get("escalation_policy", {})
        escalation_policy_id = escalation_policy.get("id")
        escalation_policy_name = escalation_policy.get("summary") or escalation_policy.get("name")

        # Parse assignments
        assignments = incident_data.get("assignments", [])
        assigned_to = []
        for assignment in assignments:
            assignee = assignment.get("assignee", {})
            if assignee:
                assigned_to.append({
                    "id": assignee.get("id"),
                    "email": assignee.get("email") or assignee.get("summary"),
                    "name": assignee.get("summary") or assignee.get("email"),
                })

        # Parse teams
        teams_data = incident_data.get("teams", [])
        teams = []
        for team in teams_data:
            teams.append({
                "id": team.get("id"),
                "name": team.get("summary") or team.get("name"),
            })

        # Common fields
        common_fields = {
            "incident_number": incident_data.get("incident_number"),
            "title": incident_data.get("title") or incident_data.get("summary", "Untitled Incident"),
            "status": incident_data.get("status"),
            "urgency": incident_data.get("urgency"),
            "priority": incident_data.get("priority"),
            "service_id": service_id,
            "service_name": service_name,
            "escalation_policy_id": escalation_policy_id,
            "escalation_policy_name": escalation_policy_name,
            "assigned_to": assigned_to if assigned_to else None,
            "teams": teams if teams else None,
            "triggered_at": triggered_at,
            "acknowledged_at": acknowledged_at,
            "resolved_at": resolved_at,
            "last_status_change_at": self._parse_timestamp(
                incident_data.get("last_status_change_at")
            ),
            "incident_url": incident_data.get("incident_url"),
            "html_url": incident_data.get("html_url"),
            "incident_key": incident_data.get("incident_key"),
            "description": incident_data.get("description"),
            "acknowledgements": acknowledgements if acknowledgements else None,
            "assignments": assignments if assignments else None,
            "log_entries": incident_data.get("log_entries"),
            "alerts": incident_data.get("alerts"),
            "last_synced_at": datetime.utcnow(),
        }

        if incident:
            # Update existing incident
            for key, value in common_fields.items():
                setattr(incident, key, value)
            incident.updated_at = datetime.utcnow()
            logger.debug(f"Updated incident #{incident.incident_number}: {incident.title}")
        else:
            # Create new incident
            incident = PagerDutyIncident(
                external_incident_id=external_id,
                **common_fields
            )
            self.db.add(incident)
            logger.info(f"Created new incident #{incident.incident_number}: {incident.title}")

        await self.db.flush()
        return incident

    async def get_incident_by_id(self, incident_id: str) -> Optional[PagerDutyIncident]:
        """Get incident from database by external ID.

        Args:
            incident_id: PagerDuty incident ID (e.g., "Q123ABC456")

        Returns:
            PagerDutyIncident model or None
        """
        result = await self.db.execute(
            select(PagerDutyIncident).where(
                PagerDutyIncident.external_incident_id == incident_id
            )
        )
        return result.scalar_one_or_none()

    async def search_incidents(
        self,
        status: str = None,
        urgency: str = None,
        service_name: str = None,
        team_name: str = None,
        since: datetime = None,
        limit: int = 50
    ) -> List[PagerDutyIncident]:
        """Search incidents in database with filters.

        Args:
            status: Filter by status (triggered, acknowledged, resolved)
            urgency: Filter by urgency (high, low)
            service_name: Filter by service name (partial match)
            team_name: Filter by team name (partial match)
            since: Only incidents triggered after this date
            limit: Max number of results

        Returns:
            List of PagerDutyIncident models
        """
        query = select(PagerDutyIncident)

        # Apply filters
        if status:
            query = query.where(PagerDutyIncident.status == status)
        if urgency:
            query = query.where(PagerDutyIncident.urgency == urgency)
        if service_name:
            query = query.where(PagerDutyIncident.service_name.ilike(f"%{service_name}%"))
        if since:
            query = query.where(PagerDutyIncident.triggered_at >= since)

        # Team name filter requires JSONB query
        # For now, fetch all and filter in Python (can optimize later with JSONB contains)
        # TODO: Optimize with JSONB query when needed

        # Order by triggered_at descending (most recent first)
        query = query.order_by(PagerDutyIncident.triggered_at.desc())

        # Apply limit
        query = query.limit(limit)

        result = await self.db.execute(query)
        incidents = list(result.scalars().all())

        # Filter by team name if provided
        if team_name:
            incidents = [
                inc for inc in incidents
                if any(team_name.lower() in t.lower() for t in inc.team_names)
            ]

        return incidents

    async def extract_incident_references(self, text: str) -> List[str]:
        """Extract PagerDuty incident IDs from text.

        Patterns:
        - https://planet-labs.pagerduty.com/incidents/ABC123
        - PD-ABC123
        - incident ABC123

        Args:
            text: Text to scan for incident references

        Returns:
            List of unique incident IDs found
        """
        if not text:
            return []

        incident_ids = []

        # URL pattern: https://planet-labs.pagerduty.com/incidents/ABC123
        url_pattern = r'https://planet-labs\.pagerduty\.com/incidents/([A-Z0-9]+)'
        incident_ids.extend(re.findall(url_pattern, text, re.IGNORECASE))

        # PD- pattern: PD-ABC123
        pd_pattern = r'\bPD-([A-Z0-9]{6,})\b'
        incident_ids.extend(re.findall(pd_pattern, text, re.IGNORECASE))

        # incident # pattern: incident ABC123 or incident #ABC123
        incident_pattern = r'\bincident\s+#?([A-Z0-9]{6,})\b'
        incident_ids.extend(re.findall(incident_pattern, text, re.IGNORECASE))

        # Deduplicate and normalize to uppercase
        return list(set([id.upper() for id in incident_ids]))

    async def enrich_from_references(self, text: str) -> Dict[str, Any]:
        """Extract incident IDs and fetch from PagerDuty.

        Args:
            text: Text to scan for incident references

        Returns:
            {
                "incident_ids": ["ABC123", ...],
                "incidents_fetched": 3,
                "incidents_cached": 2,
                "errors": []
            }
        """
        incident_ids = await self.extract_incident_references(text)

        stats = {
            "incident_ids": incident_ids,
            "incidents_fetched": 0,
            "incidents_cached": 0,
            "errors": []
        }

        for incident_id in incident_ids:
            try:
                # Check if in cache
                incident = await self.get_incident_by_id(incident_id)
                if incident:
                    stats["incidents_cached"] += 1
                    logger.debug(f"Incident {incident_id} already in cache")
                else:
                    # Fetch from PagerDuty
                    incident_data = await self.fetch_incident_from_mcp(incident_id)
                    if incident_data:
                        await self.sync_incident(incident_data)
                        stats["incidents_fetched"] += 1
                        logger.info(f"Fetched and cached incident {incident_id}")
                    else:
                        error_msg = f"Incident {incident_id} not found in PagerDuty"
                        logger.warning(error_msg)
                        stats["errors"].append(error_msg)

            except Exception as e:
                error_msg = f"Error enriching incident {incident_id}: {e}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)

        return stats

    async def get_compute_team_incidents(
        self,
        status: str = None,
        days: int = 7,
        limit: int = 50
    ) -> List[PagerDutyIncident]:
        """Get recent Compute team incidents.

        Args:
            status: Filter by status (triggered, acknowledged, resolved)
            days: Number of days to look back
            limit: Max number of results

        Returns:
            List of PagerDutyIncident models for Compute team
        """
        since = datetime.utcnow() - timedelta(days=days)

        # Get all incidents since date
        incidents = await self.search_incidents(
            status=status,
            since=since,
            limit=limit * 2  # Get more, then filter
        )

        # Filter to Compute team
        compute_incidents = [inc for inc in incidents if inc.is_compute_team]

        # Apply limit after filtering
        return compute_incidents[:limit]

    @staticmethod
    def _parse_timestamp(timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO 8601 timestamp string to datetime.

        Args:
            timestamp_str: ISO 8601 timestamp (e.g., "2026-03-19T14:00:00Z")

        Returns:
            Datetime object or None if invalid
        """
        if not timestamp_str:
            return None

        try:
            # Handle various ISO 8601 formats
            # Try with timezone first
            if timestamp_str.endswith('Z'):
                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                return datetime.fromisoformat(timestamp_str)
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
            return None
