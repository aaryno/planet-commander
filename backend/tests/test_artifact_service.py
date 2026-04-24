"""Tests for ArtifactService."""

import pytest
from datetime import datetime, timezone
from app.services.artifact_service import ArtifactService


class TestFilenameParser:
    """Test filename parsing logic."""

    def test_parse_valid_filename(self):
        """Test parsing valid artifact filename."""
        service = ArtifactService(db=None)  # No DB needed for parsing
        result = service.parse_filename("20260211-1455-proximity-insights-mvp-complete.md")

        assert result is not None
        assert result["created_at"] == datetime(2026, 2, 11, 14, 55, tzinfo=timezone.utc)
        assert result["description"] == "proximity-insights-mvp-complete"
        assert result["artifact_type"] == "complete"

    def test_parse_investigation_filename(self):
        """Test parsing investigation artifact."""
        service = ArtifactService(db=None)
        result = service.parse_filename("20260130-1200-chad-g4-cost-investigation.md")

        assert result is not None
        assert result["artifact_type"] == "investigation"
        assert result["description"] == "chad-g4-cost-investigation"

    def test_parse_plan_filename(self):
        """Test parsing plan artifact."""
        service = ArtifactService(db=None)
        result = service.parse_filename("20260317-1805-phase1-implementation-plan.md")

        assert result is not None
        assert result["artifact_type"] == "plan"
        assert result["description"] == "phase1-implementation-plan"

    def test_parse_handoff_filename(self):
        """Test parsing handoff artifact."""
        service = ArtifactService(db=None)
        result = service.parse_filename("20251201-1532-tardis-investigation-handoff.md")

        assert result is not None
        assert result["artifact_type"] == "handoff"
        assert result["description"] == "tardis-investigation-handoff"

    def test_parse_analysis_filename(self):
        """Test parsing analysis artifact."""
        service = ArtifactService(db=None)
        result = service.parse_filename("20260212-0957-ppc-capacity-analysis.md")

        assert result is not None
        assert result["artifact_type"] == "analysis"
        assert result["description"] == "ppc-capacity-analysis"

    def test_parse_invalid_filename(self):
        """Test parsing invalid filename."""
        service = ArtifactService(db=None)
        result = service.parse_filename("README.md")

        assert result is None

    def test_parse_wrong_date_format(self):
        """Test parsing filename with wrong date format."""
        service = ArtifactService(db=None)
        result = service.parse_filename("2026-02-11-description.md")

        assert result is None

    def test_parse_no_extension(self):
        """Test parsing filename without .md extension."""
        service = ArtifactService(db=None)
        result = service.parse_filename("20260211-1455-description")

        assert result is None


class TestJiraKeyExtraction:
    """Test JIRA key extraction."""

    def test_extract_single_jira_key(self):
        """Test extracting single JIRA key."""
        service = ArtifactService(db=None)
        content = "This is about COMPUTE-1234"
        keys = service._extract_jira_keys(content)

        assert keys == ["COMPUTE-1234"]

    def test_extract_multiple_jira_keys(self):
        """Test extracting multiple JIRA keys."""
        service = ArtifactService(db=None)
        content = "Working on COMPUTE-1234 and WX-567"
        keys = service._extract_jira_keys(content)

        assert set(keys) == {"COMPUTE-1234", "WX-567"}

    def test_extract_jira_keys_case_insensitive(self):
        """Test JIRA key extraction is case-insensitive."""
        service = ArtifactService(db=None)
        content = "See compute-1234 and Wx-567"
        keys = service._extract_jira_keys(content)

        # Should normalize to uppercase
        assert "COMPUTE-1234" in keys or "compute-1234" in keys

    def test_extract_duplicate_jira_keys(self):
        """Test deduplication of JIRA keys."""
        service = ArtifactService(db=None)
        content = "COMPUTE-1234 and COMPUTE-1234 again"
        keys = service._extract_jira_keys(content)

        assert keys == ["COMPUTE-1234"]

    def test_extract_no_jira_keys(self):
        """Test content with no JIRA keys."""
        service = ArtifactService(db=None)
        content = "Just some regular text"
        keys = service._extract_jira_keys(content)

        assert keys == []

    def test_extract_all_prefixes(self):
        """Test extracting keys with all supported prefixes."""
        service = ArtifactService(db=None)
        content = "COMPUTE-1 WX-2 JOBS-3 TEMPORAL-4 G4-5 PRODISSUE-6"
        keys = service._extract_jira_keys(content)

        assert len(keys) == 6
        assert "COMPUTE-1" in keys
        assert "WX-2" in keys
        assert "JOBS-3" in keys
        assert "TEMPORAL-4" in keys
        assert "G4-5" in keys
        assert "PRODISSUE-6" in keys


