from pathlib import Path

from pydantic_settings import BaseSettings


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

    # Google Drive
    gdrive_shared: Path = Path.home() / "Library" / "CloudStorage" / "GoogleDrive-aaryn@planet.com" / "Shared drives"

    # Auth tokens (read from files)
    grafana_token_path: Path = Path.home() / ".config" / "grafana-token"
    pagerduty_token_path: Path = Path.home() / ".config" / "pagerduty-token"

    # Project path mapping (Claude Code project dir name → project key)
    project_path_map: dict[str, str] = {
        "-Users-aaryn-workspaces-wx-1": "wx",
        "-Users-aaryn-workspaces-wx-temporal": "wx",
        "-Users-aaryn-workspaces-g4": "g4",
        "-Users-aaryn-workspaces-jobs": "jobs",
        "-Users-aaryn-workspaces-temporalio": "temporal",
        "-Users-aaryn-claude": "general",
    }

    # Team repos for MR scanning
    team_repos: list[str] = [
        "wx/wx",
        "wx/eso-golang",
        "product/g4-wk/g4",
        "product/g4-wk/g4-task",
        "temporal/temporalio-cloud",
    ]

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


settings = Settings()
