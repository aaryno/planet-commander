"""
Escalation Detector Service

Monitors critical alerts and correlates with warnings to detect escalations.
When warning → critical escalation detected, activates standby context.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.warning_event import WarningEvent
from app.services.standby_context import StandbyContextService
from app.services.warning_parser import WarningParser, WarningSeverity
from app.services.warning_notifier import WarningNotifier

logger = logging.getLogger(__name__)


class EscalationDetector:
    """
    Detect when warnings escalate to critical incidents.

    Monitors critical alerts from #compute-platform and correlates with
    warnings from #compute-platform-warn to detect escalations.

    Correlation criteria:
    - Same alert name
    - Critical alert occurs within 2 hours of warning
    - Warning has standby context (escalation_probability > 50%)
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize escalation detector.

        Args:
            db: Database session
        """
        self.db = db
        self.parser = WarningParser()
        self.standby_service = StandbyContextService(db)
        self.notifier = WarningNotifier(db)

    async def detect_escalation(
        self, alert_name: str, critical_timestamp: datetime
    ) -> Optional[WarningEvent]:
        """
        Detect if critical alert matches a recent warning.

        Searches for warnings with:
        - Same alert name
        - Occurred within 2 hours before critical alert
        - Not already escalated

        Args:
            alert_name: Alert name from critical message
            critical_timestamp: When critical alert fired

        Returns:
            WarningEvent if escalation detected, None otherwise
        """
        # Calculate time window (2 hours before critical)
        time_window_start = critical_timestamp - timedelta(hours=2)

        logger.debug(
            f"Checking for warning escalation: {alert_name} "
            f"(window: {time_window_start} - {critical_timestamp})"
        )

        # Find matching warning
        result = await self.db.execute(
            select(WarningEvent)
            .where(
                (WarningEvent.alert_name == alert_name)
                & (WarningEvent.escalated == False)  # Not already escalated
                & (WarningEvent.first_seen >= time_window_start)
                & (WarningEvent.first_seen <= critical_timestamp)
            )
            .order_by(WarningEvent.first_seen.desc())  # Most recent first
            .limit(1)
        )

        warning = result.scalar_one_or_none()

        if warning:
            logger.info(
                f"Escalation detected: Warning {warning.id} ({alert_name}) → Critical"
            )
            return warning
        else:
            logger.debug(f"No matching warning found for {alert_name}")
            return None

    async def handle_critical_alert(
        self,
        alert_name: str,
        critical_timestamp: datetime,
        incident_context_id: Optional[uuid.UUID] = None,
    ) -> Optional[WarningEvent]:
        """
        Handle critical alert and check for escalation.

        If escalation detected:
        1. Mark warning as escalated
        2. Activate standby context (if exists)
        3. Link standby → incident context

        Args:
            alert_name: Alert name
            critical_timestamp: When alert fired
            incident_context_id: Optional incident work context ID

        Returns:
            WarningEvent if escalation detected and handled
        """
        warning = await self.detect_escalation(alert_name, critical_timestamp)

        if not warning:
            return None

        # Mark warning as escalated
        warning.escalated = True
        warning.escalated_at = critical_timestamp

        logger.info(f"Marking warning {warning.id} as escalated")

        # Activate standby context if exists
        if warning.standby_context_id and incident_context_id:
            logger.info(
                f"Activating standby context {warning.standby_context_id} → "
                f"incident {incident_context_id}"
            )

            await self.standby_service.activate_standby_context(
                warning_id=warning.id, incident_context_id=incident_context_id
            )
        elif warning.standby_context_id:
            logger.warning(
                f"Warning {warning.id} has standby context but no incident_context_id provided"
            )
        else:
            logger.debug(
                f"Warning {warning.id} has no standby context (probability was likely < 50%)"
            )

        await self.db.commit()

        # Send escalation notification
        try:
            await self.notifier.notify_warning_escalated(
                warning,
                standby_context_id=str(warning.standby_context_id)
                if warning.standby_context_id
                else None,
                incident_context_id=str(incident_context_id)
                if incident_context_id
                else None,
            )
        except Exception as e:
            logger.error(f"Failed to send escalation notification: {e}")

        return warning

    async def process_critical_message(
        self, message: str, timestamp: datetime
    ) -> Optional[WarningEvent]:
        """
        Process critical alert message and detect escalation.

        Parses message to extract alert name, then checks for escalation.

        Args:
            message: Slack message text
            timestamp: Message timestamp

        Returns:
            WarningEvent if escalation detected
        """
        # Parse message
        parsed = self.parser.parse_warning_message(message)

        if not parsed:
            logger.debug("Failed to parse critical message (not an alert)")
            return None

        # Only handle CRITICAL severity
        if parsed["severity"] != WarningSeverity.CRITICAL:
            logger.debug(
                f"Message severity {parsed['severity']} is not CRITICAL, ignoring"
            )
            return None

        alert_name = parsed["alert_name"]
        system = parsed["system"]

        logger.info(
            f"Processing critical alert: {alert_name} (system: {system}) at {timestamp}"
        )

        # Check for escalation
        # Note: incident_context_id not provided here - would come from
        # incident response workflow or PagerDuty integration
        warning = await self.handle_critical_alert(alert_name, timestamp)

        if warning:
            logger.info(
                f"Escalation handled: Warning {warning.id} escalated to critical"
            )
        else:
            logger.debug(f"No escalation detected for {alert_name}")

        return warning

    async def monitor_critical_channel(self, messages: list[dict]) -> int:
        """
        Monitor critical alert channel for escalations.

        Processes messages from #compute-platform and checks for escalations.

        Args:
            messages: List of message dicts with 'text' and 'timestamp' keys

        Returns:
            Number of escalations detected
        """
        escalations_detected = 0

        for msg in messages:
            text = msg.get("text", "")
            timestamp_str = msg.get("timestamp")

            if not text or not timestamp_str:
                continue

            # Parse timestamp (assume ISO format or Unix timestamp)
            try:
                if isinstance(timestamp_str, str):
                    if "." in timestamp_str:
                        # Unix timestamp
                        timestamp = datetime.fromtimestamp(
                            float(timestamp_str), tz=timezone.utc
                        )
                    else:
                        # ISO format
                        timestamp = datetime.fromisoformat(timestamp_str)
                else:
                    # Already a datetime
                    timestamp = timestamp_str
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to parse timestamp {timestamp_str}: {e}")
                continue

            # Process message
            warning = await self.process_critical_message(text, timestamp)

            if warning:
                escalations_detected += 1

        if escalations_detected > 0:
            logger.info(f"Detected {escalations_detected} escalations")

        return escalations_detected
