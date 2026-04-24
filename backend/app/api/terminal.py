"""Terminal launching API endpoints."""

import asyncio
import logging
import shlex
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class TerminalRequest(BaseModel):
    """Request to launch a terminal."""
    path: str
    command: str  # e.g., "open -a Ghostty {path}"


@router.post("/launch")
async def launch_terminal(req: TerminalRequest):
    """Launch a terminal application in the specified directory.

    The command should contain {path} as a placeholder for the directory path.
    """
    # Validate path exists
    path_obj = Path(req.path).expanduser()
    if not path_obj.exists():
        raise HTTPException(status_code=400, detail=f"Path does not exist: {req.path}")

    if not path_obj.is_dir():
        # If it's a file, use its parent directory
        path_obj = path_obj.parent

    # Replace {path} placeholder with actual path
    command = req.command.replace("{path}", str(path_obj))

    # Parse and execute command
    try:
        # Split command safely
        cmd_parts = shlex.split(command)

        logger.info(f"Launching terminal: {command}")

        # Execute command asynchronously
        proc = await asyncio.create_subprocess_exec(
            *cmd_parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Don't wait for completion - terminal apps launch detached
        # Just check if the process started successfully
        await asyncio.sleep(0.5)

        if proc.returncode is not None and proc.returncode != 0:
            stderr = await proc.stderr.read() if proc.stderr else b""
            error_msg = stderr.decode("utf-8", errors="replace")
            raise HTTPException(
                status_code=500,
                detail=f"Terminal launch failed: {error_msg}"
            )

        return {
            "success": True,
            "path": str(path_obj),
            "command": command,
        }

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Terminal application not found. Please check your settings. Error: {e}"
        )
    except Exception as e:
        logger.error(f"Failed to launch terminal: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to launch terminal: {str(e)}"
        )
