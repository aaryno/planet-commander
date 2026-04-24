#!/bin/bash
# Continuously sync Claude Code processes to backend
# Run this in the background: ./scripts/sync-processes-loop.sh &

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INTERVAL=30  # seconds between syncs

echo "Starting process sync loop (every ${INTERVAL}s)..."
echo "Press Ctrl+C to stop"

while true; do
    python3 "$SCRIPT_DIR/sync-processes.py" 2>&1 | while read line; do
        echo "[$(date +%H:%M:%S)] $line"
    done
    sleep $INTERVAL
done
