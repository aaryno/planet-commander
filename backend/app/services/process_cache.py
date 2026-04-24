"""In-memory cache for Claude Code process information.

Since Docker on macOS runs in a VM, we can't see host processes directly.
This cache stores process information POSTed from a host-side script.
"""

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    pid: int
    session_id: str
    updated_at: float


class ProcessCache:
    """Thread-safe in-memory cache of Claude Code processes."""

    def __init__(self, ttl_seconds: int = 120):
        self._processes: dict[str, ProcessInfo] = {}
        self._ttl = ttl_seconds

    def update(self, processes: list[dict]):
        """Update cache with new process list from host.

        Args:
            processes: List of {"pid": int, "session_id": str}
        """
        now = time.time()
        new_map = {}

        for p in processes:
            session_id = p.get("session_id")
            pid = p.get("pid")
            if session_id and pid:
                new_map[session_id] = ProcessInfo(
                    pid=pid,
                    session_id=session_id,
                    updated_at=now,
                )

        self._processes = new_map
        logger.info("Process cache updated: %d processes", len(new_map))

    def get_all(self) -> list[ProcessInfo]:
        """Get all processes, filtering out stale entries."""
        now = time.time()
        fresh = []

        for info in self._processes.values():
            age = now - info.updated_at
            if age < self._ttl:
                fresh.append(info)

        return fresh

    def get_pid_for_session(self, session_id: str) -> int | None:
        """Get PID for a session ID, if it exists and is fresh."""
        info = self._processes.get(session_id)
        if not info:
            return None

        age = time.time() - info.updated_at
        if age >= self._ttl:
            return None

        return info.pid


# Singleton instance
process_cache = ProcessCache()
