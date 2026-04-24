"""Worktree API - list existing worktrees and create new ones."""

import logging
import random
import string
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
from app.services.worktree_service import REPO_ROOTS, discover_worktrees

logger = logging.getLogger(__name__)

router = APIRouter()

# Map project key to the repo root used for worktree creation
PROJECT_REPO_MAP: dict[str, str] = {
    "wx": "wx-1/wx",
    "jobs": "jobs/jobs",
    "temporal": "temporalio/temporalio-cloud",
}


@router.get("")
async def list_worktrees(project: str | None = Query(None)):
    """List all git worktrees across known repos.

    Optionally filter by project (matches repo root).
    """
    worktrees = discover_worktrees()

    # Filter out bare repos
    worktrees = [w for w in worktrees if not w.is_bare]

    if project:
        repo_root = PROJECT_REPO_MAP.get(project)
        if repo_root:
            worktrees = [
                w
                for w in worktrees
                if repo_root.split("/")[0] in w.path
            ]

    return {
        "worktrees": [
            {
                "path": w.path,
                "branch": w.branch,
                "commit": w.commit[:8] if w.commit else "",
            }
            for w in worktrees
        ],
        "total": len(worktrees),
    }


def _random_name() -> str:
    """Generate a short random worktree name like 'fox-42'."""
    animals = [
        "fox", "owl", "elk", "jay", "ram", "bee", "ant",
        "ape", "bat", "cat", "cow", "dog", "eel", "hen",
        "hog", "yak", "koi", "lynx", "pug", "ray",
    ]
    return f"{random.choice(animals)}-{random.randint(10, 99)}"


class CreateWorktreeRequest(BaseModel):
    project: str
    branch_name: str | None = None
    jira_key: str | None = None
    checkout_branch: str | None = None


async def _checkout_existing_branch(repo_path: Path, branch: str) -> dict:
    """Create a worktree that checks out an existing remote branch (e.g., for MR review)."""
    worktree_parent = repo_path.parent
    branch_suffix = branch.replace("/", "-")
    worktree_dir = worktree_parent / "worktrees" / f"review-{branch_suffix}"

    if worktree_dir.exists():
        return {
            "path": str(worktree_dir).replace(str(Path.home()), "~"),
            "branch": branch,
            "created": False,
            "message": "Worktree already exists",
        }

    worktree_dir.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["git", "fetch", "origin", branch],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=60,
    )

    try:
        result = subprocess.run(
            ["git", "worktree", "add", str(worktree_dir), f"origin/{branch}"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"git worktree add failed for branch {branch}: {result.stderr.strip()}",
            )

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="git worktree add timed out")

    display_path = str(worktree_dir).replace(str(Path.home()), "~")
    logger.info("Created review worktree: %s for branch %s", display_path, branch)

    return {
        "path": display_path,
        "branch": branch,
        "created": True,
        "message": f"Created review worktree at {display_path}",
    }


@router.post("")
async def create_worktree(request: CreateWorktreeRequest):
    """Create a new git worktree for a project.

    If jira_key is provided, uses it in the branch name (ao/COMPUTE-1234).
    If branch_name is provided, uses that directly.
    Otherwise generates a random name.

    Returns the worktree path and branch name.
    """
    repo_root = PROJECT_REPO_MAP.get(request.project)
    if not repo_root:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown project '{request.project}'. Known: {list(PROJECT_REPO_MAP.keys())}",
        )

    repo_path = settings.workspaces_dir / repo_root
    if not repo_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Repo not found at {repo_path}",
        )

    if request.checkout_branch:
        return await _checkout_existing_branch(repo_path, request.checkout_branch)

    # Determine branch name
    if request.branch_name:
        branch = request.branch_name
    elif request.jira_key:
        # ao/COMPUTE-1234
        branch = f"ao/{request.jira_key.lower()}"
    else:
        branch = f"ao/{_random_name()}"

    # Ensure branch has ao/ prefix
    if not branch.startswith("ao/"):
        branch = f"ao/{branch}"

    # Worktree directory: ~/workspaces/{project-root}/../worktrees/{branch-suffix}
    # e.g., ~/workspaces/wx-1/worktrees/compute-1234
    worktree_parent = repo_path.parent
    branch_suffix = branch.replace("ao/", "").replace("/", "-")
    worktree_dir = worktree_parent / "worktrees" / branch_suffix

    if worktree_dir.exists():
        # Already exists - return it
        return {
            "path": str(worktree_dir).replace(str(Path.home()), "~"),
            "branch": branch,
            "created": False,
            "message": "Worktree already exists",
        }

    # Create the worktree
    worktree_dir.parent.mkdir(parents=True, exist_ok=True)

    try:
        # First try: create with new branch from main
        result = subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(worktree_dir), "main"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            # Branch might already exist - try attaching to existing branch
            if "already exists" in result.stderr:
                result = subprocess.run(
                    ["git", "worktree", "add", str(worktree_dir), branch],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

            if result.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"git worktree add failed: {result.stderr.strip()}",
                )

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="git worktree add timed out")

    display_path = str(worktree_dir).replace(str(Path.home()), "~")
    logger.info("Created worktree: %s on branch %s", display_path, branch)

    return {
        "path": display_path,
        "branch": branch,
        "created": True,
        "message": f"Created worktree at {display_path}",
    }
