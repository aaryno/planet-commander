"""Process information endpoints (for host-side script integration)."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.process_cache import process_cache

router = APIRouter()


class ProcessUpdate(BaseModel):
    processes: list[dict]  # [{"pid": int, "session_id": str}, ...]


@router.post("/update")
async def update_processes(update: ProcessUpdate):
    """Receive process list from host-side script.

    This endpoint is called by a host-side script that can see
    all running Claude Code processes (which Docker containers cannot).
    """
    process_cache.update(update.processes)
    return {
        "received": len(update.processes),
        "status": "ok",
    }


@router.get("/list")
async def list_processes():
    """Get cached process list (for debugging)."""
    processes = process_cache.get_all()
    return {
        "processes": [
            {"pid": p.pid, "session_id": p.session_id}
            for p in processes
        ],
        "total": len(processes),
    }
