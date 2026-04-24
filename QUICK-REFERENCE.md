# Planet Commander - Quick Reference Guide

**Version**: Phases 2-5 Complete
**Last Updated**: 2026-03-17

---

## 🚀 Quick Start

### Start the System

**Recommended (using Make):**

```bash
cd ~/claude/dashboard

# Start both backend + frontend together
make start

# Or start individually:
make start-backend   # Backend only (port 9000)
make start-frontend  # Frontend only (port 3000)

# Stop everything
make stop

# See all commands
make help
```

**Manual start (if needed):**

```bash
# Terminal 1: Backend
cd ~/claude/dashboard/backend
uvicorn app.main:app --reload

# Terminal 2: Frontend
cd ~/claude/dashboard/frontend
npm run dev

# Terminal 3: CLI
commander status
```

### Environment Variables

```bash
export ANTHROPIC_API_KEY=sk-ant-...  # For AI summaries
export DATABASE_URL=postgresql://postgres:postgres@localhost:9432/planet_ops
```

---

## 📋 CLI Commands

### Repository Scanning

```bash
# Scan branches
commander scan branches ~/code/wx/wx
commander scan branches ~/code/product/g4-wk/g4

# Scan worktrees
commander scan worktrees ~/code/wx/wx
```

### JIRA Synchronization

```bash
# Default sync (uses config.yaml queries)
commander sync jira

# Custom JQL
commander sync jira --jql "project = COMPUTE AND status = 'In Progress'"
commander sync jira --jql "assignee = currentUser()" --max-results 50
```

### Link Inference

```bash
# Run link inference manually
commander infer links

# Output shows:
# ✓ Created 15 suggested links
#   - Branch→JIRA: 12
#   - Chat→JIRA: 3
```

### Job Status

```bash
# Show all recent jobs
commander status

# Show specific job
commander status --job-name git_scanner

# Show more history
commander status --limit 50
```

---

## 🔌 API Quick Reference

### Base URL
```
http://localhost:8000/api
```

### Health Audits

```bash
# Audit all contexts
curl http://localhost:8000/api/health/audit

# Audit specific context
curl http://localhost:8000/api/health/audit/{context-id}

# Find stale contexts (30+ days)
curl http://localhost:8000/api/health/stale?days=30

# Find orphaned entities
curl http://localhost:8000/api/health/orphaned

# Mark stale as orphaned (60+ days)
curl -X POST http://localhost:8000/api/health/mark-orphaned?days=60
```

### AI Summaries

```bash
# Summarize chat
curl -X POST http://localhost:8000/api/summaries/chat/{chat-id}

# Force regenerate
curl -X POST http://localhost:8000/api/summaries/chat/{chat-id}?force_regenerate=true

# Get existing summary
curl http://localhost:8000/api/summaries/chat/{chat-id}

# Generate context overview
curl -X POST http://localhost:8000/api/summaries/context/{context-id}
```

### Artifact Extraction

```bash
# Extract artifacts from chat
curl -X POST http://localhost:8000/api/summaries/artifacts/chat/{chat-id}

# Get code snippets only
curl http://localhost:8000/api/summaries/artifacts/chat/{chat-id}?artifact_type=code_snippet

# Get all artifacts for context
curl http://localhost:8000/api/summaries/artifacts/context/{context-id}
```

### PR/MR Automation

```bash
# Create PR from chat
curl -X POST "http://localhost:8000/api/automation/pr/chat/{chat-id}?target_branch=main&auto_push=true"

# Create PR from context
curl -X POST "http://localhost:8000/api/automation/pr/context/{context-id}?target_branch=main"
```

### JIRA Automation

```bash
# Sync context status to JIRA
curl -X POST http://localhost:8000/api/automation/jira/sync-context/{context-id}

# Add comment to all linked tickets
curl -X POST http://localhost:8000/api/automation/jira/comment-context/{context-id} \
  -H "Content-Type: application/json" \
  -d '{"comment": "Development complete, ready for review"}'
```

