"""Slack notification service for workflow events."""
import logging
import subprocess
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SlackNotificationService:
    """Service for sending Slack notifications about workflow events."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def notify_pr_created(
        self,
        channel: str,
        pr_url: str,
        title: str,
        author: str,
        jira_key: str | None = None
    ) -> Dict[str, any]:
        """
        Notify Slack channel about new PR/MR.

        Args:
            channel: Slack channel (e.g., #compute-platform)
            pr_url: URL to the MR
            title: MR title
            author: Author name
            jira_key: Associated JIRA ticket (optional)

        Returns:
            dict: Notification result
        """
        # Build message
        message_parts = [
            f"🔀 *New Merge Request*",
            f"*{title}*",
            f"Author: {author}",
        ]

        if jira_key:
            message_parts.append(f"JIRA: {jira_key}")

        message_parts.append(f"<{pr_url}|View MR>")

        message = "\n".join(message_parts)

        # Send to Slack
        return await self._send_slack_message(channel, message)

    async def notify_context_status_change(
        self,
        channel: str,
        context_title: str,
        old_status: str,
        new_status: str,
        jira_keys: List[str] | None = None
    ) -> Dict[str, any]:
        """
        Notify Slack channel about context status change.

        Args:
            channel: Slack channel
            context_title: Work context title
            old_status: Previous status
            new_status: New status
            jira_keys: Associated JIRA tickets (optional)

        Returns:
            dict: Notification result
        """
        # Status emoji mapping
        status_emoji = {
            "active": "🟢",
            "blocked": "🔴",
            "done": "✅",
            "ready": "🚀",
            "stalled": "⏸️",
            "orphaned": "⚠️",
            "archived": "📦"
        }

        old_emoji = status_emoji.get(old_status.lower(), "📋")
        new_emoji = status_emoji.get(new_status.lower(), "📋")

        # Build message
        message_parts = [
            f"📊 *Context Status Updated*",
            f"*{context_title}*",
            f"{old_emoji} {old_status} → {new_emoji} {new_status}",
        ]

        if jira_keys:
            message_parts.append(f"JIRA: {', '.join(jira_keys)}")

        message = "\n".join(message_parts)

        # Send to Slack
        return await self._send_slack_message(channel, message)

    async def notify_health_alert(
        self,
        channel: str,
        context_title: str,
        health_status: str,
        issues: List[str]
    ) -> Dict[str, any]:
        """
        Notify Slack channel about context health issues.

        Args:
            channel: Slack channel
            context_title: Work context title
            health_status: Health status (red, yellow)
            issues: List of health issues

        Returns:
            dict: Notification result
        """
        # Health emoji
        health_emoji = {
            "red": "🔴",
            "yellow": "🟡",
            "green": "🟢"
        }

        emoji = health_emoji.get(health_status.lower(), "⚠️")

        # Build message
        message_parts = [
            f"{emoji} *Health Alert*",
            f"*{context_title}*",
            f"Status: {health_status.upper()}",
            "",
            "*Issues:*"
        ]

        for issue in issues[:5]:  # Limit to 5 issues
            message_parts.append(f"• {issue}")

        if len(issues) > 5:
            message_parts.append(f"• ...and {len(issues) - 5} more")

        message = "\n".join(message_parts)

        # Send to Slack
        return await self._send_slack_message(channel, message)

    async def notify_jira_updated(
        self,
        channel: str,
        jira_key: str,
        old_status: str,
        new_status: str,
        context_title: str | None = None
    ) -> Dict[str, any]:
        """
        Notify Slack channel about JIRA ticket update.

        Args:
            channel: Slack channel
            jira_key: JIRA ticket key
            old_status: Previous status
            new_status: New status
            context_title: Associated context title (optional)

        Returns:
            dict: Notification result
        """
        # Build message
        message_parts = [
            f"📝 *JIRA Updated*",
            f"*{jira_key}*",
            f"{old_status} → {new_status}",
        ]

        if context_title:
            message_parts.append(f"Context: {context_title}")

        message = "\n".join(message_parts)

        # Send to Slack
        return await self._send_slack_message(channel, message)

    async def _send_slack_message(self, channel: str, message: str) -> Dict[str, any]:
        """
        Send message to Slack channel using slack CLI.

        Args:
            channel: Slack channel (with or without #)
            message: Message to send

        Returns:
            dict: Send result
        """
        # Ensure channel has #
        if not channel.startswith("#"):
            channel = f"#{channel}"

        try:
            # TODO: Use actual Slack API or webhook
            # For now, using slack CLI if available
            result = subprocess.run(
                ["slack", "chat", "send", "--channel", channel, "--text", message],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "channel": channel,
                    "message": "Notification sent"
                }
            else:
                logger.warning(f"Slack send failed: {result.stderr}")
                return {
                    "success": False,
                    "channel": channel,
                    "error": result.stderr
                }

        except FileNotFoundError:
            # Slack CLI not found - log only (don't fail workflow)
            logger.info(f"Slack CLI not available. Would send to {channel}: {message}")
            return {
                "success": False,
                "channel": channel,
                "error": "Slack CLI not available",
                "message": message  # Include for debugging
            }
        except subprocess.TimeoutExpired:
            logger.warning(f"Slack send timed out for {channel}")
            return {
                "success": False,
                "channel": channel,
                "error": "Timeout"
            }
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return {
                "success": False,
                "channel": channel,
                "error": str(e)
            }
