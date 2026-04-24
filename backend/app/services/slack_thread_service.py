"""Slack thread parsing, enrichment, and context extraction service."""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.slack_thread import SlackThread

logger = logging.getLogger(__name__)


class SlackThreadService:
    """Service for Slack thread parsing, enrichment, and cross-reference extraction."""

    # Slack URL pattern: https://planet-labs.slack.com/archives/C123ABC/p1234567890123456?thread_ts=1234567890.123456
    SLACK_URL_PATTERN = re.compile(
        r"https://(?P<workspace>[a-z-]+)\.slack\.com/archives/(?P<channel>[A-Z0-9]+)/p(?P<message_ts>\d+)(?:\?thread_ts=(?P<thread_ts>\d+\.\d+))?"
    )

    # Cross-reference patterns
    JIRA_KEY_PATTERN = re.compile(
        r"\b(?:COMPUTE|PRODISSUE|WX|JOBS|G4|TEMPORAL|ESO|DELTA|HOBBES|AN)-\d+\b",
        re.IGNORECASE
    )

    PAGERDUTY_PATTERN = re.compile(
        r"(?:https://planet-labs\.pagerduty\.com/incidents/([A-Z0-9]+)|PD-([A-Z0-9]+)|\bincident\s+([A-Z0-9]{7,})\b)",
        re.IGNORECASE
    )

    GITLAB_MR_PATTERN = re.compile(
        r"(?:!(\d+)|https://hello\.planet\.com/code/[^/]+/[^/]+/-/merge_requests/(\d+)|MR[\s#]*(\d+))",
        re.IGNORECASE
    )

    CHANNEL_REF_PATTERN = re.compile(
        r"#([a-z0-9-]+)",
        re.IGNORECASE
    )

    # Incident detection patterns
    SEVERITY_PATTERN = re.compile(
        r"\b(?:SEV|severity|S)[\s-]*([1-4])\b",
        re.IGNORECASE
    )

    ONCALL_PATTERN = re.compile(
        r"@(?:oncall|here|channel)",
        re.IGNORECASE
    )

    ESCALATION_KEYWORDS = [
        "escalate", "escalating", "escalation",
        "page", "paging", "pagerduty",
        "incident", "outage", "down",
        "critical", "urgent", "emergency"
    ]

    def __init__(self, db: AsyncSession):
        self.db = db
        self._slack_client = None
        self._slack_token = None

    def _get_slack_client(self):
        """Get or create Slack WebClient."""
        if self._slack_client is None:
            # Load token from ~/tools/slack/slack-config.json
            config_path = Path.home() / "tools/slack/slack-config.json"

            if not config_path.exists():
                raise FileNotFoundError(
                    f"Slack config not found at {config_path}. "
                    "Please create slack-config.json with token."
                )

            with open(config_path, 'r') as f:
                config = json.load(f)
                self._slack_token = config.get("token")

            if not self._slack_token:
                raise ValueError("Slack token not found in config")

            # Import slack_sdk here to avoid requiring it as a dependency for the whole app
            try:
                from slack_sdk import WebClient
                self._slack_client = WebClient(token=self._slack_token)
            except ImportError:
                raise ImportError(
                    "slack_sdk not installed. Install with: pip install slack-sdk"
                )

        return self._slack_client

    def extract_slack_links(self, text: str) -> List[Dict]:
        """Extract Slack thread URLs from text.

        Args:
            text: Text containing Slack URLs

        Returns:
            List of dicts with {channel_id, thread_ts, message_ts, permalink}
        """
        links = []

        for match in self.SLACK_URL_PATTERN.finditer(text):
            workspace = match.group("workspace")
            channel_id = match.group("channel")
            message_ts_raw = match.group("message_ts")
            thread_ts = match.group("thread_ts")

            # Convert p-format timestamp to Slack timestamp (p1234567890123456 -> 1234567890.123456)
            message_ts = f"{message_ts_raw[:-6]}.{message_ts_raw[-6:]}"

            # If no thread_ts, the message itself is the thread root
            if not thread_ts:
                thread_ts = message_ts

            links.append({
                "workspace": workspace,
                "channel_id": channel_id,
                "thread_ts": thread_ts,
                "message_ts": message_ts,
                "permalink": match.group(0)
            })

        return links

    async def fetch_thread(
        self,
        channel_id: str,
        thread_ts: str,
        include_surrounding: bool = False
    ) -> Dict:
        """Fetch thread messages from Slack API.

        Args:
            channel_id: Slack channel ID (e.g., C123ABC)
            thread_ts: Thread timestamp (e.g., 1234567890.123456)
            include_surrounding: If True, fetch ±24h context

        Returns:
            Dict with:
            - messages: List of message dicts
            - participants: List of user dicts
            - reactions: Dict of reaction counts
            - surrounding_messages: List of surrounding messages (if include_surrounding=True)
        """
        client = self._get_slack_client()

        try:
            # Fetch thread replies
            response = client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=1000
            )

            messages = response["messages"]

            # Fetch surrounding context if requested
            surrounding_messages = []
            if include_surrounding and messages:
                # Get ±24 hours around thread start
                thread_start = float(thread_ts)
                oldest = thread_start - (24 * 3600)
                latest = thread_start + (24 * 3600)

                try:
                    context_response = client.conversations_history(
                        channel=channel_id,
                        oldest=str(oldest),
                        latest=str(latest),
                        limit=1000
                    )
                    surrounding_messages = context_response["messages"]
                except Exception as e:
                    logger.warning(f"Failed to fetch surrounding context: {e}")

            # Extract participant user IDs
            participant_ids = set()
            for msg in messages:
                if "user" in msg:
                    participant_ids.add(msg["user"])

            # Fetch user info for participants
            participants = []
            for user_id in participant_ids:
                try:
                    user_response = client.users_info(user=user_id)
                    user = user_response["user"]
                    participants.append({
                        "id": user_id,
                        "name": user.get("real_name", user_id),
                        "display_name": user.get("profile", {}).get("display_name", ""),
                        "email": user.get("profile", {}).get("email", "")
                    })
                except Exception as e:
                    logger.warning(f"Failed to fetch user {user_id}: {e}")

            # Aggregate reactions
            reactions = {}
            for msg in messages:
                if "reactions" in msg:
                    for reaction in msg["reactions"]:
                        name = reaction["name"]
                        count = reaction["count"]
                        reactions[name] = reactions.get(name, 0) + count

            # Get channel info for channel name
            channel_name = None
            try:
                channel_response = client.conversations_info(channel=channel_id)
                channel_name = channel_response["channel"].get("name")
            except Exception as e:
                logger.warning(f"Failed to fetch channel info: {e}")

            return {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "thread_ts": thread_ts,
                "messages": messages,
                "participants": participants,
                "reactions": reactions,
                "surrounding_messages": surrounding_messages
            }

        except Exception as e:
            logger.error(f"Failed to fetch Slack thread {channel_id}/{thread_ts}: {e}")
            raise

    def detect_cross_references(self, messages: List[Dict]) -> Dict:
        """Extract cross-references from messages.

        Detects:
        - JIRA keys (COMPUTE-*, WX-*, etc.)
        - PagerDuty incidents (PD-*, URLs)
        - GitLab MRs (!123, MR URLs)
        - Channel refs (#compute-platform)

        Args:
            messages: List of message dicts from Slack

        Returns:
            Dict with:
            - jira_keys: List[str]
            - pagerduty_incident_ids: List[str]
            - gitlab_mr_refs: List[str]
            - cross_channel_refs: List[str]
        """
        jira_keys = set()
        pd_incidents = set()
        gitlab_mrs = set()
        channel_refs = set()

        for msg in messages:
            text = msg.get("text", "")

            # Extract JIRA keys
            for match in self.JIRA_KEY_PATTERN.finditer(text):
                jira_keys.add(match.group(0).upper())

            # Extract PagerDuty incidents
            for match in self.PAGERDUTY_PATTERN.finditer(text):
                # Match can capture from different groups
                incident_id = match.group(1) or match.group(2) or match.group(3)
                if incident_id:
                    pd_incidents.add(incident_id)

            # Extract GitLab MR references
            for match in self.GITLAB_MR_PATTERN.finditer(text):
                mr_num = match.group(1) or match.group(2) or match.group(3)
                if mr_num:
                    gitlab_mrs.add(f"!{mr_num}")

            # Extract channel references
            for match in self.CHANNEL_REF_PATTERN.finditer(text):
                channel_refs.add(match.group(1))

        return {
            "jira_keys": sorted(list(jira_keys)) if jira_keys else None,
            "pagerduty_incident_ids": sorted(list(pd_incidents)) if pd_incidents else None,
            "gitlab_mr_refs": sorted(list(gitlab_mrs)) if gitlab_mrs else None,
            "cross_channel_refs": sorted(list(channel_refs)) if channel_refs else None
        }

    def detect_incident_pattern(self, messages: List[Dict]) -> Dict:
        """Detect if thread is incident-related.

        Checks for:
        - Severity mentions (SEV1, SEV2)
        - On-call pings (@oncall, @here)
        - PagerDuty incident creation
        - Escalation keywords

        Args:
            messages: List of message dicts from Slack

        Returns:
            Dict with:
            - is_incident: bool
            - severity: str (1-4) or None
            - incident_type: str or None
        """
        is_incident = False
        severity = None
        incident_type = None

        combined_text = " ".join(msg.get("text", "") for msg in messages)

        # Check for severity mentions
        severity_matches = list(self.SEVERITY_PATTERN.finditer(combined_text))
        if severity_matches:
            # Take highest severity (lowest number)
            severities = [int(m.group(1)) for m in severity_matches]
            severity = str(min(severities))
            is_incident = True
            incident_type = f"SEV{severity}"

        # Check for on-call pings
        if self.ONCALL_PATTERN.search(combined_text):
            is_incident = True
            if not incident_type:
                incident_type = "escalation"

        # Check for escalation keywords
        text_lower = combined_text.lower()
        for keyword in self.ESCALATION_KEYWORDS:
            if keyword in text_lower:
                is_incident = True
                if not incident_type:
                    incident_type = keyword
                break

        return {
            "is_incident": is_incident,
            "severity": severity,
            "incident_type": incident_type
        }

    async def sync_thread(self, thread_data: Dict) -> SlackThread:
        """Sync thread to database.

        - Parse messages
        - Extract cross-references
        - Detect incident patterns
        - Insert/update in DB

        Args:
            thread_data: Thread data from fetch_thread()

        Returns:
            SlackThread model
        """
        channel_id = thread_data["channel_id"]
        thread_ts = thread_data["thread_ts"]
        messages = thread_data["messages"]

        # Check if thread already exists
        result = await self.db.execute(
            select(SlackThread).where(
                SlackThread.channel_id == channel_id,
                SlackThread.thread_ts == thread_ts
            )
        )
        existing = result.scalar_one_or_none()

        # Extract cross-references
        cross_refs = self.detect_cross_references(messages)

        # Detect incident pattern
        incident_info = self.detect_incident_pattern(messages)

        # Calculate metadata
        participant_count = len(thread_data["participants"])
        message_count = len(messages)

        # Calculate start/end times
        timestamps = [float(msg["ts"]) for msg in messages]
        start_time = datetime.fromtimestamp(min(timestamps), tz=timezone.utc) if timestamps else None
        end_time = datetime.fromtimestamp(max(timestamps), tz=timezone.utc) if timestamps else None

        duration_hours = None
        if start_time and end_time:
            duration_hours = (end_time - start_time).total_seconds() / 3600

        # Generate title from first message
        title = None
        if messages:
            first_text = messages[0].get("text", "")
            # Take first line or first 100 chars
            title = first_text.split("\n")[0][:100]

        # Build permalink
        # Format: https://workspace.slack.com/archives/CHANNEL/pTIMESTAMP?thread_ts=THREAD_TS
        permalink = thread_data.get("permalink")
        if not permalink:
            # Construct permalink if not provided
            message_ts_p = thread_ts.replace(".", "")
            permalink = f"https://planet-labs.slack.com/archives/{channel_id}/p{message_ts_p}"

        if existing:
            # Update existing thread
            existing.channel_name = thread_data.get("channel_name")
            existing.participant_count = participant_count
            existing.message_count = message_count
            existing.start_time = start_time
            existing.end_time = end_time
            existing.duration_hours = duration_hours
            existing.title = title
            existing.is_incident = incident_info["is_incident"]
            existing.severity = incident_info["severity"]
            existing.incident_type = incident_info["incident_type"]
            existing.jira_keys = cross_refs["jira_keys"]
            existing.pagerduty_incident_ids = cross_refs["pagerduty_incident_ids"]
            existing.gitlab_mr_refs = cross_refs["gitlab_mr_refs"]
            existing.cross_channel_refs = cross_refs["cross_channel_refs"]
            existing.messages = messages
            existing.participants = thread_data["participants"]
            existing.reactions = thread_data["reactions"]
            existing.last_updated_at = datetime.utcnow()

            if thread_data.get("surrounding_messages"):
                existing.surrounding_context_fetched = True

            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        else:
            # Create new thread
            thread = SlackThread(
                channel_id=channel_id,
                channel_name=thread_data.get("channel_name"),
                thread_ts=thread_ts,
                permalink=permalink,
                participant_count=participant_count,
                message_count=message_count,
                start_time=start_time,
                end_time=end_time,
                duration_hours=duration_hours,
                title=title,
                is_incident=incident_info["is_incident"],
                severity=incident_info["severity"],
                incident_type=incident_info["incident_type"],
                surrounding_context_fetched=bool(thread_data.get("surrounding_messages")),
                jira_keys=cross_refs["jira_keys"],
                pagerduty_incident_ids=cross_refs["pagerduty_incident_ids"],
                gitlab_mr_refs=cross_refs["gitlab_mr_refs"],
                cross_channel_refs=cross_refs["cross_channel_refs"],
                messages=messages,
                participants=thread_data["participants"],
                reactions=thread_data["reactions"]
            )

            self.db.add(thread)
            await self.db.commit()
            await self.db.refresh(thread)
            return thread

    async def get_thread_by_url(self, slack_url: str) -> Optional[SlackThread]:
        """Get thread from cache by URL.

        Args:
            slack_url: Full Slack URL

        Returns:
            SlackThread or None if not found
        """
        links = self.extract_slack_links(slack_url)
        if not links:
            return None

        link = links[0]

        result = await self.db.execute(
            select(SlackThread).where(
                SlackThread.channel_id == link["channel_id"],
                SlackThread.thread_ts == link["thread_ts"]
            )
        )

        return result.scalar_one_or_none()

    async def search_threads(
        self,
        channel_id: str = None,
        is_incident: bool = None,
        has_jira_key: str = None,
        since: datetime = None,
        limit: int = 50
    ) -> List[SlackThread]:
        """Search threads with filters.

        Args:
            channel_id: Filter by channel
            is_incident: Filter incident threads
            has_jira_key: Filter threads mentioning JIRA key
            since: Filter threads after this date
            limit: Max results

        Returns:
            List of SlackThread models
        """
        query = select(SlackThread)

        if channel_id:
            query = query.where(SlackThread.channel_id == channel_id)

        if is_incident is not None:
            query = query.where(SlackThread.is_incident == is_incident)

        if has_jira_key:
            # Use JSONB containment operator for array search
            from sqlalchemy import func
            query = query.where(
                func.jsonb_path_exists(
                    SlackThread.jira_keys,
                    f'$[*] ? (@ == "{has_jira_key}")'
                )
            )

        if since:
            query = query.where(SlackThread.start_time >= since)

        query = query.order_by(SlackThread.start_time.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def parse_and_sync_from_text(
        self,
        text: str,
        include_surrounding: bool = False
    ) -> List[SlackThread]:
        """Extract Slack URLs from text and sync all threads.

        Convenience method that combines:
        1. Extract URLs
        2. Fetch threads
        3. Sync to database

        Args:
            text: Text containing Slack URLs
            include_surrounding: Fetch ±24h context

        Returns:
            List of synced SlackThread models
        """
        links = self.extract_slack_links(text)
        threads = []

        for link in links:
            try:
                thread_data = await self.fetch_thread(
                    link["channel_id"],
                    link["thread_ts"],
                    include_surrounding=include_surrounding
                )
                thread = await self.sync_thread(thread_data)
                threads.append(thread)
                logger.info(f"Synced Slack thread: {link['permalink']}")
            except Exception as e:
                logger.error(f"Failed to sync thread {link['permalink']}: {e}")

        return threads
