"""Claude Code process detection and management."""

import logging
import re
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClaudeProcess:
    pid: int
    session_id: str
    command: str


def discover_claude_processes() -> list[ClaudeProcess]:
    """Find all running Claude Code processes and extract their session IDs."""
    processes = []

    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            logger.warning("ps aux failed: %s", result.stderr)
            return processes

        # Parse each line looking for claude processes with --resume <session-id>
        for line in result.stdout.splitlines():
            if "claude" not in line or "--resume" not in line:
                continue

            # Extract PID (second field in ps aux output)
            parts = line.split(None, 10)  # Split on whitespace, max 11 fields
            if len(parts) < 11:
                continue

            pid_str = parts[1]
            command = parts[10]

            try:
                pid = int(pid_str)
            except ValueError:
                continue

            # Extract session ID from --resume argument
            match = re.search(r"--resume\s+([a-f0-9-]{36})", command)
            if match:
                session_id = match.group(1)
                processes.append(ClaudeProcess(
                    pid=pid,
                    session_id=session_id,
                    command=command,
                ))

    except subprocess.TimeoutExpired:
        logger.error("ps aux timed out")
    except Exception as e:
        logger.error("Failed to discover claude processes: %s", e)

    logger.info("Discovered %d running Claude Code agents", len(processes))
    return processes


def send_to_agent_stdin(pid: int, message: str) -> bool:
    """Send a message to a Claude Code agent's stdin.

    NOTE: This is currently not possible because Claude Code agents
    communicate via stdin/stdout with VS Code, and the stdin is owned
    by the VS Code process, not accessible to external processes.

    Possible future approaches:
    1. VS Code extension modification to expose a control socket
    2. File-based message queue that agents monitor
    3. HTTP endpoint in Claude Code itself

    For now, this returns False indicating the message cannot be sent.
    """
    logger.warning(
        "send_to_agent_stdin called for PID %d but stdin relay not yet implemented",
        pid,
    )
    # TODO: Implement actual stdin relay mechanism
    return False