### Slack Notifications

```bash
# Notify about new PR
curl -X POST http://localhost:8000/api/automation/slack/notify-pr \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "compute-platform",
    "pr_url": "https://hello.planet.com/code/wx/wx/-/merge_requests/123",
    "title": "COMPUTE-1234: OAuth integration",
    "author": "aaryn",
    "jira_key": "COMPUTE-1234"
  }'

# Notify about status change
curl -X POST http://localhost:8000/api/automation/slack/notify-status-change \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "compute-platform",
    "context_title": "OAuth Integration",
    "old_status": "active",
    "new_status": "done",
    "jira_keys": ["COMPUTE-1234"]
  }'

# Notify about health alert
curl -X POST http://localhost:8000/api/automation/slack/notify-health-alert \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "compute-platform",
    "context_title": "OAuth Integration",
    "health_status": "red",
    "issues": ["No linked branch", "Stale: no updates in 45 days"]
  }'
```

### GitLab Automation

```bash
# Approve MR
curl -X POST "http://localhost:8000/api/automation/gitlab/approve-mr?project=wx%2Fwx&mr_iid=123"

# Merge MR
curl -X POST "http://localhost:8000/api/automation/gitlab/merge-mr?project=wx%2Fwx&mr_iid=123&when_pipeline_succeeds=true"

# Check MR status
curl "http://localhost:8000/api/automation/gitlab/mr-status?project=wx%2Fwx&mr_iid=123"

# Auto-approve and merge
curl -X POST "http://localhost:8000/api/automation/gitlab/auto-approve-merge?project=wx%2Fwx&mr_iid=123"
```

### Background Jobs

```bash
# List job runs
curl http://localhost:8000/api/jobs/runs?limit=20

# Get job status
curl http://localhost:8000/api/jobs/status

# Trigger job manually
curl -X POST http://localhost:8000/api/jobs/trigger/git_scanner
curl -X POST http://localhost:8000/api/jobs/trigger/jira_sync
curl -X POST http://localhost:8000/api/jobs/trigger/link_inference
curl -X POST http://localhost:8000/api/jobs/trigger/health_audit
```

---

## ⚙️ Configuration

### Background Jobs (`backend/config.yaml`)

```yaml
background_jobs:
  enabled: true

  git_scanner:
    enabled: true
    schedule_minutes: 30
    repositories:
      - path: /Users/aaryn/code/wx/wx
        name: wx
      - path: /Users/aaryn/code/product/g4-wk/g4
        name: g4

  jira_sync:
    enabled: true
    schedule_minutes: 15
    queries:
      - name: active_compute
        jql: 'project = COMPUTE AND status IN ("In Progress", "In Review")'
        max_results: 100

  link_inference:
    enabled: true
    schedule_hours: 1
    min_confidence: 0.7

  health_audit:
    enabled: true
    schedule_hours: 6
```

### Frontend API Usage

```typescript
import { api } from "@/lib/api";

// Health
const health = await api.healthAuditAll();
const stale = await api.healthStaleContexts(30);
const orphaned = await api.healthOrphanedEntities();

// Summaries
const summary = await api.summarizeChat(chatId);
const overview = await api.generateContextOverview(contextId);
const artifacts = await api.extractChatArtifacts(chatId);

// Automation
const pr = await api.createPRFromChat(chatId, "main", true);
await api.syncContextToJira(contextId);
await api.notifyPRCreated("compute-platform", prUrl, title, author);
await api.approveMR("wx/wx", 123);
await api.autoApproveMergeMR("wx/wx", 123);
```

---

## 🎨 Dashboard Widgets

### Import All Widgets

```typescript
import {
  SuggestedLinksCard,
  BackgroundJobsCard,
  HealthAuditCard,
  StaleContextsCard,
  OrphanedEntitiesCard,
} from "@/components/widgets";
```

### Basic Layout

