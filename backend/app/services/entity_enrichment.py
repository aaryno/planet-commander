"""Entity enrichment service for auto-context detection.

Scans entities for cross-references (JIRA keys, Slack URLs, PagerDuty incidents, etc.)
and creates entity links automatically.
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Agent,
    EntityLink,
    JiraIssue,
    LinkSourceType,
    LinkType,
    LinkStatus,
)
from app.services.entity_link import EntityLinkService

logger = logging.getLogger(__name__)


class EnrichmentStatus(str, Enum):
    """Enrichment status for entities."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ReferencePattern:
    """Reference detection patterns."""

    # JIRA issue keys
    JIRA_KEY = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")

    # Slack URLs
    SLACK_URL = re.compile(
        r"https://planet-labs\.slack\.com/archives/([A-Z0-9]+)/p(\d{10})(\d{6})"
    )

    # PagerDuty incidents
    PAGERDUTY_URL = re.compile(
        r"https://planet-labs\.pagerduty\.com/incidents/([A-Z0-9]+)"
    )
    PAGERDUTY_ID = re.compile(r"\bPD-([A-Z0-9]{6,})\b")

    # Grafana URLs
    GRAFANA_DASHBOARD = re.compile(
        r"https://planet\.grafana\.net/d/([a-z0-9-]+)/"
    )
    GRAFANA_ALERT = re.compile(
        r"\[FIRING:\d+\]\s+([a-z0-9-]+)"
    )

    # GitLab MR URLs
    GITLAB_MR_URL = re.compile(
        r"https://hello\.planet\.com/code/([a-z0-9-]+/[a-z0-9-]+)/-/merge_requests/(\d+)"
    )
    # MR references in text
    GITLAB_MR_REF = re.compile(r"\bMR\s*!?(\d+)\b")

    # Google Drive URLs
    GDRIVE_URL = re.compile(
        r"https://docs\.google\.com/(document|spreadsheets|presentation)/d/([a-zA-Z0-9_-]+)"
    )


