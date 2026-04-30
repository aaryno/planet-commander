"""Project configuration service — queries active projects from DB.

Replaces hardcoded project lists across the backend with dynamic lookups.
Local paths are resolved using the ~/code/{gitlab_path} convention.
"""

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.project import Project

logger = logging.getLogger(__name__)
CODE_DIR = Path.home() / "code"
WORKSPACES_DIR = Path.home() / "workspaces"


def resolve_local_path(gitlab_path: str, local_path: str | None = None) -> Path:
    """Resolve a GitLab repo path to a local clone directory.

    Resolution order:
      0. Explicit local_path from repo config   (user override)
      1. ~/code/{gitlab_path}                    (standard convention)
      2. ~/workspaces/{gitlab_path}              (multi-workspace setups)
      3. ~/workspaces/*/{repo_name}              (worktree-style: wx-1/wx)

    Returns the first path that exists, or ~/code/{gitlab_path} as default.
    """
    if local_path:
        return Path(local_path).expanduser()

    repo_name = Path(gitlab_path).name

    candidate = CODE_DIR / gitlab_path
    if candidate.exists():
        return candidate

    candidate = WORKSPACES_DIR / gitlab_path
    if candidate.exists():
        return candidate

    if WORKSPACES_DIR.exists():
        for child in WORKSPACES_DIR.iterdir():
            if child.is_dir():
                candidate = child / repo_name
                if candidate.exists() and (candidate / ".git").exists():
                    return candidate

    return CODE_DIR / gitlab_path


class ProjectConfigService:
    """Provides project configuration from the database.

    Usage:
        svc = ProjectConfigService(db)
        projects = await svc.get_gitlab_projects()
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_active_projects(self) -> list[Project]:
        result = await self.db.execute(
            select(Project).where(Project.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def get_active_project_keys(self) -> list[str]:
        result = await self.db.execute(
            select(Project.key).where(Project.is_active.is_(True))
        )
        return [r[0] for r in result.fetchall()]

    async def get_gitlab_projects(self) -> dict[str, dict]:
        """Returns project configs keyed by project key.

        Shape: {project_key: {"repo": "wx/wx", "web_url": "https://..."}}
        Each project maps to its first repository entry.
        """
        projects = await self._get_active_projects()
        result = {}
        for p in projects:
            repos = p.repositories or []
            if not repos:
                continue
            primary_repo = repos[0]
            path = primary_repo.get("path", "")
            if not path:
                continue
            result[p.key] = {
                "repo": path,
                "web_url": f"{settings.gitlab_base_url}/{path}",
            }
        return result

    async def get_all_repo_paths(self) -> list[str]:
        """Returns all repo paths across all active projects.

        Flattens Project.repositories into a deduplicated list of paths.
        """
        projects = await self._get_active_projects()
        paths = []
        seen = set()
        for p in projects:
            for repo in (p.repositories or []):
                path = repo.get("path", "")
                if path and path not in seen:
                    paths.append(path)
                    seen.add(path)
        return paths

    async def get_jira_keys(self, project_key: str) -> list[str]:
        """Returns JIRA project keys for a specific project."""
        result = await self.db.execute(
            select(Project.jira_project_keys).where(
                Project.key == project_key,
                Project.is_active.is_(True),
            )
        )
        row = result.scalar_one_or_none()
        return row if row else []

    async def get_all_jira_keys(self) -> list[str]:
        """Returns deduplicated JIRA keys across all active projects."""
        projects = await self._get_active_projects()
        keys = []
        seen = set()
        for p in projects:
            for key in (p.jira_project_keys or []):
                if key not in seen:
                    keys.append(key)
                    seen.add(key)
        return keys

    async def get_repo_scan_config(self) -> list[dict]:
        """Returns repo configs for git scanning with resolved local paths.

        Shape: [{"path": "/Users/.../wx/wx", "name": "WX Core"}, ...]
        Only includes repos whose local clone exists on disk.
        """
        projects = await self._get_active_projects()
        configs = []
        seen = set()
        for p in projects:
            for repo in (p.repositories or []):
                gitlab_path = repo.get("path", "")
                if not gitlab_path or gitlab_path in seen:
                    continue
                seen.add(gitlab_path)
                local = resolve_local_path(gitlab_path, repo.get("local_path"))
                if local.exists():
                    configs.append({
                        "path": str(local),
                        "name": repo.get("name", gitlab_path),
                    })
                else:
                    logger.debug("Repo not cloned locally: %s (expected at %s)", gitlab_path, local)
        return configs

    async def get_worktree_roots(self) -> list[str]:
        """Returns local repo paths that exist on disk, for worktree discovery.

        Returns paths relative to nothing — these are full repo roots
        that `git worktree list` can be run against.
        """
        projects = await self._get_active_projects()
        roots = []
        seen = set()
        for p in projects:
            for repo in (p.repositories or []):
                gitlab_path = repo.get("path", "")
                if not gitlab_path or gitlab_path in seen:
                    continue
                seen.add(gitlab_path)
                local = resolve_local_path(gitlab_path, repo.get("local_path"))
                if (local / ".git").exists() or (local / ".git").is_file():
                    roots.append(str(local))
        return roots

    async def get_worktree_map(self) -> dict[str, str]:
        """Returns {project_key: local_repo_path} for worktree creation.

        Maps each project to its primary repo's local path.
        """
        projects = await self._get_active_projects()
        result = {}
        for p in projects:
            repos = p.repositories or []
            if not repos:
                continue
            gitlab_path = repos[0].get("path", "")
            if not gitlab_path:
                continue
            local = resolve_local_path(gitlab_path, repos[0].get("local_path"))
            if local.exists():
                result[p.key] = str(local)
        return result

    async def get_project_path_map(self) -> dict[str, str]:
        """Returns {dir_name: project_key} for Claude session mapping.

        Derives directory names from local repo paths following the
        Claude Code convention where project dir names use hyphens
        instead of path separators.
        e.g. /Users/aaryn/code/wx/wx -> "-Users-aaryn-code-wx-wx" -> "wx"
        """
        projects = await self._get_active_projects()
        result = {}
        for p in projects:
            for repo in (p.repositories or []):
                gitlab_path = repo.get("path", "")
                if not gitlab_path:
                    continue
                local = resolve_local_path(gitlab_path, repo.get("local_path"))
                dir_name = str(local).replace("/", "-").lstrip("-")
                result[dir_name] = p.key
        return result
