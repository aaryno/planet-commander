"""
Warning Message Parser and Classifier

Parses warning messages from Slack channels and classifies escalation probability.
Used for proactive incident response.
"""

import re
from dataclasses import dataclass
from typing import Optional

from app.models.warning_event import WarningSeverity


# Escalation probability patterns from PROACTIVE-INCIDENT-RESPONSE-SPEC.md
ESCALATION_PATTERNS = {
    "high": [
        r"database.*cpu.*high",
        r"scheduler.*low.*runs",
        r"memory.*approaching.*limit",
        r"deployment.*failed.*rollback",
        r"service.*degraded",
        r"connection.*pool.*exhausted",
        r"disk.*full",
        r"oom.*kill",
        r"cpu.*\d{2}%",  # High CPU percentage
    ],
    "medium": [
        r"connection.*pool.*warning",
        r"queue.*depth.*increasing",
        r"disk.*\d{2}%.*full",
        r"retry.*attempts",
        r"timeout.*increasing",
        r"latency.*high",
        r"error.*rate.*increasing",
    ],
    "low": [
        r"transient.*failure",
        r"retry.*successful",
        r"brief.*threshold",
        r"non-critical",
    ],
}

# System detection patterns
SYSTEM_PATTERNS = {
    "jobs": [r"\bjobs\b", r"scheduler", r"worker", r"pjclient"],
    "wx": [r"\bwx\b", r"workexchange", r"task", r"executor"],
    "g4": [r"\bg4\b", r"datacollect", r"order"],
    "temporal": [r"temporal", r"workflow"],
    "database": [r"database", r"postgres", r"db", r"connection pool"],
    "redis": [r"redis", r"cache"],
    "kubernetes": [r"k8s", r"kubernetes", r"pod", r"node"],
}


@dataclass
class ParsedWarning:
    """Parsed warning message from Slack."""
    alert_name: str
    system: Optional[str]
    severity: WarningSeverity
    escalation_probability: float
    escalation_reason: str
    raw_text: str


