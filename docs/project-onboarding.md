# Project Onboarding — Agent Instructions

This document tells an agent (or human) how to onboard a project into Planet Commander. The agent reads this, explores the user's environment, and creates a Project entity via the API.

**Key principle**: Map to what exists. Never ask the user to reorganize their files, duplicate docs, or adopt a new structure. Commander adapts to them.

---

## Quick Version (for agents with full context)

If you already know the project's repos, JIRA keys, Slack channels, and monitoring — just POST:

```bash
curl -X POST http://localhost:9000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "key": "my-project",
    "name": "My Project",
    "description": "What this project does in one sentence",
    "color": "#3B82F6",
    "jira_project_keys": ["MYPROJ"],
    "jira_default_filters": {
      "label_filters": ["bug", "feature", "incident"],
      "quick_filters": [
        {"name": "My Tickets", "jql": "assignee = currentUser() AND resolution = Unresolved"},
        {"name": "In Review", "jql": "status = \"In Review\""}
      ]
    },
    "repositories": [
      {"path": "group/repo", "name": "Main Repo"}
    ],
    "grafana_dashboards": [
      {"name": "Overview", "url": "https://grafana.example.com/d/abc123"}
    ],
    "pagerduty_service_ids": ["PXXXXXX"],
    "slack_channels": [
      {"name": "#my-project", "purpose": "general"},
      {"name": "#my-project-alerts", "purpose": "alerts"}
    ],
    "deployment_config": {
      "type": "argocd",
      "cluster": "prod-cluster",
      "namespaces": ["my-project-prod", "my-project-staging"]
    },
    "links": [
      {"category": "docs", "label": "Architecture", "url": "https://..."},
      {"category": "runbook", "label": "On-Call Runbook", "url": "https://..."}
    ]
  }'
```

Done. The project appears in Commander immediately.

---

## Guided Version (for agents discovering context)

When you don't know the project details upfront, walk through these steps. At each step, try to auto-discover before asking the user.

### Step 1: Identify the project

Ask the user:
- "What's the short key for this project?" (e.g., `wx`, `g4`, `my-service`) — lowercase, no spaces
- "What's the full name?" (e.g., "Work Exchange", "Imagery Pipeline")
- "One sentence: what does it do?"

Pick a color. Use one that's visually distinct from existing projects:
```bash
curl -s http://localhost:9000/api/projects | python3 -c "
import sys, json
for p in json.load(sys.stdin):
    print(f'  {p[\"key\"]}: {p[\"color\"]}')
"
```

Suggested palette for new projects: `#EC4899` (pink), `#14B8A6` (teal), `#F97316` (orange), `#6366F1` (indigo), `#EF4444` (red), `#84CC16` (lime).

### Step 2: Find repositories

**Auto-discover**: If the user points to a directory:
```bash
# Scan a directory for git repos
find /path/to/code -maxdepth 3 -name .git -type d | while read gitdir; do
  repo=$(dirname "$gitdir")
  remote=$(git -C "$repo" remote get-url origin 2>/dev/null)
  name=$(basename "$repo")
  echo "$name | $repo | $remote"
done
```

**From the remote URL**, extract the GitLab path:
- `git@code.earth.planet.com:wx/wx.git` → path: `wx/wx`
- `git@github.com:org/repo.git` → path: `org/repo`

**Ask if not found**: "What GitLab repos belong to this project? Give me the paths (e.g., `wx/wx`, `product/g4`)."

Build the repositories array:
```json
[
  {"path": "wx/wx", "name": "WX Core", "local_path": "/Users/chad/code/wx/wx"},
  {"path": "wx/eso-golang", "name": "ESO SDK"}
]
```

### Step 3: JIRA configuration

**Auto-discover**: Look for JIRA config:
```bash
# Check for existing JIRA config
cat ~/.jira/config 2>/dev/null
# Check for JIRA references in project docs
grep -r "JIRA\|jira\|COMPUTE-\|PROJ-" /path/to/repo/CLAUDE.md 2>/dev/null | head -5
```

**Ask**: "What JIRA project key(s) does your team use? (e.g., COMPUTE, PLATFORM)"

**For filters**, ask: "What ticket labels or categories matter to you?" Common ones:
- `bug`, `feature`, `incident`, `tech-debt`, `documentation`
- Sprint/board-specific labels

Build the config:
```json
{
  "jira_project_keys": ["COMPUTE"],
  "jira_default_filters": {
    "label_filters": ["incident", "feature", "bug", "tech-debt"],
    "quick_filters": [
      {"name": "My Tickets", "jql": "assignee = currentUser() AND resolution = Unresolved"},
      {"name": "Sprint", "jql": "sprint in openSprints()"},
      {"name": "In Review", "jql": "status = 'In Review'"},
      {"name": "Blocked", "jql": "status = 'Blocked'"}
    ]
  }
}
```

### Step 4: Team & communication

**Auto-discover**: If Slack tools are available:
```bash
# List channels the user is in
ls ~/tools/slack/data/messages/ 2>/dev/null | head -20
```

**Ask**: "What Slack channels does your team use?"

Categorize by purpose:
```json
[
  {"name": "#my-project", "purpose": "general"},
  {"name": "#my-project-alerts", "purpose": "alerts"},
  {"name": "#my-team", "purpose": "team"},
  {"name": "#my-project-oncall", "purpose": "oncall"}
]
```

### Step 5: Monitoring & alerts

