"""Background sync scheduler with active/idle modes.

Active mode:  Syncs every 60s  - when web activity or agent changes within 15 min
Idle mode:    Syncs every 15m  - no activity for 15 min
"""

import asyncio
import logging
import time

from app.database import async_session
from app.services.agent_service import sync_agents, update_agent_statuses_from_processes
from app.services.worktree_service import enrich_agents_with_worktrees

logger = logging.getLogger(__name__)

ACTIVE_INTERVAL = 60       # seconds between syncs in active mode
IDLE_INTERVAL = 15 * 60    # seconds between syncs in idle mode
IDLE_THRESHOLD = 15 * 60   # seconds of inactivity before switching to idle


class SyncScheduler:
    def __init__(self):
        self._last_web_activity: float = time.monotonic()
        self._last_agent_change: float = 0.0
        self._task: asyncio.Task | None = None
        self._running = False

    @property
    def is_active(self) -> bool:
        now = time.monotonic()
        web_active = (now - self._last_web_activity) < IDLE_THRESHOLD
        agent_active = (now - self._last_agent_change) < IDLE_THRESHOLD
        return web_active or agent_active

    @property
    def interval(self) -> int:
        return ACTIVE_INTERVAL if self.is_active else IDLE_INTERVAL

    @property
    def mode(self) -> str:
        return "active" if self.is_active else "idle"

    def record_web_activity(self):
        """Called on incoming web requests."""
        self._last_web_activity = time.monotonic()

    def record_agent_change(self):
        """Called when agent sync detects new or changed agents."""
        self._last_agent_change = time.monotonic()

    def start(self):
        """Start the background sync loop."""
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Sync scheduler started")

    async def stop(self):
        """Stop the background sync loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Sync scheduler stopped")

    async def _loop(self):
        # Run initial sync on startup
        await self._do_sync()

        while self._running:
            interval = self.interval
            logger.debug("Sync scheduler: %s mode, next sync in %ds", self.mode, interval)
            await asyncio.sleep(interval)
            if self._running:
                await self._do_sync()

    async def _do_sync(self):
        try:
            async with async_session() as db:
                result = await sync_agents(db)
                await enrich_agents_with_worktrees(db)
                await update_agent_statuses_from_processes(db)

                if result["new"] > 0:
                    self.record_agent_change()
                    logger.info(
                        "Sync [%s]: %d total (%d new, %d updated)",
                        self.mode, result["synced"], result["new"], result["updated"],
                    )
                else:
                    logger.debug("Sync [%s]: %d agents, no changes", self.mode, result["synced"])
        except Exception:
            logger.exception("Sync failed")

    def status(self) -> dict:
        """Return current scheduler status."""
        return {
            "mode": self.mode,
            "interval_seconds": self.interval,
            "running": self._running,
        }


# Singleton instance
scheduler = SyncScheduler()
