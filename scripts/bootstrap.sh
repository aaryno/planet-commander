#!/usr/bin/env bash
set -euo pipefail

# Planet Commander — First-time setup
# Idempotent: safe to run multiple times

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS_DIR="${HOME}/tools"
TOOLS_REMOTE="git@code.earth.planet.com:aaryn/tools.git"
SLACK_REMOTE="git@code.earth.planet.com:aaryn/slack-tools.git"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

step()  { echo -e "\n${BLUE}${BOLD}==>${NC}${BOLD} $1${NC}"; }
ok()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}!${NC} $1"; }
fail()  { echo -e "  ${RED}✗${NC} $1"; }
info()  { echo -e "  $1"; }

# --------------------------------------------------------------------------
# Step 1: Check prerequisites
# --------------------------------------------------------------------------
step "Checking prerequisites"

errors=0

if command -v docker &>/dev/null; then
    ok "Docker $(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"
else
    fail "Docker not found — install from https://docker.com"
    errors=$((errors + 1))
fi

if command -v node &>/dev/null; then
    node_ver=$(node --version | tr -d 'v')
    node_major=$(echo "$node_ver" | cut -d. -f1)
    if [ "$node_major" -ge 18 ]; then
        ok "Node.js v${node_ver}"
    else
        fail "Node.js v${node_ver} — need ≥18. Run: brew install node"
        errors=$((errors + 1))
    fi
else
    fail "Node.js not found — run: brew install node"
    errors=$((errors + 1))
fi

if command -v python3 &>/dev/null; then
    py_ver=$(python3 --version | grep -oE '[0-9]+\.[0-9]+')
    ok "Python ${py_ver}"
else
    fail "Python 3 not found — run: brew install python"
    errors=$((errors + 1))
fi

if command -v uv &>/dev/null; then
    ok "uv $(uv --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo 'installed')"
else
    fail "uv not found — run: curl -LsSf https://astral.sh/uv/install.sh | sh"
    errors=$((errors + 1))
fi

if [ "$errors" -gt 0 ]; then
    echo ""
    fail "Fix the ${errors} issue(s) above and re-run: make bootstrap"
    exit 1
fi

# --------------------------------------------------------------------------
# Step 2: Test GitLab SSH access
# --------------------------------------------------------------------------
step "Testing GitLab SSH access"

if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new -T git@code.earth.planet.com 2>&1 | grep -qi "welcome\|successfully"; then
    ok "SSH access to code.earth.planet.com"
else
    warn "Could not verify SSH access to code.earth.planet.com"
    warn "Tools cloning may fail — ensure your SSH key is added to GitLab"
fi

# --------------------------------------------------------------------------
# Step 3: Clone tools repos
# --------------------------------------------------------------------------
step "Setting up tools directory"

if [ -d "${TOOLS_DIR}/.git" ]; then
    ok "~/tools/ already cloned — pulling latest"
    git -C "${TOOLS_DIR}" pull --quiet 2>/dev/null || warn "Pull failed (offline?) — using existing"
else
    info "Cloning aaryn/tools → ~/tools/"
    git clone "${TOOLS_REMOTE}" "${TOOLS_DIR}"
    ok "Cloned ~/tools/"
fi

if [ -d "${TOOLS_DIR}/slack/.git" ]; then
    ok "~/tools/slack/ already cloned — pulling latest"
    git -C "${TOOLS_DIR}/slack" pull --quiet 2>/dev/null || warn "Pull failed — using existing"
else
    info "Cloning aaryn/slack-tools → ~/tools/slack/"
    git clone "${SLACK_REMOTE}" "${TOOLS_DIR}/slack"
    ok "Cloned ~/tools/slack/"
fi

# --------------------------------------------------------------------------
# Step 4: Environment file
# --------------------------------------------------------------------------
step "Setting up environment"

cd "${REPO_ROOT}"

if [ -f .env ]; then
    ok ".env already exists"
else
    cp .env.example .env
    ok "Created .env from .env.example"
fi

# --------------------------------------------------------------------------
# Step 5: Install dependencies
# --------------------------------------------------------------------------
step "Installing frontend dependencies"

