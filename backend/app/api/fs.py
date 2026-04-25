"""Filesystem browsing API for directory picker."""

import os
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