```tsx
<div className="grid grid-cols-2 gap-6">
  <HealthAuditCard />
  <StaleContextsCard />
  <SuggestedLinksCard />
  <BackgroundJobsCard />
</div>
```

### Widget Features

| Widget | Auto-Refresh | Actions |
|--------|--------------|---------|
| HealthAuditCard | 5 min | Refresh, Run Audit |
| StaleContextsCard | 5 min | Refresh, Mark Orphaned |
| OrphanedEntitiesCard | 5 min | Refresh |
| BackgroundJobsCard | 1 min | Refresh, Trigger |
| SuggestedLinksCard | 5 min | Refresh, Confirm All |

---

## 🏃 Common Workflows

### Workflow 1: Create Branch → PR

```bash
# 1. Create branch with JIRA key
git checkout -b ao/COMPUTE-1234-oauth

# 2. Wait ~1 hour for background jobs (or trigger manually)
commander infer links

# 3. Confirm suggested link in dashboard
# (Or via API: POST /api/links/batch-confirm)

# 4. After development, create PR
curl -X POST "http://localhost:8000/api/automation/pr/chat/{chat-id}?auto_push=true"

# 5. Notify Slack
curl -X POST http://localhost:8000/api/automation/slack/notify-pr -d '{...}'

# 6. Auto-approve and merge when ready
curl -X POST "http://localhost:8000/api/automation/gitlab/auto-approve-merge?..."
```

### Workflow 2: Health Monitoring

```bash
# 1. Run health audit
curl -X POST http://localhost:8000/api/health/audit

# 2. Check stale contexts
curl http://localhost:8000/api/health/stale?days=30

# 3. Mark very stale as orphaned
curl -X POST http://localhost:8000/api/health/mark-orphaned?days=60

# 4. Send alerts for red health contexts
curl -X POST http://localhost:8000/api/automation/slack/notify-health-alert -d '{...}'
```

### Workflow 3: Generate Documentation

```bash
# 1. Extract artifacts from chat
curl -X POST http://localhost:8000/api/summaries/artifacts/chat/{chat-id}

# 2. Get code snippets
curl "http://localhost:8000/api/summaries/artifacts/chat/{chat-id}?artifact_type=code_snippet"

# 3. Generate summary
curl -X POST http://localhost:8000/api/summaries/chat/{chat-id}

# 4. Generate context overview
curl -X POST http://localhost:8000/api/summaries/context/{context-id}
```

---

## 🐛 Troubleshooting

### CLI Not Found

```bash
# Reinstall entry point
cd backend
pip install -e .
commander --help
```

### Background Jobs Not Running

```bash
# Check job status
commander status

# Check backend logs
# Jobs register on startup - look for:
# "Background jobs registered: git_scanner (30m), jira_sync (15m), ..."

# Trigger manually to test
curl -X POST http://localhost:8000/api/jobs/trigger/git_scanner
```

### AI Summaries Failing

```bash
# Check ANTHROPIC_API_KEY is set
echo $ANTHROPIC_API_KEY

# Check backend logs for Claude API errors
# Summaries fall back to simple summaries if API fails
```

### Slack Notifications Not Sending

```bash
# Check if slack CLI is available
which slack

# If not available, notifications will be logged but not sent
# This is intentional - Slack is optional, won't fail workflows

# To enable: Install slack CLI or configure webhook
```

### GitLab Automation Not Working

```bash
# Check glab CLI is configured
glab --version
glab auth status

# Ensure glab is authenticated with hello.planet.com
glab auth login
```

---

## 📊 Health Score Reference

### Score Calculation (0.0 - 1.0)

```
+0.3  Has primary entity (JIRA or chat)
+0.2  Has linked entities
+0.2  Has active branch
+0.1  Has active worktree
+0.2  Recent activity (<7 days)
────
1.0   Maximum score
```

### Status Thresholds

- **🟢 Green** (0.8-1.0): Healthy, complete
- **🟡 Yellow** (0.5-0.79): Functional, incomplete
- **🔴 Red** (0.0-0.49): Problematic, needs attention