class TestKeywordExtraction:
    """Test keyword extraction."""

    def test_extract_keywords_from_text(self):
        """Test extracting keywords from text."""
        service = ArtifactService(db=None)
        text = "task lease expiration investigation redis spanner database"
        keywords = service.extract_keywords(text)

        assert "task" in keywords
        assert "lease" in keywords
        assert "expiration" in keywords

    def test_filter_stopwords(self):
        """Test that stopwords are filtered out."""
        service = ArtifactService(db=None)
        text = "the task is in the database and it was working"
        keywords = service.extract_keywords(text)

        # Stopwords should not be in keywords
        assert "the" not in keywords
        assert "is" not in keywords
        assert "and" not in keywords

        # Real words should be present
        assert "task" in keywords
        assert "database" in keywords
        assert "working" in keywords

    def test_keyword_frequency(self):
        """Test that most frequent keywords are returned first."""
        service = ArtifactService(db=None)
        text = "task task task lease lease investigation"
        keywords = service.extract_keywords(text)

        # "task" appears 3 times, should be first
        assert keywords[0] == "task"


class TestEntityExtraction:
    """Test entity extraction."""

    def test_extract_systems(self):
        """Test extracting system names."""
        service = ArtifactService(db=None)
        content = "WX task failed in Redis and G4 DataCollect had issues"
        entities = service.extract_entities(content)

        assert "WX" in entities["systems"]
        assert "Redis" in entities["systems"]
        assert "G4" in entities["systems"]
        assert "DataCollect" in entities["systems"]

    def test_extract_alerts(self):
        """Test extracting alert names."""
        service = ArtifactService(db=None)
        content = "Alert wx-task-lease-expiration firing, also jobs-scheduler-low-runs"
        entities = service.extract_entities(content)

        assert "wx-task-lease-expiration" in entities["alerts"]
        assert "jobs-scheduler-low-runs" in entities["alerts"]

    def test_no_false_positive_alerts(self):
        """Test that random hyphenated words are not extracted as alerts."""
        service = ArtifactService(db=None)
        content = "this-is-just-a-sentence with-some-hyphens"
        entities = service.extract_entities(content)

        # Should not include random hyphenated text (no platform keyword)
        assert len(entities["alerts"]) == 0

    def test_case_insensitive_systems(self):
        """Test system extraction is case-insensitive."""
        service = ArtifactService(db=None)
        content = "wx and Wx and WX all refer to WorkExchange"
        entities = service.extract_entities(content)

        assert "WX" in entities["systems"] or "WorkExchange" in entities["systems"]


class TestTitleExtraction:
    """Test markdown title extraction."""

    def test_extract_title_h1(self):
        """Test extracting H1 title."""
        service = ArtifactService(db=None)
        content = "# My Investigation\n\nSome content here"
        title = service._extract_title(content)

        assert title == "My Investigation"

    def test_extract_title_h2(self):
        """Test extracting H2 title if no H1."""
        service = ArtifactService(db=None)
        content = "## Secondary Title\n\nContent"
        title = service._extract_title(content)

        assert title == "Secondary Title"

    def test_extract_title_multiple_headings(self):
        """Test extracting first heading when multiple exist."""
        service = ArtifactService(db=None)
        content = "# First Title\n\n## Second Title\n\nContent"
        title = service._extract_title(content)

        assert title == "First Title"

    def test_no_title(self):
        """Test content with no headings."""
        service = ArtifactService(db=None)
        content = "Just plain text with no headings"
        title = service._extract_title(content)

        assert title is None


class TestArtifactTypeInference:
    """Test artifact type inference."""

    def test_infer_investigation(self):
        """Test inferring investigation type."""
        service = ArtifactService(db=None)
        assert service.infer_artifact_type("wx-task-investigation") == "investigation"
        assert service.infer_artifact_type("incident-debug-analysis") == "investigation"
        assert service.infer_artifact_type("stuck-resources-diagnosis") == "investigation"

    def test_infer_plan(self):
        """Test inferring plan type."""
        service = ArtifactService(db=None)
        assert service.infer_artifact_type("implementation-plan") == "plan"
        assert service.infer_artifact_type("migration-strategy") == "plan"
        assert service.infer_artifact_type("rollout-roadmap") == "plan"

    def test_infer_handoff(self):
        """Test inferring handoff type."""
        service = ArtifactService(db=None)
        assert service.infer_artifact_type("investigation-handoff") == "handoff"
        assert service.infer_artifact_type("transition-notes") == "handoff"

    def test_infer_analysis(self):
        """Test inferring analysis type."""
        service = ArtifactService(db=None)
        assert service.infer_artifact_type("capacity-analysis") == "analysis"
        assert service.infer_artifact_type("security-audit") == "analysis"
        assert service.infer_artifact_type("performance-findings") == "analysis"

    def test_infer_complete(self):
        """Test inferring complete type."""
        service = ArtifactService(db=None)
        assert service.infer_artifact_type("mvp-complete") == "complete"
        assert service.infer_artifact_type("implementation-done") == "complete"
        assert service.infer_artifact_type("migration-finished") == "complete"

    def test_infer_summary(self):
        """Test inferring summary type."""
        service = ArtifactService(db=None)
        assert service.infer_artifact_type("incident-summary") == "summary"
        assert service.infer_artifact_type("weekly-report") == "summary"
        assert service.infer_artifact_type("project-overview") == "summary"

    def test_no_type_match(self):
        """Test when no type matches."""
        service = ArtifactService(db=None)
        result = service.infer_artifact_type("random-filename")
        assert result is None