**Auto-discover from repo**: Look for Grafana/PagerDuty references:
```bash
# Check for alert definitions in Terraform
find /path/to/repo -name "*.tf" -exec grep -l "grafana\|pagerduty\|alert" {} \;
# Check CLAUDE.md for dashboard links
grep -i "grafana\|dashboard\|pagerduty\|alert" /path/to/repo/CLAUDE.md 2>/dev/null
```

**Auto-discover from Grafana** (if token available):
```bash
# Search Grafana for dashboards mentioning the project
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "https://planet.grafana.net/api/search?query=${PROJECT_KEY}" | python3 -m json.tool
```

**Ask if not found**: "Do you have Grafana dashboards? PagerDuty services?"

### Step 6: Deployments

**Auto-discover**: Check for deployment config:
```bash
# ArgoCD applications
kubectl get applications -n argocd 2>/dev/null | grep -i "${PROJECT_KEY}"
# Check for deploy directories in repo
ls /path/to/repo/deploy/ /path/to/repo/k8s/ /path/to/repo/terraform/ 2>/dev/null
```

**Ask**: "How is this project deployed? (ArgoCD, Kubernetes, Terraform, other, none)"

```json
{
  "type": "argocd",
  "cluster": "prod-cluster",
  "namespaces": ["my-project-prod", "my-project-staging"],
  "argocd_app": "my-project"
}
```

### Step 7: Context mapping

**This is the key step.** Map the user's existing context files to Commander — don't copy or reorganize.

**Auto-discover**: Look for project documentation:
```bash
# Check for CLAUDE.md in repos
find /path/to/repos -maxdepth 2 -name "CLAUDE.md" -o -name "README.md" | head -10

# Check for progressive disclosure layers
ls ~/claude/v2/projects/*${PROJECT_KEY}* 2>/dev/null
ls ~/claude/projects/*${PROJECT_KEY}* 2>/dev/null

# Check for project-specific notes
find ~ -maxdepth 4 -path "*/claude/*${PROJECT_KEY}*" -name "*.md" 2>/dev/null | head -10
```

Build links for discovered docs:
```json
[
  {"category": "docs", "label": "CLAUDE.md", "url": "/path/to/repo/CLAUDE.md"},
  {"category": "docs", "label": "Architecture", "url": "/path/to/docs/architecture.md"},
  {"category": "runbook", "label": "On-Call Runbook", "url": "https://wiki.example.com/runbook"},
  {"category": "context", "label": "Project Index", "url": "~/claude/v2/projects/WX-INDEX.md"}
]
```

### Step 8: Adjacent teams (service graph)

**Auto-discover**: From PagerDuty escalation policies and Slack channel membership:
```bash
# Who else is in your alert channels?
# What services page your team?
# What repos have cross-references to your project?
grep -r "import.*${PROJECT_KEY}\|from.*${PROJECT_KEY}" /path/to/other/repos 2>/dev/null
```

**Ask**: "What teams do you depend on? What teams depend on you?"

Store as links:
```json
[
  {"category": "team", "label": "Platform Ops", "url": "#hobbes", "relationship": "depends_on"},
  {"category": "team", "label": "Data Pipeline", "url": "#data-pipeline", "relationship": "depended_by"}
]
```

### Step 9: Create the project

Combine everything from steps 1-8 into a single POST:

```bash
curl -X POST http://localhost:9000/api/projects \
  -H "Content-Type: application/json" \
  -d '{ ... combined JSON ... }'
```

### Step 10: Verify and iterate

```bash
# Verify the project was created
curl -s http://localhost:9000/api/projects/${KEY} | python3 -m json.tool

# Open in Commander
echo "Open http://localhost:3000/projects/${KEY}"
```

**Tell the user**: "Your project is set up. You can edit any of these settings at `/projects/${KEY}/settings`. To re-scan and update the mapping, run this onboarding again with `--update`."

---

## Regeneration / Re-scan

To update an existing project's mapping (new repos added, new dashboards, team changes):

```bash
# Re-run discovery steps 2-8, then PATCH:
curl -X PUT http://localhost:9000/api/projects/${KEY} \
  -H "Content-Type: application/json" \
  -d '{ ... updated fields only ... }'
```

Only send fields that changed — the API merges, not replaces.

---

## API Reference

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/projects` | List all projects |
| `GET` | `/api/projects/{key}` | Get project config |
| `POST` | `/api/projects` | Create project |
| `PUT` | `/api/projects/{key}` | Update project (partial) |
| `DELETE` | `/api/projects/{key}` | Soft-delete |
| `GET` | `/api/projects/{key}/links` | Get links by category |

## Schema Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `key` | string | yes | Short identifier (lowercase, no spaces) |
| `name` | string | yes | Display name |
| `description` | string | no | One-sentence description |
| `color` | string | no | Hex color for badges (default: `#6366F1`) |
| `jira_project_keys` | string[] | no | JIRA project keys (e.g., `["COMPUTE"]`) |
| `jira_default_filters` | object | no | `{label_filters: string[], quick_filters: [{name, jql}]}` |
| `repositories` | object[] | no | `[{path, name, local_path?}]` |
| `grafana_dashboards` | object[] | no | `[{name, url, dashboard_id?}]` |
| `pagerduty_service_ids` | string[] | no | PagerDuty service IDs |
| `slack_channels` | object[] | no | `[{name, purpose}]` — purpose: general, alerts, team, oncall |
| `deployment_config` | object | no | `{type, cluster, namespaces, argocd_app?}` |
| `links` | object[] | no | `[{category, label, url, icon?, relationship?}]` |
| `sort_order` | int | no | Display order (default: 0) |