class WarningParser:
    """
    Parse and classify warning messages from Slack channels.

    Extracts alert name, system, severity, and predicts escalation probability
    using pattern matching.
    """

    def __init__(self):
        """Initialize parser with compiled patterns."""
        # Compile escalation patterns for performance
        self.escalation_patterns = {
            level: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            for level, patterns in ESCALATION_PATTERNS.items()
        }

        # Compile system patterns
        self.system_patterns = {
            system: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            for system, patterns in SYSTEM_PATTERNS.items()
        }

    def parse(self, message_text: str, channel_name: str = None) -> ParsedWarning:
        """
        Parse warning message and classify escalation probability.

        Args:
            message_text: Slack message text
            channel_name: Slack channel name (for context)

        Returns:
            ParsedWarning with extracted information
        """
        # Extract alert name (usually first line or prominent text)
        alert_name = self._extract_alert_name(message_text)

        # Detect system from message content
        system = self._detect_system(message_text, alert_name)

        # Determine severity from keywords
        severity = self._detect_severity(message_text, channel_name)

        # Classify escalation probability
        escalation_prob, reason = self._classify_escalation_probability(
            message_text, alert_name
        )

        return ParsedWarning(
            alert_name=alert_name,
            system=system,
            severity=severity,
            escalation_probability=escalation_prob,
            escalation_reason=reason,
            raw_text=message_text,
        )

    def _extract_alert_name(self, text: str) -> str:
        """
        Extract alert name from message.

        Looks for patterns like:
        - "alert-name-here WARNING"
        - "Alert: alert-name-here"
        - "🚨 alert-name-here"
        """
        text_lower = text.lower()

        # Pattern 1: alert-name-here WARNING/CRITICAL
        match = re.search(r'([a-z0-9-_]+)\s+(warning|critical|error)', text_lower)
        if match:
            return match.group(1)

        # Pattern 2: Alert: alert-name
        match = re.search(r'alert:?\s+([a-z0-9-_]+)', text_lower)
        if match:
            return match.group(1)

        # Pattern 3: Emoji prefix + alert name
        match = re.search(r'[🚨⚠️❌]\s+([a-z0-9-_]+)', text)
        if match:
            return match.group(1)

        # Pattern 4: First line (up to first newline or period)
        first_line = text.split('\n')[0].strip()
        # Remove common prefixes
        for prefix in ['warning:', 'alert:', 'error:', '🚨', '⚠️']:
            first_line = first_line.lower().replace(prefix, '').strip()

        # Extract word-like alert name (kebab-case or snake_case)
        match = re.search(r'([a-z0-9-_]+)', first_line)
        if match:
            return match.group(1)

        # Fallback: use first 50 chars as alert name
        return text[:50].strip().replace('\n', ' ')

    def _detect_system(self, text: str, alert_name: str) -> Optional[str]:
        """
        Detect which system the warning is about.

        Args:
            text: Message text
            alert_name: Extracted alert name

        Returns:
            System name or None
        """
        # Combine alert name and text for better matching
        combined = f"{alert_name} {text}".lower()

        # Check each system's patterns
        for system, patterns in self.system_patterns.items():
            for pattern in patterns:
                if pattern.search(combined):
                    return system

        return None

    def _detect_severity(
        self, text: str, channel_name: Optional[str] = None
    ) -> WarningSeverity:
        """
        Detect severity from message content and channel.

        Args:
            text: Message text
            channel_name: Slack channel name

        Returns:
            WarningSeverity enum value
        """
        text_lower = text.lower()

        # Explicit severity keywords
        if re.search(r'\b(critical|sev[12]|emergency|outage)\b', text_lower):
            return WarningSeverity.CRITICAL

        if re.search(r'\b(warning|warn|alert)\b', text_lower):
            return WarningSeverity.WARNING

        # Channel-based detection
        if channel_name:
            if 'warn' in channel_name.lower():
                return WarningSeverity.WARNING
            elif 'alert' in channel_name.lower() or 'platform' in channel_name.lower():
                return WarningSeverity.CRITICAL

        # Default to warning
        return WarningSeverity.WARNING

    def _classify_escalation_probability(
        self, text: str, alert_name: str
    ) -> tuple[float, str]:
        """
        Classify escalation probability using pattern matching.

        Args:
            text: Message text
            alert_name: Alert name

        Returns:
            Tuple of (probability 0-1, reason string)
        """
        text_lower = f"{alert_name} {text}".lower()

        matched_reasons = []

        # Check high-priority patterns (75% probability)
        for pattern in self.escalation_patterns["high"]:
            if pattern.search(text_lower):
                matched_reasons.append(f"High: {pattern.pattern}")

        if matched_reasons:
            return (
                0.75,
                f"High escalation risk: {', '.join(matched_reasons[:2])}",
            )

        # Check medium-priority patterns (45% probability)
        for pattern in self.escalation_patterns["medium"]:
            if pattern.search(text_lower):
                matched_reasons.append(f"Medium: {pattern.pattern}")

        if matched_reasons:
            return (
                0.45,
                f"Medium escalation risk: {', '.join(matched_reasons[:2])}",
            )

        # Check low-priority patterns (15% probability)
        for pattern in self.escalation_patterns["low"]:
            if pattern.search(text_lower):
                matched_reasons.append(f"Low: {pattern.pattern}")

        if matched_reasons:
            return (
                0.15,
                f"Low escalation risk: {', '.join(matched_reasons[:2])}",
            )

        # No patterns matched - default to medium-low (30%)
        return (0.30, "No specific pattern matched - baseline probability")

    def should_pre_assemble_context(
        self, escalation_probability: float, threshold: float = 0.5
    ) -> bool:
        """
        Determine if we should pre-assemble context for this warning.

        Args:
            escalation_probability: Calculated probability (0-1)
            threshold: Minimum probability to trigger pre-assembly

        Returns:
            True if context should be pre-assembled
        """
        return escalation_probability >= threshold
