"""Configuration service for background jobs and scanning."""
import yaml
from pathlib import Path
from typing import Dict, Any


class ConfigService:
    """Manages configuration for background jobs and scanning."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] | None = None

    def load(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            return self._get_default_config()

        with open(self.config_path) as f:
            self._config = yaml.safe_load(f)

        return self._config or {}

    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration.

        Repo list is intentionally empty — repos come from the projects
        table via ProjectConfigService. Add repo overrides in
        ~/.config/planet-commander/config.yaml if needed.
        """
        return {
            "background_jobs": {
                "enabled": True,
                "git_scanner": {
                    "enabled": True,
                    "schedule_minutes": 30,
                    "repositories": [],
                },
                "jira_sync": {
                    "enabled": True,
                    "schedule_minutes": 15,
                    "queries": [
                        {
                            "name": "my_assigned",
                            "jql": "assignee = currentUser() AND resolution = Unresolved",
                            "max_results": 50,
                        },
                    ],
                },
                "link_inference": {
                    "enabled": True,
                    "schedule_hours": 1,
                    "min_confidence": 0.7,
                },
            }
        }

    def get_repos_to_scan(self) -> list[str]:
        """Get list of repository paths to scan."""
        config = self._config or self.load()
        repos = (
            config.get("background_jobs", {})
            .get("git_scanner", {})
            .get("repositories", [])
        )
        return [str(Path(r["path"]).expanduser()) for r in repos]

    def get_jira_queries(self) -> list[dict]:
        """Get JIRA sync queries."""
        config = self._config or self.load()
        return (
            config.get("background_jobs", {})
            .get("jira_sync", {})
            .get("queries", [])
        )

    def is_job_enabled(self, job_name: str) -> bool:
        """Check if a specific job is enabled."""
        config = self._config or self.load()
        job_config = config.get("background_jobs", {}).get(job_name, {})
        return job_config.get("enabled", False)

    def get_schedule_minutes(self, job_name: str) -> int | None:
        """Get schedule in minutes for a job."""
        config = self._config or self.load()
        job_config = config.get("background_jobs", {}).get(job_name, {})
        return job_config.get("schedule_minutes")

    def get_schedule_hours(self, job_name: str) -> int | None:
        """Get schedule in hours for a job."""
        config = self._config or self.load()
        job_config = config.get("background_jobs", {}).get(job_name, {})
        return job_config.get("schedule_hours")

    def get_min_confidence(self) -> float:
        """Get minimum confidence threshold for link inference."""
        config = self._config or self.load()
        return (
            config.get("background_jobs", {})
            .get("link_inference", {})
            .get("min_confidence", 0.7)
        )


async def get_repos_to_scan_from_db(db) -> list[dict]:
    """Get repos to scan from the projects database.

    Returns repo configs with resolved local paths for all active projects.
    Only includes repos that exist on disk at ~/code/{gitlab_path}.
    """
    from app.services.project_config import ProjectConfigService
    return await ProjectConfigService(db).get_repo_scan_config()


# Singleton instance
config = ConfigService()