class DetectedReference:
    """A detected cross-reference in entity content."""

    def __init__(
        self,
        ref_type: str,
        ref_id: str,
        url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.ref_type = ref_type
        self.ref_id = ref_id
        self.url = url
        self.metadata = metadata or {}


class EntityEnrichmentService:
    """Detect and link cross-references in entities."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.link_service = EntityLinkService(db)

    async def enrich_jira_issue(self, jira_key: str) -> dict[str, Any]:
        """Enrich a JIRA issue by detecting and linking cross-references.

        Args:
            jira_key: JIRA issue key (e.g., COMPUTE-1234)

        Returns:
            Enrichment result with detected references and links created
        """
        # Find JIRA issue
        result = await self.db.execute(
            select(JiraIssue).where(JiraIssue.external_key == jira_key)
        )
        jira_issue = result.scalar_one_or_none()

        if not jira_issue:
            return {
                "status": EnrichmentStatus.FAILED,
                "error": f"JIRA issue {jira_key} not found in cache",
            }

        # Scan description and comments for references
        content = ""
        if jira_issue.description:
            content += jira_issue.description + "\n"

        # Detect references
        references = self._detect_references(content)

        # Create entity links for detected references
        links_created = []
        for ref in references:
            try:
                link = await self._create_link_for_reference(
                    jira_issue.id, "jira_issue", ref
                )
                if link:
                    links_created.append(
                        {
                            "type": ref.ref_type,
                            "id": ref.ref_id,
                            "url": ref.url,
                        }
                    )
            except Exception as e:
                logger.error(f"Failed to create link for {ref.ref_type}:{ref.ref_id}: {e}")

        # Commit all links
        await self.db.commit()

        return {
            "status": EnrichmentStatus.COMPLETED,
            "entity_type": "jira_issue",
            "entity_id": str(jira_issue.id),
            "entity_key": jira_key,
            "references_detected": len(references),
            "links_created": len(links_created),
            "detected_types": {ref.ref_type for ref in references},
            "links": links_created,
            "enriched_at": datetime.now(timezone.utc).isoformat(),
        }

    async def enrich_chat(self, chat_id: uuid.UUID) -> dict[str, Any]:
        """Enrich a chat/agent session by detecting cross-references.

        Args:
            chat_id: Agent/chat UUID

        Returns:
            Enrichment result with detected references and links created
        """
        # Find chat
        result = await self.db.execute(select(Agent).where(Agent.id == chat_id))
        chat = result.scalar_one_or_none()

        if not chat:
            return {
                "status": EnrichmentStatus.FAILED,
                "error": f"Chat {chat_id} not found",
            }

        # Scan title and any available message content
        content = ""
        if chat.title:
            content += chat.title + "\n"

        # TODO: Scan chat messages when we add message storage
        # For now, just scan title

        # Detect references
        references = self._detect_references(content)

        # Create entity links
        links_created = []
        for ref in references:
            try:
                link = await self._create_link_for_reference(
                    chat.id, "agent", ref
                )
                if link:
                    links_created.append(
                        {
                            "type": ref.ref_type,
                            "id": ref.ref_id,
                            "url": ref.url,
                        }
                    )
            except Exception as e:
                logger.error(f"Failed to create link for {ref.ref_type}:{ref.ref_id}: {e}")

        await self.db.commit()

        return {
            "status": EnrichmentStatus.COMPLETED,
            "entity_type": "agent",
            "entity_id": str(chat.id),
            "references_detected": len(references),
            "links_created": len(links_created),
            "detected_types": {ref.ref_type for ref in references},
            "links": links_created,
            "enriched_at": datetime.now(timezone.utc).isoformat(),
        }

    def _detect_references(self, content: str) -> list[DetectedReference]:
        """Detect all cross-references in content.

        Args:
            content: Text content to scan

        Returns:
            List of detected references
        """
        references = []

        # JIRA keys
        for match in ReferencePattern.JIRA_KEY.finditer(content):
            jira_key = match.group(1)
            references.append(
                DetectedReference(
                    ref_type="jira_issue",
                    ref_id=jira_key,
                    url=f"https://hello.planet.com/jira/browse/{jira_key}",
                )
            )

        # Slack URLs
        for match in ReferencePattern.SLACK_URL.finditer(content):
            channel_id = match.group(1)
            ts_major = match.group(2)
            ts_minor = match.group(3)
            slack_url = match.group(0)
            references.append(
                DetectedReference(
                    ref_type="slack_message",
                    ref_id=f"{channel_id}:{ts_major}.{ts_minor}",
                    url=slack_url,
                    metadata={"channel_id": channel_id, "timestamp": f"{ts_major}.{ts_minor}"},
                )
            )

        # PagerDuty incidents (URLs)
        for match in ReferencePattern.PAGERDUTY_URL.finditer(content):
            incident_id = match.group(1)
            references.append(
                DetectedReference(
                    ref_type="pagerduty_incident",
                    ref_id=incident_id,
                    url=match.group(0),
                )
            )

        # PagerDuty incidents (IDs in text)
        for match in ReferencePattern.PAGERDUTY_ID.finditer(content):
            incident_id = f"PD-{match.group(1)}"
            references.append(
                DetectedReference(
                    ref_type="pagerduty_incident",
                    ref_id=incident_id,
                    url=f"https://planet-labs.pagerduty.com/incidents/{incident_id}",
                )
            )

        # Grafana dashboards
        for match in ReferencePattern.GRAFANA_DASHBOARD.finditer(content):
            dashboard_id = match.group(1)
            references.append(
                DetectedReference(
                    ref_type="grafana_dashboard",
                    ref_id=dashboard_id,
                    url=match.group(0),
                )
            )

        # Grafana alerts (firing messages)
        for match in ReferencePattern.GRAFANA_ALERT.finditer(content):
            alert_name = match.group(1)
            references.append(
                DetectedReference(
                    ref_type="grafana_alert",
                    ref_id=alert_name,
                )
            )

        # GitLab MR URLs
        for match in ReferencePattern.GITLAB_MR_URL.finditer(content):
            repo = match.group(1)
            mr_number = match.group(2)
            references.append(
                DetectedReference(
                    ref_type="gitlab_merge_request",
                    ref_id=f"{repo}!{mr_number}",
                    url=match.group(0),
                    metadata={"repo": repo, "mr_number": int(mr_number)},
                )
            )

        # GitLab MR references
        for match in ReferencePattern.GITLAB_MR_REF.finditer(content):
            mr_number = match.group(1)
            references.append(
                DetectedReference(
                    ref_type="gitlab_merge_request",
                    ref_id=f"!{mr_number}",
                    metadata={"mr_number": int(mr_number)},
                )
            )

        # Google Drive URLs
        for match in ReferencePattern.GDRIVE_URL.finditer(content):
            doc_type = match.group(1)
            doc_id = match.group(2)
            references.append(
                DetectedReference(
                    ref_type="google_drive_document",
                    ref_id=doc_id,
                    url=match.group(0),
                    metadata={"doc_type": doc_type},
                )
            )

        return references

    async def _create_link_for_reference(
        self,
        entity_id: uuid.UUID,
        entity_type: str,
        reference: DetectedReference,
    ) -> EntityLink | None:
        """Create an entity link for a detected reference.

        Args:
            entity_id: Source entity ID
            entity_type: Source entity type
            reference: Detected reference

        Returns:
            Created EntityLink or None if reference target doesn't exist yet
        """
        # For now, create "suggested" links
        # Later we can fetch external data and create confirmed links

        # Map reference type to appropriate link type
        link_type_map = {
            "jira_issue": LinkType.REFERENCES,
            "slack_message": LinkType.REFERENCES_SLACK,
            "pagerduty_incident": LinkType.REFERENCES_PAGERDUTY,
            "grafana_alert": LinkType.REFERENCES_ALERT,
            "grafana_dashboard": LinkType.REFERENCES,
            "gitlab_merge_request": LinkType.REFERENCES,
            "google_drive_document": LinkType.DOCUMENTED_IN_GDRIVE,
        }

        link_type = link_type_map.get(reference.ref_type, LinkType.RELATED_TO)

        # Link direction: entity → reference (entity references the external resource)
        link = await self.link_service.create_link(
            from_type=entity_type,
            from_id=str(entity_id),
            to_type=reference.ref_type,
            to_id=reference.ref_id,
            link_type=link_type,
            source_type=LinkSourceType.INFERRED,
            status=LinkStatus.SUGGESTED,
            confidence_score=0.9,  # High confidence for regex matches
        )

        return link

    async def get_enrichment_status(
        self, entity_type: str, entity_id: str
    ) -> dict[str, Any]:
        """Get enrichment status for an entity.

        Args:
            entity_type: Entity type (jira_issue, agent, etc.)
            entity_id: Entity ID

        Returns:
            Enrichment status information
        """
        # Get all links for this entity
        links = await self.link_service.get_links_for_entity(entity_type, entity_id)

        # Categorize links by type and status
        link_types = {}
        for link in links:
            # Determine reference type (what this entity links to)
            ref_type = link.to_type if link.from_id == entity_id else link.from_type

            if ref_type not in link_types:
                link_types[ref_type] = {
                    "confirmed": 0,
                    "suggested": 0,
                    "total": 0,
                }

            link_types[ref_type]["total"] += 1
            if link.status == LinkStatus.CONFIRMED:
                link_types[ref_type]["confirmed"] += 1
            elif link.status == LinkStatus.SUGGESTED:
                link_types[ref_type]["suggested"] += 1

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "total_links": len(links),
            "link_types": link_types,
            "last_enriched_at": None,  # TODO: Track enrichment timestamp
        }
