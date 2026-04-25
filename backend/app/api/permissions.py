"""Agent permissions API — manage allowed tools for spawned agents."""

import logging
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.process_manager import process_manager, _load_allowed_tools, ALLOWED_TOOLS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/permissions", tags=["permissions"])

PERMISSIONS_FILE = Path(__file__).parent.parent.parent / "agent-permissions.txt"

CATEGORY_COMMENTS = {
    "Read": "# File operations",
    "TaskCreate": "# Task management",
    "NotebookEdit": "# Notebook",
    "Agent": "# Agent (sub-agents)",
}


class PermissionsResponse(BaseModel):
    tools: list[str]
    raw: str
    count: int


class AddToolRequest(BaseModel):
    tool: str


class UpdatePermissionsRequest(BaseModel):
    raw: str


def _read_permissions() -> tuple[list[str], str]:
    """Read permissions file, return (tool_list, raw_content)."""
    if not PERMISSIONS_FILE.exists():
        return [], ""
    raw = PERMISSIONS_FILE.read_text()
    tools = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            tools.append(stripped)
    return tools, raw


def _write_permissions(tools: list[str]) -> str:
    """Write deduplicated tools back to file with section comments."""
    seen = set()
    deduped = []
    for t in tools:
        if t not in seen:
            seen.add(t)
            deduped.append(t)

    lines = [
        "# Planet Commander — Allowed tools for spawned agents",
        "#",
        "# One tool pattern per line. Blank lines and # comments are ignored.",
        "# Format: ToolName or Bash(pattern) for shell command patterns.",
        "#",
        "# Changes auto-apply to the next agent turn.",
        "",
    ]

    bash_tools = [t for t in deduped if t.startswith("Bash")]
    non_bash = [t for t in deduped if not t.startswith("Bash")]

    file_ops = [t for t in non_bash if t in ("Read", "Edit", "Write", "Glob", "Grep")]
    task_tools = [t for t in non_bash if t.startswith("Task")]
    other = [t for t in non_bash if t not in file_ops and t not in task_tools]

    if file_ops:
        lines.append("# File operations")
        lines.extend(file_ops)
        lines.append("")

    if bash_tools:
        lines.append("# Shell commands")
        lines.extend(bash_tools)
        lines.append("")

    if task_tools:
        lines.append("# Task management")
        lines.extend(task_tools)
        lines.append("")

    if other:
        lines.append("# Other")
        lines.extend(other)
        lines.append("")

    raw = "\n".join(lines) + "\n"
    PERMISSIONS_FILE.write_text(raw)
    return raw


async def _reload_and_resume(granted_tool: str | None = None):
    """Reload permissions and resume any blocked sessions."""
    import app.services.process_manager as pm
    pm.ALLOWED_TOOLS = _load_allowed_tools()
    logger.info(f"Reloaded {len(pm.ALLOWED_TOOLS)} allowed tools")

    if granted_tool:
        resumed = await pm.process_manager.resume_blocked_sessions(granted_tool)
        if resumed:
            logger.info(f"Auto-resumed {resumed} session(s) after granting {granted_tool}")


@router.get("", response_model=PermissionsResponse)
async def get_permissions():
    tools, raw = _read_permissions()
    return PermissionsResponse(tools=tools, raw=raw, count=len(tools))


@router.put("", response_model=PermissionsResponse)
async def update_permissions(req: UpdatePermissionsRequest):
    tools = []
    for line in req.raw.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            tools.append(stripped)
    raw = _write_permissions(tools)
    await _reload_and_resume()
    return PermissionsResponse(tools=tools, raw=raw, count=len(tools))


@router.post("/add", response_model=PermissionsResponse)
async def add_permission(req: AddToolRequest):
    tool = req.tool.strip()
    if not tool:
        from fastapi import HTTPException
        raise HTTPException(400, "Tool pattern cannot be empty")

    tools, _ = _read_permissions()
    if tool not in tools:
        tools.append(tool)
        raw = _write_permissions(tools)
        await _reload_and_resume(tool)
        logger.info(f"Added permission: {tool}")
    else:
        _, raw = _read_permissions()
        logger.info(f"Permission already exists: {tool}")

    return PermissionsResponse(tools=tools, raw=raw, count=len(tools))


@router.delete("/{tool:path}", response_model=PermissionsResponse)
async def remove_permission(tool: str):
    tools, _ = _read_permissions()
    tools = [t for t in tools if t != tool]
    raw = _write_permissions(tools)
    await _reload_and_resume()
    logger.info(f"Removed permission: {tool}")
    return PermissionsResponse(tools=tools, raw=raw, count=len(tools))
