"""URL classification service - pattern matching for URL types."""
import re
import logging
from typing import Any
from urllib.parse import urlparse

from app.models.url_type import URLType

logger = logging.getLogger(__name__)


class URLClassifier:
    """Classify URLs by pattern matching to known types."""

    # Pattern registry: URLType -> (regex pattern, component extractor)
    # Patterns are compiled once at class load
    PATTERNS: dict[URLType, tuple[re.Pattern, callable]] = {}

    @classmethod
    def _init_patterns(cls):
        """Initialize pattern registry (called once at import)."""
        if cls.PATTERNS:
            return  # Already initialized

        # GitLab patterns
        cls.PATTERNS[URLType.GITLAB_JOB] = (
            re.compile(r'hello\.planet\.com/code/api/v4/jobs/(\d+)'),
            lambda m: {"job_id": int(m.group(1))}
        )

        cls.PATTERNS[URLType.GITLAB_MR] = (
            re.compile(r'hello\.planet\.com/code/([^/]+)/([^/]+)/-/merge_requests/(\d+)'),
            lambda m: {
                "project": m.group(1),
                "repo": m.group(2),
                "mr_id": int(m.group(3))
            }
        )

        cls.PATTERNS[URLType.GITLAB_BRANCH] = (
            re.compile(r'hello\.planet\.com/code/([^/]+)/([^/]+)/-/tree/([^?#]+)'),
            lambda m: {
                "project": m.group(1),
                "repo": m.group(2),
                "branch": m.group(3)
            }
        )

        cls.PATTERNS[URLType.GITLAB_COMMIT] = (
            re.compile(r'hello\.planet\.com/code/([^/]+)/([^/]+)/-/commit/([a-f0-9]{7,40})'),
            lambda m: {
                "project": m.group(1),
                "repo": m.group(2),
                "commit_sha": m.group(3)
            }
        )

        cls.PATTERNS[URLType.GITLAB_PIPELINE] = (
            re.compile(r'hello\.planet\.com/code/([^/]+)/([^/]+)/-/pipelines/(\d+)'),
            lambda m: {
                "project": m.group(1),
                "repo": m.group(2),
                "pipeline_id": int(m.group(3))
            }
        )

        cls.PATTERNS[URLType.GITLAB_ISSUE] = (
            re.compile(r'hello\.planet\.com/code/([^/]+)/([^/]+)/-/issues/(\d+)'),
            lambda m: {
                "project": m.group(1),
                "repo": m.group(2),
                "issue_id": int(m.group(3))
            }
        )

        cls.PATTERNS[URLType.GITLAB_FILE] = (
            re.compile(r'hello\.planet\.com/code/([^/]+)/([^/]+)/-/blob/([^/]+)/(.+)'),
            lambda m: {
                "project": m.group(1),
                "repo": m.group(2),
                "branch": m.group(3),
                "file_path": m.group(4)
            }
        )

        # JIRA patterns
        cls.PATTERNS[URLType.JIRA_ISSUE] = (
            re.compile(r'hello\.planet\.com/jira/browse/([A-Z]+-\d+)'),
            lambda m: {"jira_key": m.group(1)}
        )

        # Google Docs patterns
        cls.PATTERNS[URLType.GOOGLE_DOC] = (
            re.compile(r'docs\.google\.com/document/d/([a-zA-Z0-9_-]+)'),
            lambda m: {"doc_id": m.group(1)}
        )

        cls.PATTERNS[URLType.GOOGLE_SHEET] = (
            re.compile(r'docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]+)'),
            lambda m: {"sheet_id": m.group(1)}
        )

        cls.PATTERNS[URLType.GOOGLE_SLIDE] = (
            re.compile(r'docs\.google\.com/presentation/d/([a-zA-Z0-9_-]+)'),
            lambda m: {"slide_id": m.group(1)}
        )

        cls.PATTERNS[URLType.GOOGLE_DRIVE] = (
            re.compile(r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)'),
            lambda m: {"file_id": m.group(1)}
        )

        # Slack patterns
        cls.PATTERNS[URLType.SLACK_MESSAGE] = (
            re.compile(r'planet\.slack\.com/archives/([A-Z0-9]+)/p(\d+)'),
            lambda m: {
                "channel_id": m.group(1),
                "timestamp": m.group(2)
            }
        )

        # Grafana patterns
        cls.PATTERNS[URLType.GRAFANA_DASHBOARD] = (
            re.compile(r'grafana[^/]*/d/([a-zA-Z0-9_-]+)'),
            lambda m: {"dashboard_id": m.group(1)}
        )

        cls.PATTERNS[URLType.GRAFANA_EXPLORE] = (
            re.compile(r'grafana[^/]*/explore'),
            lambda m: {}
        )

        # PagerDuty patterns
        cls.PATTERNS[URLType.PAGERDUTY_INCIDENT] = (
            re.compile(r'pagerduty\.com/incidents/([A-Z0-9]+)'),
            lambda m: {"incident_id": m.group(1)}
        )

        # GitHub patterns
        cls.PATTERNS[URLType.GITHUB_REPO] = (
            re.compile(r'github\.com/([^/]+)/([^/]+)/?$'),
            lambda m: {
                "org": m.group(1),
                "repo": m.group(2)
            }
        )

        cls.PATTERNS[URLType.GITHUB_ISSUE] = (
            re.compile(r'github\.com/([^/]+)/([^/]+)/issues/(\d+)'),
            lambda m: {
                "org": m.group(1),
                "repo": m.group(2),
                "issue_id": int(m.group(3))
            }
        )

        cls.PATTERNS[URLType.GITHUB_PR] = (
            re.compile(r'github\.com/([^/]+)/([^/]+)/pull/(\d+)'),
            lambda m: {
                "org": m.group(1),
                "repo": m.group(2),
                "pr_id": int(m.group(3))
            }
        )

    def __init__(self):
        # Ensure patterns are initialized
        self._init_patterns()

    def classify(self, url: str) -> dict[str, Any]:
        """Classify URL and extract components.

        Args:
            url: URL string to classify

        Returns:
            {
                "type": URLType,
                "confidence": float,
                "components": dict,  # Extracted parts (job_id, mr_id, etc.)
                "url": str,
                "domain": str
            }
        """
        # Parse domain
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or "unknown"
        except Exception:
            domain = "unknown"

        # Try each pattern
        for url_type, (pattern, extractor) in self.PATTERNS.items():
            match = pattern.search(url)
            if match:
                try:
                    components = extractor(match)
                except Exception as e:
                    logger.warning(f"Failed to extract components from {url}: {e}")
                    components = {}

                return {
                    "type": url_type,
                    "confidence": 1.0,  # Exact pattern match
                    "components": components,
                    "url": url,
                    "domain": domain
                }

        # No match - unknown URL
        return {
            "type": URLType.UNKNOWN,
            "confidence": 0.0,
            "components": {},
            "url": url,
            "domain": domain
        }

    def classify_batch(self, urls: list[str]) -> list[dict[str, Any]]:
        """Classify multiple URLs in batch.

        Args:
            urls: List of URL strings

        Returns:
            List of classification results
        """
        return [self.classify(url) for url in urls]


# Initialize patterns at module load
URLClassifier._init_patterns()
