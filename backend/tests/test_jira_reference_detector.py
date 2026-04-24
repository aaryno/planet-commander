"""
Unit tests for JiraReferenceDetector service.
"""

import pytest
from app.services.jira_reference_detector import (
    JiraReferenceDetector,
    DetectedReference,
)
from app.models.entity_link import LinkType


class TestJiraReferenceDetector:
    """Test suite for JIRA reference detection."""

    def setup_method(self):
        """Setup test detector instance."""
        self.detector = JiraReferenceDetector()

    def test_detect_slack_thread_url(self):
        """Test detection of Slack thread URL."""
        text = "See discussion: https://planet-labs.slack.com/archives/C07K123ABC/p1234567890123456"
        refs = self.detector.detect_all(text)

        assert len(refs) == 1
        assert refs[0].entity_type == "slack_thread"
        assert refs[0].entity_id == "C07K123ABC:1234567890.123456"
        assert refs[0].link_type == LinkType.REFERENCES_SLACK
        assert refs[0].confidence == 1.0
        assert "See discussion" in refs[0].context

    def test_detect_slack_thread_url_short_timestamp(self):
        """Test Slack URL with short timestamp (legacy format)."""
        text = "https://planet-labs.slack.com/archives/C123/p1234567890"
        refs = self.detector.detect_all(text)

        assert len(refs) == 1
        assert refs[0].entity_type == "slack_thread"
        assert refs[0].entity_id == "C123:1234567890.000000"

    def test_detect_pagerduty_incident_url(self):
        """Test detection of PagerDuty incident URL."""
        text = "Related to: https://planet-labs.pagerduty.com/incidents/PD-ABC123"
        refs = self.detector.detect_all(text)

        assert len(refs) == 1
        assert refs[0].entity_type == "pagerduty_incident"
        assert refs[0].entity_id == "PD-ABC123"
        assert refs[0].link_type == LinkType.ESCALATED_TO
        assert refs[0].confidence == 1.0

    def test_detect_pagerduty_incident_id(self):
        """Test detection of standalone PagerDuty incident ID."""
        text = "This is related to incident PD-ABC123 from last week"
        refs = self.detector.detect_all(text)

        assert len(refs) == 1
        assert refs[0].entity_type == "pagerduty_incident"
        assert refs[0].entity_id == "PD-ABC123"
        assert refs[0].link_type == LinkType.ESCALATED_TO
        assert refs[0].confidence == 0.95  # Slightly lower for standalone ID

    def test_detect_pagerduty_incident_id_case_insensitive(self):
        """Test PagerDuty ID detection is case-insensitive."""
        text = "See pd-xyz789 for details"
        refs = self.detector.detect_all(text)

        assert len(refs) == 1
        assert refs[0].entity_id == "PD-XYZ789"  # Normalized to uppercase

    def test_detect_multiple_references(self):
        """Test detection of multiple references in one text."""
        text = """
        Background: See Slack thread https://planet-labs.slack.com/archives/C123/p1234567890
        Related PagerDuty incident: PD-ABC123
        Also see: https://planet-labs.pagerduty.com/incidents/PD-XYZ789
        """
        refs = self.detector.detect_all(text)

        assert len(refs) == 3

        # Check we have both entity types
        slack_refs = [r for r in refs if r.entity_type == "slack_thread"]
        pd_refs = [r for r in refs if r.entity_type == "pagerduty_incident"]

        assert len(slack_refs) == 1
        assert len(pd_refs) == 2

    def test_deduplicate_same_incident(self):
        """Test deduplication when same incident referenced multiple times."""
        text = """
        PD-ABC123 was reported.
        See https://planet-labs.pagerduty.com/incidents/PD-ABC123
        Update: PD-ABC123 resolved.
        """
        refs = self.detector.detect_all(text)

        # Should have only 1 reference (deduplicated)
        # URL has confidence 1.0, standalone has 0.95 - should keep URL
        assert len(refs) == 1
        assert refs[0].entity_id == "PD-ABC123"
        assert refs[0].confidence == 1.0  # Kept the URL version

    def test_context_extraction(self):
        """Test that context is extracted around matches."""
        text = "A" * 100 + "See PD-ABC123 here" + "B" * 100
        refs = self.detector.detect_all(text)

        assert len(refs) == 1
        # Context should include surrounding chars
        assert "AAA" in refs[0].context
        assert "PD-ABC123" in refs[0].context
        assert "here" in refs[0].context
        # Should have ellipsis
        assert refs[0].context.startswith("...")
        assert refs[0].context.endswith("...")

    def test_empty_text(self):
        """Test handling of empty text."""
        refs = self.detector.detect_all("")
        assert len(refs) == 0

        refs = self.detector.detect_all(None)
        assert len(refs) == 0

    def test_no_matches(self):
        """Test text with no matches."""
        text = "This is just a regular JIRA ticket description with no external references."
        refs = self.detector.detect_all(text)

        assert len(refs) == 0

    def test_invalid_slack_url_domain(self):
        """Test that only planet-labs.slack.com URLs are matched."""
        text = "https://other-company.slack.com/archives/C123/p1234567890"
        refs = self.detector.detect_all(text)

        assert len(refs) == 0

    def test_invalid_pagerduty_url_domain(self):
        """Test that only planet-labs.pagerduty.com URLs are matched."""
        text = "https://other-company.pagerduty.com/incidents/PD-ABC123"
        refs = self.detector.detect_all(text)

        assert len(refs) == 0

    def test_pagerduty_id_with_short_suffix(self):
        """Test that short PD IDs are not matched (require 6+ chars after PD-)."""
        text = "PD-AB is too short, but PD-ABC123 is valid"
        refs = self.detector.detect_all(text)

        assert len(refs) == 1
        assert refs[0].entity_id == "PD-ABC123"

    def test_raw_match_preserved(self):
        """Test that raw matched text is preserved."""
        text = "See pd-abc123 (lowercase)"
        refs = self.detector.detect_all(text)

        assert len(refs) == 1
        # entity_id is normalized to uppercase
        assert refs[0].entity_id == "PD-ABC123"
        # But raw_match preserves original
        assert refs[0].raw_match == "pd-abc123"

    def test_slack_url_in_markdown_link(self):
        """Test Slack URL detection in markdown link syntax."""
        text = "[Discussion](https://planet-labs.slack.com/archives/C123/p1234567890)"
        refs = self.detector.detect_all(text)

        assert len(refs) == 1
        assert refs[0].entity_type == "slack_thread"

    def test_multiple_slack_threads(self):
        """Test detection of multiple Slack threads."""
        text = """
        First: https://planet-labs.slack.com/archives/C111/p1111111111
        Second: https://planet-labs.slack.com/archives/C222/p2222222222
        """
        refs = self.detector.detect_all(text)

        assert len(refs) == 2
        slack_refs = [r for r in refs if r.entity_type == "slack_thread"]
        assert len(slack_refs) == 2

        entity_ids = {r.entity_id for r in slack_refs}
        assert "C111:1111111111.000000" in entity_ids
        assert "C222:2222222222.000000" in entity_ids