cd "${REPO_ROOT}/frontend"
if [ -d node_modules ] && [ -f package-lock.json ]; then
    ok "node_modules exists — running npm install to sync"
fi
npm install --silent 2>&1 | tail -1
ok "Frontend dependencies installed"

step "Installing backend dependencies"

cd "${REPO_ROOT}/backend"
uv sync --quiet 2>/dev/null || uv sync
ok "Backend dependencies installed"

# --------------------------------------------------------------------------
# Step 6: Start database
# --------------------------------------------------------------------------
step "Starting PostgreSQL"

cd "${REPO_ROOT}"

if docker compose ps postgres 2>/dev/null | grep -q "running"; then
    ok "PostgreSQL already running on port 9432"
else
    docker compose up -d postgres 2>/dev/null
    info "Waiting for PostgreSQL to be ready..."
    for i in $(seq 1 30); do
        if docker compose exec -T postgres pg_isready -U planet_ops -q 2>/dev/null; then
            break
        fi
        sleep 1
    done
    if docker compose exec -T postgres pg_isready -U planet_ops -q 2>/dev/null; then
        ok "PostgreSQL ready on port 9432"
    else
        fail "PostgreSQL failed to start — check: docker compose logs postgres"
        exit 1
    fi
fi

# --------------------------------------------------------------------------
# Step 7: Run migrations + seed
# --------------------------------------------------------------------------
step "Running database migrations"

cd "${REPO_ROOT}/backend"
uv run alembic upgrade head 2>&1 | tail -3
ok "Migrations applied"

step "Seeding database"

uv run python -m app.seed 2>&1 | tail -5
ok "Database seeded"

# --------------------------------------------------------------------------
# Step 8: Summary
# --------------------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}Planet Commander is ready!${NC}"
echo ""
echo -e "${BOLD}Start the app:${NC}"
echo "  make start              # Backend (9000) + Frontend (3000)"
echo "  make dev-local          # Postgres+Frontend in Docker, backend native"
echo ""
echo -e "${BOLD}URLs:${NC}"
echo "  Frontend:   http://localhost:3000"
echo "  Backend:    http://localhost:9000"
echo "  API Docs:   http://localhost:9000/docs"
echo ""
echo -e "${BOLD}Optional: Add auth tokens for full functionality${NC}"
echo ""
echo "  ┌──────────────┬─────────────────────────────────────────┬─────────────────────────────┐"
echo "  │ Service      │ How to configure                        │ Features unlocked           │"
echo "  ├──────────────┼─────────────────────────────────────────┼─────────────────────────────┤"
echo "  │ Grafana      │ export GRAFANA_API_TOKEN=...            │ Pipeline metrics, heartbeat │"
echo "  │              │ or: ~/.config/grafana-token             │                             │"
echo "  ├──────────────┼─────────────────────────────────────────┼─────────────────────────────┤"
echo "  │ PagerDuty    │ echo TOKEN > ~/.config/pagerduty-token  │ Incident tracking           │"
echo "  ├──────────────┼─────────────────────────────────────────┼─────────────────────────────┤"
echo "  │ JIRA         │ ~/.jira/config (host, token, project)   │ Ticket summaries, sync      │"
echo "  ├──────────────┼─────────────────────────────────────────┼─────────────────────────────┤"
echo "  │ GitLab       │ glab auth login                         │ MR reviews, CI status        │"
echo "  ├──────────────┼─────────────────────────────────────────┼─────────────────────────────┤"
echo "  │ Slack        │ ~/tools/slack/slack-config.json          │ Thread analysis, summaries  │"
echo "  ├──────────────┼─────────────────────────────────────────┼─────────────────────────────┤"
echo "  │ Anthropic    │ export ANTHROPIC_API_KEY=sk-ant-...     │ Coach sessions, MR audits   │"
echo "  └──────────────┴─────────────────────────────────────────┴─────────────────────────────┘"
echo ""
echo "  None of these are required — the app runs without them."
echo "  Add them as needed to unlock specific integrations."
echo ""
