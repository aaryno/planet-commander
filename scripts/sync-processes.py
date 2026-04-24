#!/usr/bin/env python3
"""Sync running Claude Code processes to the dashboard backend.

This script runs on the HOST machine (not in Docker) and discovers
Claude Code processes, then updates the backend via API.

Usage:
    python3 scripts/sync-processes.py
"""

import re
import subprocess
import requests

BACKEND_URL = "http://localhost:9000"


def discover_claude_processes():
    """Find all running Claude Code processes on the host."""
    processes = []

    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            print(f"ps aux failed: {result.stderr}")
            return processes

        for line in result.stdout.splitlines():
            if "claude" not in line or "--resume" not in line:
                continue

            parts = line.split(None, 10)
            if len(parts) < 11:
                continue

            pid_str = parts[1]
            command = parts[10]

            try:
                pid = int(pid_str)
            except ValueError:
                continue

            match = re.search(r"--resume\s+([a-f0-9-]{36})", command)
            if match:
                session_id = match.group(1)
                processes.append({
                    "pid": pid,
                    "session_id": session_id,
                })

    except Exception as e:
        print(f"Error: {e}")

    return processes


def main():
    processes = discover_claude_processes()
    print(f"Found {len(processes)} Claude Code processes")

    if not processes:
        print("No processes to sync")
        # Still POST empty list to clear stale entries
        try:
            response = requests.post(
                f"{BACKEND_URL}/api/processes/update",
                json={"processes": []},
                timeout=5,
            )
            response.raise_for_status()
            print("Cleared process cache")
        except Exception as e:
            print(f"Failed to clear cache: {e}")
        return

    # POST to backend
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/processes/update",
            json={"processes": processes},
            timeout=5,
        )
        response.raise_for_status()
        result = response.json()
        print(f"✓ Synced {result['received']} processes to backend")

        # Show first few for debugging
        for p in processes[:5]:
            print(f"  PID {p['pid']}: {p['session_id']}")

        if len(processes) > 5:
            print(f"  ... and {len(processes) - 5} more")

    except Exception as e:
        print(f"Failed to sync processes: {e}")


if __name__ == "__main__":
    main()
