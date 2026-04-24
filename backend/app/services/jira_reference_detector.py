"""
JIRA Reference Detection Service

Scans JIRA ticket descriptions and comments for references to external entities
and returns structured references for EntityLink creation.

Supported entity types (MVP):
- Slack thread URLs
- PagerDuty incident IDs and URLs
"""

import re
from dataclasses import dataclass

from app.models.entity_link import LinkType


@dataclass
class DetectedReference:
    """A detected reference to an external entity in text."""
    entity_type: str  # "slack_thread", "pagerduty_incident"
    entity_id: str    # Extracted ID or identifier
    link_type: LinkType
    confidence: float  # 0.0-1.0
    context: str      # Surrounding text for verification
    raw_match: str    # Original matched text


class JiraReferenceDetector:
    """
    Detects references to external entities in JIRA ticket text.

    Patterns detected (MVP):
    - Slack thread URLs: https://planet-labs.slack.com/archives/C123/p1234567890
    - PagerDuty incident URLs: https://planet-labs.pagerduty.com/incidents/PD-ABC123
    - PagerDuty incident IDs: PD-ABC123, incident #PD-ABC123
    """

    def __init__(self):
        """Initialize detector with compiled regex patterns."""

        # Slack thread URL pattern
        # Example: https://planet-labs.slack.com/archives/C07K123/p1234567890123456
        self.patterns = {
            "slack_thread": re.compile(
                r'https://planet-labs\.slack\.com/archives/([A-Z0-9]+)/p(\d+)',
                re.IGNORECASE
            ),

            # PagerDuty incident URL pattern
            # Example: https://planet-labs.pagerduty.com/incidents/PD-ABC123
            "pagerduty_incident_url": re.compile(
                r'https://planet-labs\.pagerduty\.com/incidents/(PD-[A-Z0-9]+)',
                re.IGNORECASE
            ),

            # PagerDuty incident ID pattern (standalone)
            # Examples: PD-ABC123, incident #PD-ABC123
            # Note: Uses negative lookbehind to avoid matching PD IDs in URLs
            # Limits to 3-8 characters after PD- to avoid over-matching
            # Uses lookahead to ensure next char is not alphanumeric
            "pagerduty_incident_id": re.compile(
                r'(?<!incidents/)\bPD-[A-Z0-9]{3,8}(?![A-Z0-9])',
                re.IGNORECASE
            ),
        }

    def detect_all(self, text: str) -> list[DetectedReference]:
        """
        Detect all references in text.

        Args:
            text: Text to scan for references (JIRA description, comment, etc.)

        Returns:
            List of DetectedReference objects
        """
        if not text:
            return []

        references = []

        # Detect each pattern type
        for pattern_name, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                ref = self._create_reference(pattern_name, match, text)
                if ref:
                    references.append(ref)

        # Deduplicate references (same entity_type + entity_id)
        return self._deduplicate(references)

    def _create_reference(
        self,
        pattern_name: str,
        match: re.Match,
        text: str
    ) -> DetectedReference | None:
        """
        Create DetectedReference from regex match.

        Args:
            pattern_name: Name of pattern that matched
            match: Regex match object
            text: Full text being scanned

        Returns:
            DetectedReference or None if unable to create
        """
        try:
            if pattern_name == "slack_thread":
                # Extract channel ID and timestamp
                channel_id = match.group(1)
                timestamp = match.group(2)

                # Convert timestamp format: p1234567890123456 -> 1234567890.123456
                # Slack timestamps are 10 digits (seconds) + 6 digits (microseconds)
                if len(timestamp) >= 10:
                    ts_seconds = timestamp[:10]
                    ts_micro = timestamp[10:] if len(timestamp) > 10 else "000000"
                    entity_id = f"{channel_id}:{ts_seconds}.{ts_micro}"
                else:
                    entity_id = f"{channel_id}:{timestamp}"

                return DetectedReference(
                    entity_type="slack_thread",
                    entity_id=entity_id,
                    link_type=LinkType.REFERENCES_SLACK,
                    confidence=1.0,  # URL is explicit reference
                    context=self._extract_context(match, text),
                    raw_match=match.group(0)
                )

            elif pattern_name == "pagerduty_incident_url":
                # Extract incident ID from URL
                incident_id = match.group(1).upper()

                return DetectedReference(
                    entity_type="pagerduty_incident",
                    entity_id=incident_id,
                    link_type=LinkType.ESCALATED_TO,
                    confidence=1.0,  # URL is explicit reference
                    context=self._extract_context(match, text),
                    raw_match=match.group(0)
                )

            elif pattern_name == "pagerduty_incident_id":
                # Extract incident ID (e.g., PD-ABC123)
                incident_id = match.group(0).upper()

                return DetectedReference(
                    entity_type="pagerduty_incident",
                    entity_id=incident_id,
                    link_type=LinkType.ESCALATED_TO,
                    confidence=0.95,  # ID mention is very likely intentional
                    context=self._extract_context(match, text),
                    raw_match=match.group(0)
                )

            else:
                return None

        except (IndexError, AttributeError) as e:
            # Failed to extract groups - skip this match
            return None

    def _extract_context(self, match: re.Match, text: str, chars: int = 50) -> str:
        """
        Extract surrounding context for a match.

        Args:
            match: Regex match object
            text: Full text
            chars: Number of characters to extract on each side

        Returns:
            Context string with match in the middle
        """
        start = max(0, match.start() - chars)
        end = min(len(text), match.end() + chars)

        context = text[start:end]

        # Add ellipsis if truncated
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."

        return context.strip()

    def _deduplicate(self, references: list[DetectedReference]) -> list[DetectedReference]:
        """
        Remove duplicate references (same entity_type + entity_id).

        When duplicates found, keep the one with highest confidence.

        Args:
            references: List of references (may contain duplicates)

        Returns:
            Deduplicated list
        """
        seen = {}

        for ref in references:
            key = (ref.entity_type, ref.entity_id)

            if key not in seen:
                seen[key] = ref
            else:
                # Keep reference with higher confidence
                if ref.confidence > seen[key].confidence:
                    seen[key] = ref

        return list(seen.values())
