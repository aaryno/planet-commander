import yaml
from pathlib import Path

from pydantic_settings import BaseSettings

LOCAL_CONFIG_PATH = Path.home() / ".config" / "planet-commander" / "config.yaml"


def _load_local_config() -> dict:
    """Load machine-specific config from ~/.config/planet-commander/config.yaml."""
    if LOCAL_CONFIG_PATH.exists():
        with open(LOCAL_CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


_local_config = _load_local_config()


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://planet_ops:planet_ops_local@localhost:9432/planet_ops"
    database_url_sync: str = "postgresql://planet_ops:planet_ops_local@localhost:9432/planet_ops"

    # Claude Code session data
    claude_dir: Path = Path.home() / ".claude"
    claude_projects_dir: Path = Path.home() / ".claude" / "projects"

    # Workspace paths
    workspaces_dir: Path = Path.home() / "workspaces"
    tools_dir: Path = Path.home() / "tools"
    claude_docs_dir: Path = Path.home() / "claude"

    # Google Drive (override in local config)
    gdrive_shared: Path = Path.home() / "Library" / "CloudStorage" / "GoogleDrive-shared"

    # Auth tokens (read from files)
    grafana_token_path: Path = Path.home() / ".config" / "grafana-token"
    pagerduty_token_path: Path = Path.home() / ".config" / "pagerduty-token"

    # Project path mapping (Claude Code project dir name → project key)
    # Loaded from local config — empty by default, DB-derived map is primary
    project_path_map: dict[str, str] = {}

    # Base URLs — loaded from local config, no defaults committed
    gitlab_base_url: str = ""
    gitlab_api_url: str = ""
    jira_base_url: str = ""
    grafana_base_url: str = ""
    slack_base_url: str = ""

    # User identity
    user_display_name: str = ""

    # Notification channels
    warning_channel: str = ""
    alert_channel: str = ""

    # Polling intervals (seconds)
    poll_agents: int = 30
    poll_mrs: int = 120
    poll_slack: int = 300
    poll_jira: int = 300
    poll_grafana_metrics: int = 30
    poll_oncall: int = 60
    poll_worktrees: int = 60

    class Config:
        env_prefix = "PLANET_OPS_"


def _build_settings() -> "Settings":
    overrides = {}
    for key in (
        "project_path_map", "gdrive_shared",
        "database_url", "database_url_sync",
        "gitlab_base_url", "gitlab_api_url",
        "jira_base_url", "grafana_base_url", "slack_base_url",
        "user_display_name", "warning_channel", "alert_channel",
    ):
        if key in _local_config:
            overrides[key] = _local_config[key]
    return Settings(**overrides)


settings = _build_settings()
