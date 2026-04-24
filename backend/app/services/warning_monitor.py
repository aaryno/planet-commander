"""
Warning Monitor Service - Proactive Incident Response

Monitors Slack warning channels for escalation-prone warnings.
Parses messages, classifies escalation probability, stores events.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.warning_event import WarningEvent, WarningSeverity
from app.services.warning_parser import WarningParser
from app.services.standby_context import StandbyContextService
from app.services.warning_notifier import WarningNotifier

logger = logging.getLogger(__name__)


# Monitored channels from PROACTIVE-INCIDENT-RESPONSE-SPEC.md
MONITORED_CHANNELS = {
    "compute-platform-warn": {
        "channel_id": "C123ABC",  # TODO: Get actual channel ID
        "team": "compute",
        "escalation_channel": "compute-platform",
    },
    # Add other team channels as they adopt warning monitoring
}


class WarningMonitorService:
    """
    Monitor Slack warning channels for escalation-prone warnings.

    Parses warning messages, classifies escalation probability,
    stores events, and triggers context pre-assembly for high-risk warnings.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize warning monitor service.

        Args:
            db: Database session
        """
        self.db = db
        self.parser = WarningParser()
        self.standby_service = StandbyContextService(db)
        self.notifier = WarningNotifier(db)

    async def process_message(
        self,
        message_text: str,
        channel_id: str,
        channel_name: str,
        message_ts: str,
        thread_ts: Optional[str] = None,
    ) -> Optional[WarningEvent]:
        """
        Process a warning message from Slack.

        Args:
            message_text: Message text
            channel_id: Slack channel ID
            channel_name: Slack channel name
            message_ts: Message timestamp
            thread_ts: Thread timestamp (if in thread)

        Returns:
            WarningEvent if created, None if skipped
        """
        # Parse message
        parsed = self.parser.parse(message_text, channel_name)

        logger.info(
            f"Parsed warning: alert={parsed.alert_name}, "
            f"system={parsed.system}, "
            f"escalation_prob={parsed.escalation_probability:.0%}"
        )

        # Check if this warning already exists (same alert + recent)
        existing = await self._find_recent_warning(
            alert_name=parsed.alert_name,
            channel_id=channel_id,
            lookback_hours=2,
        )

        if existing:
            # Update last_seen timestamp
            existing.last_seen = datetime.now(timezone.utc)
            existing.raw_message = {
                "text": message_text,
                "ts": message_ts,
                "thread_ts": thread_ts,
            }
            await self.db.commit()
            logger.info(
                f"Updated existing warning: {existing.id} (alert={parsed.alert_name})"
            )
            return existing

        # Create new warning event
        warning = WarningEvent(
            alert_name=parsed.alert_name,
            system=parsed.system,
            channel_id=channel_id,
            channel_name=channel_name,
            message_ts=message_ts,
            thread_ts=thread_ts,
            severity=parsed.severity,
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            escalated=False,
            auto_cleared=False,
            escalation_probability=parsed.escalation_probability,
            escalation_reason=parsed.escalation_reason,
            raw_message={
                "text": message_text,
                "ts": message_ts,
                "thread_ts": thread_ts,
            },
        )

        self.db.add(warning)
        await self.db.commit()
        await self.db.refresh(warning)

        logger.info(
            f"Created warning event: {warning.id} "
            f"(alert={parsed.alert_name}, prob={warning.escalation_probability:.0%})"
        )

        # Check if we should pre-assemble context
        if self.parser.should_pre_assemble_context(warning.escalation_probability):
            logger.info(
                f"High escalation risk ({warning.escalation_probability:.0%}), "
                f"pre-assembling standby context for {warning.alert_name}"
            )

            # Create standby context with pre-fetched mitigation data
            standby_context = await self.standby_service.create_standby_context(
                warning_id=warning.id
            )

            if standby_context:
                logger.info(
                    f"Created standby context {standby_context.id} for warning {warning.id}"
                )
            else:
                logger.error(
                    f"Failed to create standby context for warning {warning.id}"
                )

            # Notify about high-risk warning
            try:
                await self.notifier.notify_warning_detected(warning)
            except Exception as e:
                logger.error(f"Failed to send warning notification: {e}")

        return warning

    async def _find_recent_warning(
        self, alert_name: str, channel_id: str, lookback_hours: int = 2
    ) -> Optional[WarningEvent]:
        """
        Find recent warning for same alert.

        Args:
            alert_name: Alert name
            channel_id: Channel ID
            lookback_hours: How far back to look

        Returns:
            WarningEvent if found, None otherwise
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        result = await self.db.execute(
            select(WarningEvent)
            .where(
                WarningEvent.alert_name == alert_name,
                WarningEvent.channel_id == channel_id,
                WarningEvent.first_seen >= cutoff,
                WarningEvent.escalated == False,
                WarningEvent.auto_cleared == False,
            )
            .order_by(WarningEvent.first_seen.desc())
            .limit(1)
        )

        return result.scalar_one_or_none()

    async def get_active_warnings(
        self, channel_id: Optional[str] = None
    ) -> list[WarningEvent]:
        """
        Get all active warnings (not escalated or cleared).

        Args:
            channel_id: Optional filter by channel

        Returns:
            List of active WarningEvents
        """
        query = select(WarningEvent).where(
            WarningEvent.escalated == False, WarningEvent.auto_cleared == False
        )

        if channel_id:
            query = query.where(WarningEvent.channel_id == channel_id)

        query = query.order_by(WarningEvent.first_seen.desc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def mark_escalated(
        self, warning_id: uuid.UUID, incident_context_id: Optional[uuid.UUID] = None
    ) -> Optional[WarningEvent]:
        """
        Mark warning as escalated to critical alert.

        Args:
            warning_id: Warning event ID
            incident_context_id: Incident work context ID

        Returns:
            Updated WarningEvent
        """
        result = await self.db.execute(
            select(WarningEvent).where(WarningEvent.id == warning_id)
        )
        warning = result.scalar_one_or_none()

        if not warning:
            return None

        warning.escalated = True
        warning.escalated_at = datetime.now(timezone.utc)

        if incident_context_id:
            warning.incident_context_id = incident_context_id

        await self.db.commit()

        logger.info(f"Marked warning {warning_id} as escalated")

        return warning

    async def mark_cleared(self, warning_id: uuid.UUID) -> Optional[WarningEvent]:
        """
        Mark warning as auto-cleared (resolved without escalation).

        Args:
            warning_id: Warning event ID

        Returns:
            Updated WarningEvent
        """
        result = await self.db.execute(
            select(WarningEvent).where(WarningEvent.id == warning_id)
        )
        warning = result.scalar_one_or_none()

        if not warning:
            return None

        warning.auto_cleared = True
        warning.cleared_at = datetime.now(timezone.utc)

        await self.db.commit()

        logger.info(
            f"Marked warning {warning_id} as cleared "
            f"(duration: {warning.age_minutes} minutes)"
        )

        return warning

    async def auto_clear_stale_warnings(
        self, stale_hours: int = 24
    ) -> list[WarningEvent]:
        """
        Auto-clear warnings that haven't escalated after X hours.

        Args:
            stale_hours: Hours after which to auto-clear

        Returns:
            List of cleared warnings
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=stale_hours)

        result = await self.db.execute(
            select(WarningEvent).where(
                WarningEvent.first_seen < cutoff,
                WarningEvent.escalated == False,
                WarningEvent.auto_cleared == False,
            )
        )

        warnings = list(result.scalars().all())

        for warning in warnings:
            warning.auto_cleared = True
            warning.cleared_at = datetime.now(timezone.utc)

        if warnings:
            await self.db.commit()
            logger.info(f"Auto-cleared {len(warnings)} stale warnings")

        return warnings
