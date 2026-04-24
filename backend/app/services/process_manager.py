"""Process manager for launching and controlling Claude Code processes.

Architecture: Per-turn process invocation.
Each user message spawns a new `claude -p --resume <session_id> "message"` process.
Session state persists via Claude's JSONL files. No long-running piped processes.

Output is stream-json: one JSON object per line with types:
  - {"type":"system","subtype":"init",...}    → session init info
  - {"type":"assistant","message":{...}}      → assistant response (content blocks)
  - {"type":"result",...}                     → turn complete
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable, Awaitable

from sqlalchemy import select

logger = logging.getLogger(__name__)


def find_claude_binary() -> Optional[Path]:
    """Find the Claude binary. Checks PATH first, then VS Code extensions."""
    import shutil
    path_binary = shutil.which("claude")
    if path_binary:
        return Path(path_binary)

    extensions_dir = Path.home() / ".vscode" / "extensions"
    if extensions_dir.exists():
        import platform
        arch = "arm64" if platform.machine() == "arm64" else "x64"
        system = platform.system().lower()
        pattern = f"anthropic.claude-code-*-{system}-{arch}"
        matches = sorted(extensions_dir.glob(pattern), reverse=True)
        for ext_dir in matches:
            binary = ext_dir / "resources" / "native-binary" / "claude"
            if binary.exists():
                return binary

    return None


CLAUDE_BINARY = find_claude_binary()
if CLAUDE_BINARY:
    logger.info(f"Found Claude binary: {CLAUDE_BINARY}")
else:
    logger.warning("Claude binary not found — agent spawning will be unavailable")

# Type alias for stdout subscriber callbacks
StdoutCallback = Callable[[str], Awaitable[None]]


@dataclass
class AgentSession:
    """Represents a dashboard-managed Claude Code agent session.

    Unlike a long-running process, this tracks the session state across
    multiple per-turn process invocations.
    """

    session_id: str
    working_directory: str
    pid: int | None = None
    current_process: asyncio.subprocess.Process | None = None
    is_processing: bool = False
    model: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stdout_subscribers: list[StdoutCallback] = field(default_factory=list)

    def subscribe_stdout(self, callback: StdoutCallback):
        if callback not in self.stdout_subscribers:
            self.stdout_subscribers.append(callback)

    def unsubscribe_stdout(self, callback: StdoutCallback):
        if callback in self.stdout_subscribers:
            self.stdout_subscribers.remove(callback)

    async def broadcast_stdout(self, line: str):
        tasks = [cb(line) for cb in self.stdout_subscribers]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def is_alive(self) -> bool:
        """Session is 'alive' if it exists in the manager (not necessarily processing)."""
        return True

    async def terminate(self):
        """Kill the current turn's process if running."""
        if self.current_process and self.current_process.returncode is None:
            try:
                self.current_process.terminate()
                await asyncio.wait_for(self.current_process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.current_process.kill()
                await self.current_process.wait()
            self.current_process = None
            self.is_processing = False


class ProcessManager:
    """Manages Claude Code agent sessions with per-turn process invocation."""

    def __init__(self):
        self._sessions: dict[str, AgentSession] = {}

    async def spawn(
        self,
        session_id: str,
        working_directory: Optional[str] = None,
        resume: bool = False,
        initial_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> AgentSession:
        """Register a new agent session and optionally run the initial prompt.

        Args:
            session_id: Claude session ID (UUID)
            working_directory: Working directory for the process
            resume: Whether resuming an existing session
            initial_prompt: First message to send (runs immediately in background)

        Returns:
            AgentSession instance
        """
        cwd = working_directory or str(Path.home())

        session = AgentSession(
            session_id=session_id,
            working_directory=cwd,
            model=model,
        )
        self._sessions[session_id] = session

        if initial_prompt:
            asyncio.create_task(
                self._run_turn(session, initial_prompt, is_new=not resume, model=model)
            )

        logger.info(f"Registered agent session {session_id} (cwd: {cwd}, resume: {resume})")
        return session

    async def send_message(self, session_id: str, message: str, model: Optional[str] = None) -> bool:
        """Send a follow-up message to an agent session.

        Spawns a new `claude -p --resume` process for this turn.
        Returns False if the session doesn't exist or is already processing.
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        if session.is_processing:
            logger.warning(f"Session {session_id} is already processing, rejecting message")
            return False

        # Update stored model if provided
        if model:
            session.model = model

        asyncio.create_task(self._run_turn(session, message, is_new=False, model=model or session.model))
        return True

    async def _run_turn(self, session: AgentSession, message: str, is_new: bool, model: Optional[str] = None):
        """Execute a single conversation turn as a subprocess.

        Launches claude CLI, streams output to subscribers, and cleans up.
        """
        if not CLAUDE_BINARY:
            logger.error("Claude binary not found — cannot run agent turns")
            await session.broadcast_stdout(json.dumps({
                "type": "error",
                "message": "Claude binary not found. Install Claude Code CLI or VS Code extension.",
            }))
            return

        cmd = [
            str(CLAUDE_BINARY),
            "-p",
            "--output-format", "stream-json",
            "--verbose",
        ]

        # Add model flag if specified
        effective_model = model or getattr(session, "model", None)
        if effective_model:
            cmd.extend(["--model", effective_model])

        if is_new:
            cmd.extend(["--session-id", session.session_id])
        else:
            cmd.extend(["--resume", session.session_id])

        cmd.append(message)

        env = os.environ.copy()
        env.pop("CLAUDECODE", None)

        session.is_processing = True

        # Notify subscribers that processing started
        await session.broadcast_stdout(json.dumps({
            "type": "status",
            "status": "processing",
        }))

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=session.working_directory,
                env=env,
            )
            session.current_process = process
            session.pid = process.pid

            logger.info(f"Turn started for {session.session_id} (PID: {process.pid})")

            # Monitor stderr in background
            asyncio.create_task(self._drain_stderr(session))

            # Stream stdout and parse stream-json
            async for raw_line in process.stdout:
                decoded = raw_line.decode("utf-8").rstrip()
                if not decoded:
                    continue

                try:
                    parsed = json.loads(decoded)
                except json.JSONDecodeError:
                    logger.debug(f"[{session.session_id}] non-json stdout: {decoded}")
                    continue

                msg_type = parsed.get("type")

                if msg_type == "assistant":
                    # Extract text content from assistant message
                    content_blocks = parsed.get("message", {}).get("content", [])
                    text_parts = [
                        b["text"]
                        for b in content_blocks
                        if b.get("type") == "text"
                    ]
                    if text_parts:
                        text = "\n".join(text_parts)
                        await session.broadcast_stdout(json.dumps({
                            "type": "response",
                            "content": text,
                        }))

                elif msg_type == "result":
                    # Turn complete - broadcast cost info if available
                    cost = parsed.get("total_cost_usd")
                    num_turns = parsed.get("num_turns")
                    logger.info(
                        f"Turn complete for {session.session_id}: "
                        f"{num_turns} turns, ${cost:.4f}" if cost else
                        f"Turn complete for {session.session_id}"
                    )

                elif msg_type == "system":
                    # Init message - log but don't broadcast
                    logger.debug(f"[{session.session_id}] init: model={parsed.get('model')}")

            await process.wait()
            logger.info(
                f"Turn process exited for {session.session_id} "
                f"(exit code: {process.returncode})"
            )

        except Exception as e:
            logger.error(f"Error in turn for {session.session_id}: {e}")
            await session.broadcast_stdout(json.dumps({
                "type": "error",
                "message": str(e),
            }))
        finally:
            session.is_processing = False
            session.current_process = None

            # Notify subscribers that processing finished
            await session.broadcast_stdout(json.dumps({
                "type": "status",
                "status": "idle",
            }))

            # Check for queued context and deliver if available
            asyncio.create_task(self._deliver_queued_context(session))

    async def _deliver_queued_context(self, session: AgentSession):
        """After processing completes, check for queued Slack context to deliver."""
        await asyncio.sleep(2)  # Let session settle

        if session.is_processing:
            return  # Already processing again

        try:
            from app.database import async_session as make_session
            from app.services.agent_context_queue import AgentContextQueueService

            async with make_session() as db:
                service = AgentContextQueueService(db)

                # Find agent record for this session
                from app.models.agent import Agent as AgentModel
                result = await db.execute(
                    select(AgentModel).where(
                        AgentModel.claude_session_id == session.session_id
                    )
                )
                agent_row = result.scalar_one_or_none()
                if not agent_row:
                    return

                count = await service.peek(str(agent_row.id))
                if count == 0:
                    return

                items = await service.drain(str(agent_row.id), max_items=20)
                if not items:
                    return

                lines = [f"[Slack Update: {len(items)} new messages while you were working]", ""]
                current_channel = None
                for item in items:
                    if item.channel_name != current_channel:
                        current_channel = item.channel_name
                        lines.append(f"#{current_channel}:")
                    author = item.author or "unknown"
                    content = item.content[:300]
                    priority_marker = " [URGENT]" if item.priority == "high" else ""
                    lines.append(f"  {author}{priority_marker}: {content}")
                lines.append("")
                lines.append("Note this context. No action required unless directly relevant to your current task.")

                await db.commit()

                context_message = "\n".join(lines)
                await self._run_turn(session, context_message, is_new=False)

                logger.info(f"Delivered {len(items)} queued Slack items to session {session.session_id}")

        except Exception as e:
            logger.warning(f"Failed to deliver queued context to {session.session_id}: {e}")

    async def _drain_stderr(self, session: AgentSession):
        """Read and log stderr from the current turn's process."""
        if not session.current_process or not session.current_process.stderr:
            return
        try:
            async for line in session.current_process.stderr:
                decoded = line.decode("utf-8").rstrip()
                if decoded:
                    logger.warning(f"[{session.session_id}] stderr: {decoded}")
        except Exception as e:
            logger.error(f"Error reading stderr for {session.session_id}: {e}")

    def get(self, session_id: str) -> Optional[AgentSession]:
        """Get an agent session by session ID."""
        return self._sessions.get(session_id)

    async def terminate(self, session_id: str) -> bool:
        """Terminate an agent session."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        await session.terminate()
        self._sessions.pop(session_id, None)
        return True

    def list_running(self) -> list[AgentSession]:
        """List all registered agent sessions."""
        return list(self._sessions.values())

    async def shutdown_all(self):
        """Shutdown all agent sessions."""
        tasks = [s.terminate() for s in self._sessions.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._sessions.clear()


# Singleton instance
process_manager = ProcessManager()
