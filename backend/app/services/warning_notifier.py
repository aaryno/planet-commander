"""
Warning Notification Service

Sends notifications when warnings are detected or escalate.
Supports Slack messages for warning detection and escalation alerts.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.warning_event import WarningEvent, WarningSeverity
from app.services.slack_notifications import SlackNotificationService

logger = logging.getLogger(__name__)


class WarningNotifier:
    """
    Send notifications for warning events.

    Notification strategy:
    - High-risk warning detected (>50%) → Slack channel (low priority, FYI)
    - Warning escalates to critical → Slack alert channel (high priority)
    - Warning auto-clears → No notification (reduce noise)
    """

    def __init__(self, db: Optional[AsyncSession] = None):
        """
        Initialize warning notifier.

        Args:
            db: Database session (optional, for Slack service)
        """
        self.enabled = True  # TODO: Load from config
        self.warning_channel = "#compute-platform-notifications"  # TODO: Load from config
        self.alert_channel = "#compute-platform"  # TODO: Load from config
        self.slack_service = SlackNotificationService(db) if db else None

    async def notify_warning_detected(self, warning: WarningEvent) -> bool:
        """
        Notify when high-risk warning is detected.

        Sends low-priority Slack DM to on-call with:
        - Alert name and system
        - Escalation probability
        - Link to standby context (if created)
        - Recommendation: "Monitor, no action needed yet"

        Args:
            warning: WarningEvent that was detected

        Returns:
            True if notification sent successfully
        """
        if not self.enabled:
            logger.debug("Notifications disabled, skipping")
            return False

        # Only notify for high-risk warnings (>50%)
        if warning.escalation_probability < 0.5:
            logger.debug(
                f"Warning {warning.alert_name} probability too low "
                f"({warning.escalation_probability:.0%}), skipping notification"
            )
            return False

        logger.info(
            f"Notifying warning detected: {warning.alert_name} "
            f"({warning.escalation_probability:.0%})"
        )

        # Build notification message
        message = self._build_warning_message(warning)

        # Send to Slack channel (not DM - easier to implement)
        if self.slack_service:
            try:
                result = await self.slack_service._send_slack_message(
                    self.warning_channel, message
                )
                if result.get("success"):
                    logger.info(
                        f"Sent warning notification to {self.warning_channel}"
                    )
                    return True
                else:
                    logger.warning(
                        f"Failed to send warning notification: {result.get('error')}"
                    )
            except Exception as e:
                logger.error(f"Error sending Slack notification: {e}")

        # Fallback: just log
        logger.info(f"Warning notification (no Slack): {message}")
        return False

    async def notify_warning_escalated(
        self,
        warning: WarningEvent,
        standby_context_id: Optional[str] = None,
        incident_context_id: Optional[str] = None,
    ) -> bool:
        """
        Notify when warning escalates to critical alert.

        Sends high-priority Slack message to alert channel with:
        - Alert escalation notice
        - Link to pre-assembled standby context
        - Quick action steps (if available)
        - Link to similar prior incidents

        Args:
            warning: WarningEvent that escalated
            standby_context_id: ID of standby context (if exists)
            incident_context_id: ID of incident context (if created)

        Returns:
            True if notification sent successfully
        """
        if not self.enabled:
            logger.debug("Notifications disabled, skipping")
            return False

        logger.info(
            f"Notifying warning escalated: {warning.alert_name} "
            f"(standby: {standby_context_id is not None})"
        )

        # Build escalation message
        message = self._build_escalation_message(
            warning, standby_context_id, incident_context_id
        )

        # Send to alert channel
        if self.slack_service:
            try:
                result = await self.slack_service._send_slack_message(
                    self.alert_channel, message
                )
                if result.get("success"):
                    logger.info(
                        f"Sent escalation notification to {self.alert_channel}"
                    )
                    return True
                else:
                    logger.warning(
                        f"Failed to send escalation notification: {result.get('error')}"
                    )
            except Exception as e:
                logger.error(f"Error sending Slack notification: {e}")

        # Fallback: just log
        logger.info(f"Escalation notification (no Slack): {message}")
        return False

    async def notify_warning_cleared(self, warning: WarningEvent) -> bool:
        """
        Notify when warning auto-clears.

        Currently does NOT send notifications to reduce noise.
        Cleared warnings are visible in UI.

        Args:
            warning: WarningEvent that cleared

        Returns:
            False (no notification sent)
        """
        logger.debug(
            f"Warning cleared: {warning.alert_name} "
            f"(age: {warning.age_minutes}m) - no notification"
        )
        return False

    def _build_warning_message(self, warning: WarningEvent) -> str:
        """
        Build Slack message for warning detection.

        Format:
        ⚠️ Warning detected: {alert_name}
        Escalation probability: {probability}% (HIGH/MEDIUM)
        System: {system}
        Context pre-assembled: {link}

        No action needed unless this escalates to critical.

        Args:
            warning: WarningEvent

        Returns:
            Formatted Slack message
        """
        probability_label = self._get_probability_label(
            warning.escalation_probability
        )
        emoji = self._get_severity_emoji(warning.severity)

        lines = [
            f"{emoji} *Warning detected: {warning.alert_name}*",
            f"Escalation probability: *{warning.escalation_probability:.0%}* ({probability_label})",
        ]

        if warning.system:
            lines.append(f"System: `{warning.system}`")

        if warning.escalation_reason:
            lines.append(f"Pattern: _{warning.escalation_reason}_")

        if warning.standby_context_id:
            # TODO: Replace with actual Commander URL
            context_url = f"http://localhost:3000/context/{warning.standby_context_id}"
            lines.append(f"\n✅ Context pre-assembled: {context_url}")
        else:
            lines.append(
                f"\n_Escalation probability below threshold (50%), no context pre-assembled_"
            )

        lines.append(
            f"\n_No action needed unless this escalates to critical._"
        )

        return "\n".join(lines)

    def _build_escalation_message(
        self,
        warning: WarningEvent,
        standby_context_id: Optional[str],
        incident_context_id: Optional[str],
    ) -> str:
        """
        Build Slack message for warning escalation.

        Format:
        🚨 ALERT ESCALATED: {alert_name}

        ✅ Mitigation plan ready (pre-assembled {time} ago)

        Quick actions:
        1. Check {system} health
        2. Review standby context: {link}

        Prior incident (same pattern): {artifact}
        → Fix: {mitigation} ({duration} resolution)

        Args:
            warning: WarningEvent that escalated
            standby_context_id: Standby context ID
            incident_context_id: Incident context ID

        Returns:
            Formatted Slack message
        """
        lines = [f"🚨 *ALERT ESCALATED: {warning.alert_name}*", ""]

        # Standby context availability
        if standby_context_id:
            age_minutes = warning.age_minutes
            age_display = (
                f"{age_minutes}m"
                if age_minutes < 60
                else f"{age_minutes // 60}h {age_minutes % 60}m"
            )
            lines.append(
                f"✅ Mitigation plan ready (pre-assembled *{age_display}* ago)"
            )
            lines.append("")

            # TODO: Replace with actual URL
            standby_url = f"http://localhost:3000/context/{standby_context_id}"
            lines.append(f"📋 *Standby context:* {standby_url}")
        else:
            lines.append(
                "⚠️ No pre-assembled context (low escalation probability)"
            )

        # System information
        if warning.system:
            lines.append(f"🖥️ *System:* `{warning.system}`")

        # Incident context
        if incident_context_id:
            # TODO: Replace with actual URL
            incident_url = (
                f"http://localhost:3000/context/{incident_context_id}"
            )
            lines.append(f"🎯 *Incident context:* {incident_url}")

        lines.append("")
        lines.append(
            "_PagerDuty alert already triggered. Use pre-assembled context to start mitigation._"
        )

        return "\n".join(lines)

    def _get_probability_label(self, probability: float) -> str:
        """Get human-readable probability label."""
        if probability >= 0.75:
            return "HIGH"
        elif probability >= 0.5:
            return "MEDIUM"
        elif probability >= 0.25:
            return "LOW"
        else:
            return "VERY LOW"

    def _get_severity_emoji(self, severity: WarningSeverity) -> str:
        """Get emoji for severity level."""
        if severity == WarningSeverity.CRITICAL:
            return "🔴"
        elif severity == WarningSeverity.WARNING:
            return "🟡"
        else:
            return "🔵"
