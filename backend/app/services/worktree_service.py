"""Git worktree detection and matching to agent sessions."""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent import Agent

logger = logging.getLogger(__name__)


@dataclass
class Worktree:
    path: str        # display-friendly path (~/workspaces/...)
    branch: str
    commit: str
    is_bare: bool = False


# Known repo roots relative to workspaces_dir (the actual git repos, not workspace parents)
REPO_ROOTS = [
    "wx-1/wx",
    "temporalio/temporalio-cloud",
    "jobs/jobs",
]

# Host home dir prefix used in worktree paths output by git
_HOST_HOME = str(Path.home())


def _to_display_path(raw_path: str) -> str:
    """Convert a raw worktree path to a display-friendly ~/... format.

    Git worktree list outputs either:
    - Container paths: /data/workspaces/wx-1/wx  (main worktree)
    - Host paths: /Users/aaryn/workspaces/wx-1/worktrees/...  (additional worktrees)

    Both get normalized to ~/workspaces/... for display in the UI.
    """
    container_prefix = str(settings.workspaces_dir)  # /data/workspaces

    if raw_path.startswith(container_prefix):
        # Container path -> ~/workspaces/...
        rel = raw_path[len(container_prefix):]
        return f"~/workspaces{rel}"
    elif raw_path.startswith(_HOST_HOME):
        # Host path -> ~/...
        rel = raw_path[len(_HOST_HOME):]
        return f"~{rel}"
    else:
        return raw_path


def discover_worktrees() -> list[Worktree]:
    """Run `git worktree list` across known repos and return all worktrees."""
    worktrees = []
    base_dir = settings.workspaces_dir

    for repo_rel in REPO_ROOTS:
        repo_path = base_dir / repo_rel
        if not repo_path.exists():
            logger.debug("Repo root not found: %s", repo_path)
            continue

        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.debug("git worktree list failed in %s: %s", repo_path, result.stderr.strip())
                continue

            worktrees.extend(_parse_porcelain(result.stdout))
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning("Failed to list worktrees in %s: %s", repo_path, e)

    return worktrees


def _parse_porcelain(output: str) -> list[Worktree]:
    """Parse `git worktree list --porcelain` output."""
    worktrees = []
    current: dict = {}

    for line in output.splitlines():
        if line.startswith("worktree "):
            if current:
                worktrees.append(_make_worktree(current))
            current = {"path": line[len("worktree "):]}
        elif line.startswith("HEAD "):
            current["commit"] = line[len("HEAD "):]
        elif line.startswith("branch "):
            # branch refs/heads/ao/foo -> ao/foo
            ref = line[len("branch "):]
            current["branch"] = ref.replace("refs/heads/", "")
        elif line == "bare":
            current["is_bare"] = True
        elif line == "" and current:
            worktrees.append(_make_worktree(current))
            current = {}

    if current:
        worktrees.append(_make_worktree(current))

    return worktrees


def _make_worktree(data: dict) -> Worktree:
    return Worktree(
        path=_to_display_path(data.get("path", "")),
        branch=data.get("branch", ""),
        commit=data.get("commit", ""),
        is_bare=data.get("is_bare", False),
    )


# Branches that are too generic to match meaningfully
_GENERIC_BRANCHES = {"main", "master", "HEAD", ""}


async def enrich_agents_with_worktrees(db: AsyncSession) -> int:
    """Match worktrees to agents by git branch and update worktree_path."""
    worktrees = discover_worktrees()
    if not worktrees:
        return 0

    # Build branch -> worktree map (skip generic branches)
    branch_map: dict[str, Worktree] = {}
    # Build path prefix -> worktree map for cwd-based matching
    path_map: dict[str, Worktree] = {}

    for wt in worktrees:
        if wt.is_bare:
            continue
        if wt.branch and wt.branch not in _GENERIC_BRANCHES:
            branch_map[wt.branch] = wt
        # Map display path (~/workspaces/...) to worktree for cwd matching
        # Convert display path to host-style for comparison with agent working_directory
        host_path = wt.path.replace("~", _HOST_HOME)
        path_map[host_path] = wt

    # Find all agents (check both branch and working_directory)
    result = await db.execute(select(Agent))
    agents = result.scalars().all()

    matched = 0
    for agent in agents:
        new_path = None

        # Strategy 1: Match by feature branch name
        if agent.git_branch and agent.git_branch not in _GENERIC_BRANCHES:
            if agent.git_branch in branch_map:
                new_path = branch_map[agent.git_branch].path

        # Strategy 2: Match by working directory being inside a worktree
        if not new_path and agent.working_directory:
            for host_path, wt in path_map.items():
                if agent.working_directory == host_path or agent.working_directory.startswith(host_path + "/"):
                    new_path = wt.path
                    break

        if new_path and new_path != agent.worktree_path:
            agent.worktree_path = new_path
            matched += 1

    if matched > 0:
        await db.commit()

    logger.info("Worktree enrichment: %d agents matched from %d worktrees", matched, len(worktrees))
    return matched
