"""Unit tests for PagerDutyService."""

import pytest
from unittest.mock import MagicMock

from app.services.pagerduty_service import PagerDutyService


class TestPagerDutyDetection:
    """Test PagerDuty incident reference detection."""

    @pytest.fixture
    def service(self):
        """Create PagerDutyService with mock database."""
        db = MagicMock()
        return PagerDutyService(db)

    def test_detect_single_incident_id(self, service):
        """Should detect a single PD-* incident ID."""
        text = "Investigating incident PD-ABC123 from last night"
        ids = service.detect_incident_references(text)

        assert len(ids) == 1
        assert "PD-ABC123" in ids

    def test_detect_multiple_incident_ids(self, service):
        """Should detect multiple PD-* incident IDs."""
        text = "Related to PD-ABC123 and PD-XYZ789"
        ids = service.detect_incident_references(text)

        assert len(ids) == 2
        assert "PD-ABC123" in ids
        assert "PD-XYZ789" in ids

    def test_detect_incident_url(self, service):
        """Should detect incident from PagerDuty URL."""
        text = "See https://planet-labs.pagerduty.com/incidents/Q1ABCD2EFG3H"
        ids = service.detect_incident_references(text)

        assert len(ids) == 1
        assert "PDURL-Q1ABCD2EFG3H" in ids

    def test_detect_mixed_references(self, service):
        """Should detect both PD-* IDs and URLs."""
        text = """
        Incident PD-ABC123 triggered.
        See details: https://planet-labs.pagerduty.com/incidents/Q1ABCD2EFG3H
        Also related to PD-XYZ789.
        """
        ids = service.detect_incident_references(text)

        assert len(ids) == 3
        assert "PD-ABC123" in ids
        assert "PD-XYZ789" in ids
        assert "PDURL-Q1ABCD2EFG3H" in ids

    def test_case_insensitive(self, service):
        """Should detect incident IDs regardless of case."""
        text = "Check pd-abc123 and PD-XYZ789"
        ids = service.detect_incident_references(text)

        assert len(ids) == 2
        # Should normalize to uppercase
        assert "PD-ABC123" in ids
        assert "PD-XYZ789" in ids

    def test_no_false_positives(self, service):
        """Should not detect false positives."""
        text = "This is a normal description with no incidents"
        ids = service.detect_incident_references(text)

        assert len(ids) == 0

    def test_no_partial_matches(self, service):
        """Should not match partial incident IDs."""
        text = "PD-123 is too short, and NOTPD-ABC123 has a prefix"
        ids = service.detect_incident_references(text)

        # PD-123 is too short (< 6 chars after PD-)
        # NOTPD-ABC123 has a prefix
        assert len(ids) == 0

    def test_word_boundary_detection(self, service):
        """Should respect word boundaries."""
        text = "PD-ABC123 is valid, but APD-ABC123Z is not"
        ids = service.detect_incident_references(text)

        assert len(ids) == 1
        assert "PD-ABC123" in ids

    def test_empty_text(self, service):
        """Should handle empty text gracefully."""
        assert service.detect_incident_references("") == []
        assert service.detect_incident_references(None) == []

    def test_duplicate_removal(self, service):
        """Should deduplicate incident IDs."""
        text = "PD-ABC123 and PD-ABC123 mentioned twice, and pd-abc123 lowercase"
        ids = service.detect_incident_references(text)

        # Should only return unique IDs
        assert len(ids) == 1
        assert "PD-ABC123" in ids

    def test_real_world_jira_description(self, service):
        """Should detect incidents in realistic JIRA description."""
        text = """
        ## Summary
        Jobs scheduler alert fired for low runs.

        ## Details
        PagerDuty incident: PD-A7B8C9D
        URL: https://planet-labs.pagerduty.com/incidents/Q1ABCD2EFG3H

        Related to previous incident PD-X1Y2Z3A.

        ## Action Items
        - Investigate database connection pool
        - Check scheduler health
        """
        ids = service.detect_incident_references(text)

        assert len(ids) == 3
        assert "PD-A7B8C9D" in ids
        assert "PD-X1Y2Z3A" in ids
        assert "PDURL-Q1ABCD2EFG3H" in ids

    def test_real_world_slack_message(self, service):
        """Should detect incidents in realistic Slack message."""
        text = """
        @channel SEV2 incident active: jobs-scheduler-low-runs

        PagerDuty: PD-M4N5O6P
        Status: Acknowledged by @aaryn

        Investigating now. Will update shortly.
        """
        ids = service.detect_incident_references(text)

        assert len(ids) == 1
        assert "PD-M4N5O6P" in ids

    def test_sorted_output(self, service):
        """Should return sorted incident IDs."""
        text = "PD-ZZZ999 and PD-AAA111 and PD-MMM555"
        ids = service.detect_incident_references(text)

        assert ids == sorted(ids)
        assert ids == ["PD-AAA111", "PD-MMM555", "PD-ZZZ999"]
