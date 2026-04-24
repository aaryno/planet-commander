#!/bin/bash
# Run backend locally on macOS host (not in Docker)
# This allows the backend to execute the native Claude binary

set -e

# Ensure common tool paths are available
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Export environment variables for local backend
export PLANET_OPS_DATABASE_URL="postgresql+asyncpg://planet_ops:planet_ops_local@localhost:9432/planet_ops"
export PLANET_OPS_DATABASE_URL_SYNC="postgresql://planet_ops:planet_ops_local@localhost:9432/planet_ops"
export PLANET_OPS_CLAUDE_DIR="$HOME/.claude"
export PLANET_OPS_CLAUDE_PROJECTS_DIR="$HOME/.claude/projects"
export PLANET_OPS_WORKSPACES_DIR="$HOME/workspaces"
export PLANET_OPS_TOOLS_DIR="$HOME/tools"
export PLANET_OPS_CLAUDE_DOCS_DIR="$HOME/claude"
export PLANET_OPS_GRAFANA_TOKEN_PATH="$HOME/.config/grafana-token"
export PLANET_OPS_PAGERDUTY_TOKEN_PATH="$HOME/.config/pagerduty-token"
export PLANET_OPS_GDRIVE_SHARED="$HOME/Library/CloudStorage/GoogleDrive-*/Shared drives"

# Run migrations
echo "Running database migrations..."
uv run alembic upgrade head

# Start the server
echo "Starting backend on http://localhost:9000"
uv run uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload
