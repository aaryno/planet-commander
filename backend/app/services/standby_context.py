"""
Standby Context Service - Proactive Incident Response

Pre-assembles mitigation context for high-risk warnings.
Creates "standby" work contexts ready to activate if warning escalates.
"""

import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work_context import WorkContext, OriginType, ContextStatus, HealthStatus
from app.models.warning_event import WarningEvent
from app.models.investigation_artifact import InvestigationArtifact
from app.models.grafana_alert_definition import GrafanaAlertDefinition
from app.models.entity_link import EntityLink, LinkType, LinkSourceType
from app.services.entity_link import EntityLinkService

logger = logging.getLogger(__name__)


class StandbyContextService:
    """
    Create and manage standby work contexts for high-risk warnings.

    A standby context is a pre-assembled work context created when:
    - Warning detected with high escalation probability (> 50%)
    - Context includes pre-fetched:
      - Similar investigation artifacts
      - Alert definitions and runbooks
      - Project context (if system identified)
      - Related incidents (future)
      - Mitigation steps (future)
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize standby context service.

        Args:
            db: Database session
        """
        self.db = db
        self.link_service = EntityLinkService(db)

    async def create_standby_context(
        self, warning_id: uuid.UUID
    ) -> Optional[WorkContext]:
        """
        Create standby context for a warning event.

        Pre-assembles all relevant context for potential incident response.

        Args:
            warning_id: Warning event ID

        Returns:
            Created WorkContext or None if failed
        """
        # Get warning event
        result = await self.db.execute(
            select(WarningEvent).where(WarningEvent.id == warning_id)
        )
        warning = result.scalar_one_or_none()

        if not warning:
            logger.error(f"Warning {warning_id} not found")
            return None

        # Check if standby context already exists
        if warning.standby_context_id:
            logger.info(f"Standby context already exists for warning {warning_id}")
            result = await self.db.execute(
                select(WorkContext).where(WorkContext.id == warning.standby_context_id)
            )
            return result.scalar_one_or_none()

        logger.info(
            f"Creating standby context for warning: {warning.alert_name} "
            f"(prob: {warning.escalation_probability:.0%})"
        )

        # Create work context
        context = WorkContext(
            title=f"Standby: {warning.alert_name}",
            slug=f"standby-{warning.alert_name}-{warning.id}",
            origin_type=OriginType.CHAT,  # From Slack warning channel
            status=ContextStatus.ACTIVE,  # Active but standby (not incident yet)
            health_status=HealthStatus.YELLOW,  # Matches warning severity
            summary_text=(
                f"Pre-assembled context for warning: {warning.alert_name}\n\n"
                f"Escalation probability: {warning.escalation_probability:.0%}\n"
                f"System: {warning.system or 'unknown'}\n"
                f"First seen: {warning.first_seen.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                f"This is a STANDBY context - will activate if warning escalates to critical."
            ),
            owner=None,  # No owner until escalates
        )

        self.db.add(context)
        await self.db.flush()  # Get context.id

        # Link context to warning
        warning.standby_context_id = context.id

        # Pre-assemble context components
        await self._assemble_similar_artifacts(context, warning)
        await self._assemble_alert_definitions(context, warning)
        # TODO: Add project context loading (future)
        # TODO: Add runbook parsing (future)
        # TODO: Add mitigation steps (future)

        await self.db.commit()
        await self.db.refresh(context)

        logger.info(
            f"Standby context created: {context.id} for warning {warning.alert_name}"
        )

        return context

    async def _assemble_similar_artifacts(
        self, context: WorkContext, warning: WarningEvent
    ) -> int:
        """
        Search for and link similar investigation artifacts.

        Args:
            context: Standby context
            warning: Warning event

        Returns:
            Number of artifacts linked
        """
        # Search artifacts for alert name mentions
        # Simple keyword search for MVP (can add semantic search later)
        result = await self.db.execute(
            select(InvestigationArtifact)
            .where(
                InvestigationArtifact.title.ilike(f"%{warning.alert_name}%")
                | InvestigationArtifact.summary.ilike(f"%{warning.alert_name}%")
            )
            .order_by(InvestigationArtifact.created_at.desc())
            .limit(5)  # Top 5 most recent
        )

        artifacts = list(result.scalars().all())

        linked_count = 0
        for artifact in artifacts:
            created = await self.link_service.create_link(
                from_type="work_context",
                from_id=str(context.id),
                to_type="artifact",
                to_id=str(artifact.id),
                link_type=LinkType.REFERENCES_ARTIFACT,
                source_type=LinkSourceType.INFERRED,
                confidence_score=0.8,  # Keyword match confidence
            )

            if created:
                linked_count += 1
                logger.debug(
                    f"Linked artifact: {artifact.filename} to standby context"
                )

        if linked_count > 0:
            logger.info(
                f"Linked {linked_count} similar artifacts to standby context"
            )

        return linked_count

    async def _assemble_alert_definitions(
        self, context: WorkContext, warning: WarningEvent
    ) -> int:
        """
        Search for and link alert definitions.

        Args:
            context: Standby context
            warning: Warning event

        Returns:
            Number of alert definitions linked
        """
        # Search for alert definition by name
        result = await self.db.execute(
            select(GrafanaAlertDefinition)
            .where(GrafanaAlertDefinition.alert_name.ilike(f"%{warning.alert_name}%"))
            .limit(3)  # Should be 1-2 usually
        )

        definitions = list(result.scalars().all())

        linked_count = 0
        for defn in definitions:
            created = await self.link_service.create_link(
                from_type="work_context",
                from_id=str(context.id),
                to_type="grafana_alert",
                to_id=str(defn.id),
                link_type=LinkType.REFERENCES_ALERT,
                source_type=LinkSourceType.INFERRED,
                confidence_score=0.9,  # Name match confidence
            )

            if created:
                linked_count += 1
                logger.debug(
                    f"Linked alert definition: {defn.alert_name} to standby context"
                )

        if linked_count > 0:
            logger.info(
                f"Linked {linked_count} alert definitions to standby context"
            )

        return linked_count

    async def activate_standby_context(
        self, warning_id: uuid.UUID, incident_context_id: uuid.UUID
    ) -> Optional[WorkContext]:
        """
        Activate standby context when warning escalates.

        Links standby context to incident context.

        Args:
            warning_id: Warning event ID
            incident_context_id: Incident work context ID

        Returns:
            Activated standby context
        """
        # Get warning
        result = await self.db.execute(
            select(WarningEvent).where(WarningEvent.id == warning_id)
        )
        warning = result.scalar_one_or_none()

        if not warning or not warning.standby_context_id:
            logger.error(
                f"Warning {warning_id} not found or has no standby context"
            )
            return None

        # Get standby context
        result = await self.db.execute(
            select(WorkContext).where(WorkContext.id == warning.standby_context_id)
        )
        standby_context = result.scalar_one_or_none()

        if not standby_context:
            logger.error(f"Standby context {warning.standby_context_id} not found")
            return None

        # Update standby context status
        standby_context.summary_text = (
            f"⚠️ ESCALATED TO INCIDENT\n\n"
            f"{standby_context.summary_text}\n\n"
            f"Escalated at: {warning.escalated_at.strftime('%Y-%m-%d %H:%M UTC') if warning.escalated_at else 'now'}\n"
            f"Incident context: {incident_context_id}"
        )

        # Link standby context to incident context
        await self.link_service.create_link(
            from_type="work_context",
            from_id=str(standby_context.id),
            to_type="work_context",
            to_id=str(incident_context_id),
            link_type=LinkType.RELATED_TO,  # Or create ESCALATED_TO link type
            source_type=LinkSourceType.AGENT,
            confidence_score=1.0,
        )

        await self.db.commit()

        logger.info(
            f"Activated standby context {standby_context.id} → "
            f"incident {incident_context_id}"
        )

        return standby_context