---

## 🔗 Artifact Types

| Type | Description | Example |
|------|-------------|---------|
| `code_snippet` | Code blocks | Python functions, React components |
| `command` | Shell commands | `git commit -m "..."`, `npm install` |
| `config` | Configuration | JSON, YAML, env vars |
| `sql_query` | SQL queries | SELECT, UPDATE statements |
| `error_message` | Error logs | Stack traces, error messages |
| `url` | URLs | GitHub, JIRA, docs |
| `file_path` | File paths | `/path/to/file.py` |
| `decision` | Decisions | Architectural choices |

---

## 📦 Database Migrations

### Apply Migrations

```bash
cd backend
alembic upgrade head
```

### Check Current Version

```bash
alembic current
# Should show: 20260318_0305 (head)
```

### Migration History

```
20260318_0305 -> create_artifacts_table
20260318_0302 -> create_summaries_table
20260317_1855 -> ... (Phase 1 migrations)
```

---

## 🎯 Key Files Reference

### Configuration
- `backend/config.yaml` - Background job configuration
- `backend/pyproject.toml` - Python dependencies, CLI entry point

### CLI
- `backend/app/cli.py` - Commander CLI implementation

### Services
- `backend/app/services/health_audit.py` - Health scoring
- `backend/app/services/chat_summary.py` - AI chat summaries
- `backend/app/services/context_overview.py` - AI context overviews
- `backend/app/services/artifact_extraction.py` - Artifact extraction
- `backend/app/services/pr_automation.py` - PR/MR creation
- `backend/app/services/jira_sync_automation.py` - JIRA sync
- `backend/app/services/slack_notifications.py` - Slack notifications
- `backend/app/services/gitlab_automation.py` - GitLab automation

### Widgets
- `frontend/src/components/widgets/HealthAuditCard.tsx`
- `frontend/src/components/widgets/StaleContextsCard.tsx`
- `frontend/src/components/widgets/OrphanedEntitiesCard.tsx`
- `frontend/src/components/widgets/SuggestedLinksCard.tsx` (Phase 2)
- `frontend/src/components/widgets/BackgroundJobsCard.tsx` (Phase 2)

---

## 🔐 Security Notes

### TODO Flags (Safety)

Before production, review these TODO flags in code:

1. **JIRA Updates** (`jira_sync_automation.py`)
   - Line ~50: Remove `# TODO:` before `update_ticket_status()`
   - Line ~70: Remove `# TODO:` before `add_comment()`

2. **Slack Webhooks** (`slack_notifications.py`)
   - Consider using webhooks instead of CLI for production

### API Keys

Never commit API keys to git:
- `ANTHROPIC_API_KEY` - Via environment variable only
- Slack tokens - Via environment variable
- GitLab tokens - Via glab auth (stored in `~/.config/glab-cli/`)

---

## 📝 Version History

- **2026-03-17 20:26** - Phases 2-5 complete (this version)
- **2026-03-17 20:05** - Phases 2-3 complete
- **2026-03-17 18:00** - Phase 2 complete
- **2026-03-17 16:00** - Phase 1 complete

---

## 🚀 Next Steps

1. **Deploy** - Set up production environment
2. **Configure** - Update `config.yaml` for your repos
3. **Enable** - Set ANTHROPIC_API_KEY for AI features
4. **Test** - Run `commander status` to verify jobs
5. **Monitor** - Use dashboard widgets to track health
6. **Automate** - Set up PR automation workflows

For detailed documentation, see:
- `/Users/aaryn/claude/artifacts/20260317-2026-planet-commander-phases2-5-FINAL-COMPLETE.md`
- `~/claude/dashboard/CLAUDE.md`
- `~/claude/dashboard/DASHBOARD-WIDGETS-EXAMPLE.md`

---

**Questions?** Check the implementation artifacts or run `commander --help`.
