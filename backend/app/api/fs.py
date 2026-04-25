"""Filesystem browsing API for directory picker."""

import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/fs", tags=["filesystem"])


class DirectoryEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    is_git: bool = False


class BrowseResponse(BaseModel):
    path: str
    parent: str | None
    entries: list[DirectoryEntry]


@router.get("/browse", response_model=BrowseResponse)
async def browse_directory(path: str = Query(default="~")):
    resolved = Path(os.path.expanduser(path)).resolve()

    if not resolved.exists() or not resolved.is_dir():
        return BrowseResponse(
            path=str(resolved),
            parent=str(resolved.parent) if resolved.parent != resolved else None,
            entries=[],
        )

    entries = []
    try:
        for item in sorted(resolved.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if item.name.startswith(".") and item.name not in (".claude",):
                continue
            if not item.is_dir():
                continue
            entries.append(
                DirectoryEntry(
                    name=item.name,
                    path=str(item),
                    is_dir=True,
                    is_git=(item / ".git").exists(),
                )
            )
    except PermissionError:
        pass

    parent = str(resolved.parent) if resolved.parent != resolved else None

    display_path = str(resolved)
    home = str(Path.home())
    if display_path.startswith(home):
        display_path = "~" + display_path[len(home):]

    return BrowseResponse(path=display_path, parent=parent, entries=entries)


class PickerResponse(BaseModel):
    path: str | None
    cancelled: bool = False


@router.get("/pick-directory", response_model=PickerResponse)
async def pick_directory():
    """Open native OS directory picker and return selected path."""
    if sys.platform == "darwin":
        script = (
            'tell application "System Events"\n'
            '  activate\n'
            '  set theFolder to choose folder with prompt "Select working directory"\n'
            '  return POSIX path of theFolder\n'
            'end tell'
        )
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0 and result.stdout.strip():
                picked = result.stdout.strip().rstrip("/")
                return PickerResponse(path=picked)
            return PickerResponse(path=None, cancelled=True)
        except subprocess.TimeoutExpired:
            return PickerResponse(path=None, cancelled=True)
    else:
        return PickerResponse(path=None, cancelled=True)
