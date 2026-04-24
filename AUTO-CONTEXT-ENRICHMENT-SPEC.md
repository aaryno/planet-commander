# Auto-Context Enrichment — Comprehensive Specification

**Created**: 2026-03-18
**Purpose**: Automatically enrich Commander work contexts with cross-system intelligence
**Status**: Planning — extends Slack Context Parser pattern to all systems

---

## Vision

When you start work from **any entry point** (JIRA ticket, Slack message, agent chat, uploaded doc), Commander should automatically:

1. **Detect cross-references** across all systems
2. **Fetch related context** from Planet's engineering ecosystem
3. **Link artifacts** from prior investigations and discussions
4. **Load project knowledge** from ~/claude structure
5. **Surface relevant tools** (dashboards, runbooks, skills)
6. **Build a coherent work context** ready for human or agent operation

---

## Auto-Context Sources

### ✅ Already Implemented

| Source | Status | Implementation |
|--------|--------|----------------|
| **Agent Sessions** | ✅ Complete | Database models, API, UI |
| **JIRA Issues** | 🟡 Partial | Cached in DB, needs enrichment |
| **WX Deployments** | ✅ Complete | Real-time K8s SSE |

### 🚧 In Progress (Slack Parser)

| Source | Status | Implementation |
|--------|--------|----------------|
| **Slack Threads** | 🚧 Spec'd | [SLACK-CONTEXT-PARSER-SPEC.md](./SLACK-CONTEXT-PARSER-SPEC.md) |

### 📋 Planned (This Spec)

| Source | Priority | Complexity | Impact |
|--------|----------|------------|--------|
| **PagerDuty Incidents** | HIGH | Low | High — incident context |
| **Grafana Alerts** | HIGH | Medium | High — alert definitions + history |
| **Google Drive Docs** | HIGH | Medium | High — RFDs, postmortems, planning |
| **GitLab MRs** | MEDIUM | Low | Medium — code review context |
| **Artifacts** | MEDIUM | Medium | High — prior investigations |
| **Project Claude Docs** | MEDIUM | Low | High — auto-load context |
| **Skills** | LOW | Low | Medium — auto-suggest tools |
| **Calendar** | LOW | High | Low — meeting context |
| **Email** | LOW | High | Low — incident notifications |

---

## Entry Point Auto-Context Workflows

### 1. Starting from JIRA Ticket

**Trigger**: User opens JIRA ticket in Commander (or mentions ticket key)

**Auto-detect and fetch**:

```
JIRA Ticket (COMPUTE-1234)
├── Slack threads (from description/comments)
├── PagerDuty incidents (from description/comments)
├── Google Drive docs (from description/comments)
├── GitLab MRs (from description/comments)
├── Related artifacts (matching ticket key in filename)
├── Project context (~/claude/projects/{project}-notes/{project}-claude.md)
├── Grafana dashboards (for project)
├── Prior investigations (search artifacts for similar issues)
├── Related JIRA tickets (blocks/blocked-by, parent/subtasks)
├── On-call contacts (if severity/incident mentioned)
└── Recommended skills (based on ticket type/labels)
```

**Implementation**:
- Regex parsers for each reference type (like Slack parser)
- Background job to scan active tickets
- Store links in `entity_links` table
- Generate context summary

**Example**: `COMPUTE-1234` contains:
- Slack URL → Fetch thread, parse incident discussion
- "PD-ABC123" → Fetch PagerDuty incident timeline
- Link to Google Doc → Fetch doc metadata, link in context
- Label "wx" → Load `wx-claude.md`, link WX dashboards
- "SEV2" → Fetch on-call contacts, link incident response skill

---

### 2. Starting from Slack Message

**Trigger**: User pastes Slack URL or starts agent with Slack context

**Auto-detect and fetch**:

```
Slack Thread
├── JIRA tickets (mentioned in thread)
├── PagerDuty incidents (links in thread)
├── GitLab MRs (links in thread)
├── Google Drive docs (links in thread)
├── Cross-channel references (follow other channels)
├── Surrounding context (±24hr if incident)
├── Alert definitions (if from #compute-platform)
├── Related artifacts (search by date/keywords)
├── Project context (infer from channel → project mapping)
├── Team context (channel → team mapping)
└── Recommended skills (detect incident patterns)
```

**Implementation**:
- Already spec'd in [SLACK-CONTEXT-PARSER-SPEC.md](./SLACK-CONTEXT-PARSER-SPEC.md)
- Add project/team inference from channel
- Add artifact search by date + keywords

**Channel → Project Mapping**:
| Channel | Project | Claude Doc |
|---------|---------|------------|
| `#wx-dev`, `#wx-users` | WX | `wx-notes/wx-claude.md` |
| `#g4-users` | G4 | `g4-notes/g4-claude.md` |
| `#jobs-users` | Jobs | `jobs-notes/jobs-claude.md` |
| `#temporalio-cloud` | Temporal | `temporal-notes/temporal-claude.md` |
| `#compute-platform` | Multi-project | Load all |

---

### 3. Starting from Agent Chat

**Trigger**: User starts new chat or uploads context to existing chat

**Auto-detect and fetch**:

```
Agent Chat
├── JIRA tickets (detect COMPUTE-1234 patterns in messages)
├── Slack URLs (detect Slack links in messages)
├── File paths (detect ~/code/wx/... references)
├── Branch names (detect ao/TICKET-123-description patterns)
├── Worktrees (check if chat directory is worktree)
├── Uploaded files (parse for references)
├── Project context (infer from working directory)
├── Related artifacts (search by keywords/entities)
└── Recommended skills (NLP analysis of chat intent)
```

**Implementation**:
- Scan all chat messages for reference patterns
- Monitor cwd changes to detect project switches
- Parse uploaded files for JIRA keys, URLs, etc.
- Store chat → entity links

**Example**: Chat contains:
- "working on COMPUTE-1234" → Link JIRA, load context
- Working directory: `~/workspaces/wx-1/` → Load WX context
- "pods are crashlooping" → Suggest `wx-task-debug` skill
- Upload `kubectl describe pod` output → Parse pod name, link deployment

---

### 4. Starting from Uploaded Document

**Trigger**: User uploads doc (postmortem, investigation, RFD, log file)

**Auto-detect and fetch**:

```
Uploaded Document
├── JIRA tickets (scan for ticket keys)
├── Slack URLs (scan for Slack links)
├── PagerDuty incidents (scan for PD-* references)
├── GitLab MRs (scan for MR URLs)
├── Google Drive docs (scan for Drive links)
├── Timestamps (detect incident time ranges)
├── Project mentions (scan for WX/G4/Jobs/Temporal keywords)
├── Alert names (detect from alert firing messages)
├── Related artifacts (search by date/keywords)
└── Document type classification (postmortem/RFD/investigation/log)
```

**Implementation**:
- Content parsers for common formats (markdown, text, JSON, YAML)
- Entity extraction (NER for names, dates, systems)
- Classification model (or rule-based: "postmortem" → type)
- Store as `Artifact` with links

**Document Types**:
| Type | Detection | Auto-context |
|------|-----------|--------------|
| **Postmortem** | "postmortem", "incident", "root cause" | Load incident artifacts, alert definitions |
| **RFD** | "RFD-", "Request for Discussion" | Load related design docs, code repos |
| **Investigation** | Timestamps, system names, queries | Load project context, dashboards |
| **Logs** | kubectl, docker, systemd formats | Parse errors, suggest skills |
| **Config** | YAML/JSON with k8s/terraform schemas | Validate, link to repos |

---

### 5. Starting from Warning Channel (Proactive Monitoring)

**Trigger**: Real-time monitoring of `#compute-platform-warn` (or other warning channels)

**Auto-detect and classify**:

```
Warning Message
├── Alert name (jobs-scheduler-low-runs)
├── System/project (Jobs platform)
├── Severity (WARNING, not yet critical)
├── Escalation probability (pattern matching)
└── Time first seen
```

**If escalation-prone (>50% probability), pre-assemble context**:

```
Standby Context (before alert fires!)
├── Search artifacts (prior investigations of this alert)
├── Load alert definition (query, thresholds, runbook)
├── Load project context (jobs-claude.md)
├── Generate mitigation plan (from runbooks + past fixes)
├── Identify on-call contact (PagerDuty MCP)
├── Suggest skills (jobs-alert-triage)
└── Status: "standby" (ready to activate)
```

**If escalates to `#compute-platform` (critical alert)**:
- Detect escalation (same alert name)
- Activate standby context → Active incident
- Mitigation plan already ready!
- Time saved: 5-15 minutes

**Implementation**:
- Real-time Slack SSE monitoring (already implemented for WX deployments)
- Warning classification algorithm (pattern matching + historical data)
- Escalation probability prediction
- Standby context creation
- Escalation detection and activation

**Full Spec**: [PROACTIVE-INCIDENT-RESPONSE-SPEC.md](./PROACTIVE-INCIDENT-RESPONSE-SPEC.md)

**Value**:
- **50% reduction** in time-to-mitigation
- **Predictive context** instead of reactive scrambling
- **Learning system** improves over time
- **Unique to Compute team** (two-tier warn → alert pattern)

**Example Workflow**:

```
14:23 — #compute-platform-warn
  "jobs-scheduler-low-runs WARNING"

  Commander:
  ✓ Escalation probability: 75% (DB pattern)
  ✓ Searched artifacts → Found prior fix
  ✓ Generated plan: "Increase DB connection pool"
  ✓ Standby context ready in < 2 min

14:35 — #compute-platform (critical!)
  "[FIRING] jobs-scheduler-low-runs CRITICAL"

  Commander:
  ✅ Plan ready (pre-assembled 12 min ago)
  ✅ Known fix from 20260212-0936-investigation.md
  ✅ Mitigation: 3 steps, ETA 5 min

On-call: Immediate action instead of 10 min context gathering
```

---

## Cross-Reference Intelligence

### PagerDuty Integration

**Purpose**: Auto-link incidents to work contexts

**Detection Patterns**:
```regex
# PagerDuty URLs
https://planet-labs\.pagerduty\.com/incidents/([A-Z0-9]+)

# PagerDuty incident IDs in text
PD-[A-Z0-9]{6,}
incident #?[A-Z0-9]{6,}
```

**Auto-fetch**:
- Incident status, severity, timestamps
- Incident timeline (acks, escalations, resolves)
- Impacted services
- Related alerts (from Grafana)
- On-call responders
- Incident notes/postmortem links

**MCP Integration**:
- Already have PagerDuty MCP configured (`~/.cursor/mcp.json`)
- Functions: `list_oncalls`, `get_escalation_policy`, `list_incidents`

**Use Cases**:
1. JIRA ticket mentions "PD-ABC123" → Fetch incident, link timeline
2. Slack thread during incident → Auto-link PD incident
3. Agent chat: "check pagerduty" → Query active incidents
4. Postmortem upload → Extract PD incident ID, link context

**Database Schema**:
```sql
CREATE TABLE pagerduty_incidents (
    id UUID PRIMARY KEY,
    external_incident_id VARCHAR(50) UNIQUE NOT NULL,
    title TEXT,
    status VARCHAR(50),  -- triggered, acknowledged, resolved
    severity VARCHAR(10), -- SEV1, SEV2, etc.
    service_name VARCHAR(200),
    escalation_policy_id VARCHAR(50),
    triggered_at TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    incident_timeline JSONB,  -- Full timeline
    notes TEXT,
    postmortem_url TEXT,
    fetched_at TIMESTAMPTZ,
    last_updated_at TIMESTAMPTZ
);

CREATE INDEX idx_pd_incidents_external ON pagerduty_incidents(external_incident_id);
CREATE INDEX idx_pd_incidents_status ON pagerduty_incidents(status);
CREATE INDEX idx_pd_incidents_triggered ON pagerduty_incidents(triggered_at);
```

---

### Grafana Alert Definitions

**Purpose**: Link alerts to their definitions, history, and runbooks

**Source**: `~/code/build-deploy/planet-grafana-cloud-users/`

**Detection Patterns**:
```regex
# Alert names in firing messages
\[FIRING:\d+\] ([a-z0-9-]+)

# Grafana dashboard URLs
https://planet\.grafana\.net/d/([a-z0-9-]+)/

# Alert manager URLs
https://planet\.grafana\.net/alerting/
```

**Auto-fetch**:
- Alert definition (from repo)
- Alert query (PromQL/LogQL)
- Alert thresholds
- Runbook links
- Historical firings (via Grafana API)
- Related dashboards
- Owning team (from repo structure)

**Repo Structure**:
```
planet-grafana-cloud-users/
└── modules/
    ├── compute-team-jobs-alerts/
    │   ├── jobs-scheduler-low-runs.yaml
    │   ├── jobs-db-maint-workers.yaml
    │   └── ...
    ├── compute-team-wx-alerts/
    │   ├── wx-task-lease-expiration.yaml
    │   └── ...
    └── compute-team-g4-alerts/
        └── ...
```

**Parsing Strategy**:
1. Clone `planet-grafana-cloud-users` repo
2. Index all alert definitions by name
3. Parse YAML for query, thresholds, annotations
4. Extract runbook URLs from annotations
5. Link alerts to teams via directory structure

**Use Cases**:
1. Slack message: "[FIRING] jobs-scheduler-low-runs" → Link to alert definition
2. JIRA: "jobs-scheduler failing" → Link to alert, show query
3. Agent: "investigate jobs alert" → Load alert definition, suggest runbook
4. Postmortem: Extract alert names → Link definitions, show historical firings

**Database Schema**:
```sql
CREATE TABLE grafana_alert_definitions (
    id UUID PRIMARY KEY,
    alert_name VARCHAR(200) UNIQUE NOT NULL,
    team VARCHAR(100),  -- compute, datapipeline, etc.
    project VARCHAR(100),  -- jobs, wx, g4, etc.
    file_path TEXT,  -- Path in repo
    alert_query TEXT,  -- PromQL/LogQL
    thresholds JSONB,  -- { "warning": 10, "critical": 5 }
    annotations JSONB,  -- { "runbook": "url", "summary": "..." }
    labels JSONB,
    severity VARCHAR(10),
    last_synced_at TIMESTAMPTZ
);

CREATE TABLE grafana_alert_firings (
    id UUID PRIMARY KEY,
    alert_definition_id UUID REFERENCES grafana_alert_definitions(id),
    fired_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    labels JSONB,
    annotations JSONB,
    fingerprint VARCHAR(100)
);

CREATE INDEX idx_alert_defs_name ON grafana_alert_definitions(alert_name);
CREATE INDEX idx_alert_defs_team ON grafana_alert_definitions(team);
CREATE INDEX idx_alert_firings_def ON grafana_alert_firings(alert_definition_id);
CREATE INDEX idx_alert_firings_time ON grafana_alert_firings(fired_at);
```

---

### Google Drive Documents

**Purpose**: Link RFDs, postmortems, planning docs, meeting notes

**Source**: Google Drive for Desktop (`$GDRIVE_SHARED`)

**Key Locations**:
```
$COMPUTE_TEAM/           # Compute Team shared drive
├── RFCs Design Docs/    # RFDs, ADRs
├── Postmortems/         # Incident postmortems
├── WorkExchange/        # WX planning docs
├── Meeting Notes/       # Team meetings
├── On-Call/             # On-call logs, runbooks
└── ...

$POSTMORTEMS/            # Company-wide postmortems
└── Compute Team Postmortems/

$FUSION_TEAM/            # Fusion/TARDIS docs
$HOBBES_TEAM/            # Hobbes infrastructure docs
$PLANETARY_VARIABLES/    # PV project docs
```

**Detection Patterns**:
```regex
# Google Drive URLs
https://docs\.google\.com/(document|spreadsheets|presentation)/d/([a-zA-Z0-9_-]+)

# File paths (from Google Drive for Desktop)
/Users/aaryn/Library/CloudStorage/GoogleDrive-.*/Shared drives/.*

# Environment variables
\$COMPUTE_TEAM
\$POSTMORTEMS
\$FUSION_TEAM
etc.
```

**Auto-fetch**:
- Document title
- Document type (doc/sheet/slides)
- Last modified date
- Sharing permissions
- Document preview (first page/summary)
- Related documents (in same folder)

**Indexing Strategy**:
1. Scan Google Drive shared folders for relevant docs
2. Index by: project, type (postmortem/RFD/planning), date
3. Extract JIRA keys from doc content
4. Build keyword index for search

**Use Cases**:
1. JIRA mentions Google Doc → Fetch doc metadata, link
2. Incident response → Auto-link to prior postmortems
3. Planning ticket → Link to related RFDs
4. Upload doc → Detect it's from Drive, link canonical version

**Database Schema**:
```sql
CREATE TABLE google_drive_documents (
    id UUID PRIMARY KEY,
    external_doc_id VARCHAR(100) UNIQUE NOT NULL,
    doc_type VARCHAR(50),  -- document, spreadsheet, presentation
    title TEXT,
    url TEXT,
    file_path TEXT,  -- Local path via Drive for Desktop
    shared_drive VARCHAR(200),  -- Compute Team, Postmortems, etc.
    folder_path TEXT,
    project VARCHAR(100),  -- wx, g4, jobs, temporal, etc.
    document_kind VARCHAR(100),  -- postmortem, rfd, planning, meeting-notes
    last_modified_at TIMESTAMPTZ,
    owner VARCHAR(200),
    content_preview TEXT,  -- First page/summary
    keywords JSONB,  -- Extracted keywords
    jira_keys JSONB,  -- Extracted JIRA keys
    fetched_at TIMESTAMPTZ,
    last_indexed_at TIMESTAMPTZ
);

CREATE INDEX idx_gdrive_docs_external ON google_drive_documents(external_doc_id);
CREATE INDEX idx_gdrive_docs_project ON google_drive_documents(project);
CREATE INDEX idx_gdrive_docs_kind ON google_drive_documents(document_kind);
CREATE INDEX idx_gdrive_docs_modified ON google_drive_documents(last_modified_at);
```

---

### GitLab Merge Requests

**Purpose**: Link code changes to work contexts

**Detection Patterns**:
```regex
# GitLab MR URLs
https://hello\.planet\.com/code/([a-z0-9-]+/[a-z0-9-]+)/-/merge_requests/(\d+)

# MR references in text
MR !?(\d+)
!(\d+)  # GitLab shorthand
merge request #?(\d+)
```

**Auto-fetch** (via `glab` CLI):
- MR title, description
- Source/target branches
- Author, reviewers
- Approval status
- CI/CD pipeline status
- Comments, discussions
- Related commits
- Linked JIRA tickets (from title/description)

**Use Cases**:
1. JIRA ticket links MR → Fetch MR details, show status
2. Branch has open MR → Auto-link to work context
3. Slack discusses MR → Link MR, show CI status
4. Agent working on ticket → Check for existing MRs

**Database Schema**:
```sql
CREATE TABLE gitlab_merge_requests (
    id UUID PRIMARY KEY,
    external_mr_id INTEGER NOT NULL,  -- MR number
    repository VARCHAR(200) NOT NULL,  -- wx/wx, product/g4-wk/g4, etc.
    title TEXT,
    description TEXT,
    source_branch VARCHAR(200),
    target_branch VARCHAR(200),
    author VARCHAR(200),
    reviewers JSONB,
    approval_status VARCHAR(50),
    ci_status VARCHAR(50),
    state VARCHAR(50),  -- opened, merged, closed
    url TEXT,
    jira_keys JSONB,  -- Extracted from title/description
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    merged_at TIMESTAMPTZ,
    last_synced_at TIMESTAMPTZ,
    UNIQUE(repository, external_mr_id)
);

CREATE INDEX idx_gitlab_mr_repo ON gitlab_merge_requests(repository);
CREATE INDEX idx_gitlab_mr_state ON gitlab_merge_requests(state);
CREATE INDEX idx_gitlab_mr_branch ON gitlab_merge_requests(source_branch);
```

---

### Artifacts (Prior Investigations)

**Purpose**: Link to relevant prior investigations and analyses

**Source**: `~/claude/projects/{project}-notes/artifacts/`

**Filename Pattern**: `YYYYMMDD-HHMM-{description}.md`

**Indexing Strategy**:
1. Scan all artifact directories
2. Extract metadata:
   - Date/time (from filename)
   - Project (from directory)
   - JIRA keys (from filename + content)
   - Keywords (from description + content)
   - Type (investigation, plan, handoff, analysis)
3. Build searchable index

**Auto-link When**:
- Working on ticket → Search artifacts with same JIRA key
- Similar investigation → Search by keywords/entities
- Incident response → Search by date range + project
- Agent chat → Semantic search of artifact content

**Artifact Types** (inferred from filename/content):
| Pattern | Type | Example |
|---------|------|---------|
| `-investigation` | Investigation | `20260211-wx-task-debug-investigation.md` |
| `-analysis` | Analysis | `20260212-ppc-capacity-analysis.md` |
| `-plan` | Plan | `20260317-workspace-unification-plan.md` |
| `-handoff` | Handoff | `20251201-tardis-investigation-handoff.md` |
| `-complete` | Completion | `20260317-phase1-complete.md` |
| `-findings` | Findings | `20260105-security-audit-findings.md` |
| `-summary` | Summary | `20260203-slack-integration-summary.md` |

**Search Strategies**:
1. **Exact match**: JIRA key in filename
2. **Project match**: Same project + recent (last 90 days)
3. **Keyword match**: TF-IDF search on description + content
4. **Semantic search**: Embed artifacts, cosine similarity
5. **Date proximity**: Incidents near same date

**Database Schema**:
```sql
CREATE TABLE artifacts (
    id UUID PRIMARY KEY,
    file_path TEXT UNIQUE NOT NULL,
    filename VARCHAR(500),
    project VARCHAR(100),  -- wx, g4, jobs, temporal, etc.
    artifact_type VARCHAR(100),  -- investigation, plan, handoff, etc.
    title TEXT,  -- Extracted from first heading
    description TEXT,  -- From filename
    content TEXT,  -- Full markdown content
    jira_keys JSONB,  -- Extracted JIRA keys
    keywords JSONB,  -- Extracted keywords
    entities JSONB,  -- NER: systems, people, alerts
    created_at TIMESTAMPTZ,  -- From filename timestamp
    file_modified_at TIMESTAMPTZ,
    indexed_at TIMESTAMPTZ,
    embedding VECTOR(1536)  -- For semantic search
);

CREATE INDEX idx_artifacts_project ON artifacts(project);
CREATE INDEX idx_artifacts_type ON artifacts(artifact_type);
CREATE INDEX idx_artifacts_created ON artifacts(created_at);
CREATE INDEX idx_artifacts_jira_keys ON artifacts USING GIN(jira_keys);
CREATE INDEX idx_artifacts_keywords ON artifacts USING GIN(keywords);
-- Vector similarity index for semantic search
CREATE INDEX idx_artifacts_embedding ON artifacts USING ivfflat(embedding vector_cosine_ops);
```

---

### Project Claude Documentation

**Purpose**: Auto-load relevant project context

**Source**: `~/claude/projects/{project}-notes/{project}-claude.md`

**Auto-load When**:
- JIRA ticket → Load project from ticket key prefix (COMPUTE → multi-project)
- Working directory → Detect project from path
- Slack channel → Map channel to project
- Agent chat mentions project name

**Project Detection**:
| Trigger | Project | Claude Doc |
|---------|---------|------------|
| JIRA key starts with `COMPUTE-` | Infer from labels/components | Check ticket metadata |
| Working dir `~/code/wx/` | WX | `wx-notes/wx-claude.md` |
| Working dir `~/code/product/g4-wk/` | G4 | `g4-notes/g4-claude.md` |
| Working dir `~/code/jobs/` | Jobs | `jobs-notes/jobs-claude.md` |
| Working dir `~/workspaces/temporalio/` | Temporal | `temporal-notes/temporal-claude.md` |
| Slack channel `#wx-dev` | WX | `wx-notes/wx-claude.md` |
| Slack channel `#g4-users` | G4 | `g4-notes/g4-claude.md` |

**What to Load**:
- Main project claude.md file
- Project-specific grafana dashboards
- Project runbooks
- Key artifacts (recent investigations)
- Project-specific skills

**Implementation**:
- Store parsed project docs in database
- Index by project, keywords, headings
- Provide snippet extraction API
- Cache frequently accessed sections

---

### Skills Auto-Suggestion

**Purpose**: Recommend relevant skills based on context

**Source**: `~/.claude/skills/`

**Available Skills**:
| Skill | Trigger Conditions |
|-------|-------------------|
| `incident-response` | Severity mentioned, PagerDuty incident, alert firing |
| `wx-task-debug` | WX project + task failure keywords |
| `jobs-alert-triage` | Jobs alert names detected |
| `g4-incident-investigation` | G4 project + incident keywords |
| `datacollect-investigation` | G4 datacollect issues |
| `customer-impact-assessment` | Incident + customer mentions |
| `slack-catchup` | User asks to catch up |
| `temporal-onboard` | Temporal + onboarding keywords |
| `mr-review` | GitLab MR linked |
| `bigquery` | BigQuery mentioned, cost analysis |
| `cost-analysis` | Cost, billing, ROI keywords |

**Auto-suggest When**:
- **JIRA ticket labels** match skill domain (e.g., `incident` → `incident-response`)
- **Slack thread** contains skill trigger keywords
- **Agent chat** intent matches skill (NLP classification)
- **Uploaded doc** type suggests skill (e.g., alert log → `jobs-alert-triage`)

**Implementation**:
- Parse skill SKILL.md files for trigger conditions
- Build skill registry with keywords/patterns
- NLP classifier for chat intent → skill mapping
- Show suggested skills in context panel

---

### Calendar Integration

**Purpose**: Link on-call shifts, meetings, deployment windows

**Priority**: LOW (nice-to-have)

**Use Cases**:
1. Incident during on-call shift → Auto-link shift metadata
2. Meeting about ticket → Link calendar event
3. Deployment scheduled → Show in context timeline

**Implementation Complexity**: HIGH
- Requires Google Calendar API integration
- Privacy concerns (meeting content)
- Difficult to auto-link without explicit references

**Defer to later phases**

---

### Email Integration

**Purpose**: Link incident notification emails, team discussions

**Priority**: LOW (nice-to-have)

**Use Cases**:
1. PagerDuty sends email → Link to incident
2. JIRA sends email → Already have ticket
3. Postmortem shared via email → Link doc

**Implementation Complexity**: HIGH
- Requires Gmail API integration
- Privacy concerns
- Difficult to auto-link without explicit references
- Most content already captured in other systems

**Defer to later phases**

---

## Context Enrichment Workflow

### Phase 1: Detection (Immediate)

When entity is created or updated:
1. Scan content for reference patterns (regex)
2. Extract all detected references
3. Queue enrichment jobs for each reference
4. Mark entity as "enrichment pending"

### Phase 2: Fetching (Background)

For each detected reference:
1. Determine reference type (JIRA, Slack, PagerDuty, etc.)
2. Call appropriate fetcher service
3. Store fetched data in respective table
4. Create entity link
5. Update reference count

### Phase 3: Analysis (Advanced)

After basic enrichment:
1. Run pattern detection (incident, investigation, etc.)
2. Search for related artifacts
3. Load project context
4. Suggest skills
5. Generate context summary

### Phase 4: Presentation (UI)

Display enriched context:
1. Show all linked entities
2. Group by type (JIRA, Slack, PagerDuty, etc.)
3. Show health indicators
4. Display suggested actions
5. Provide quick links

---

## Implementation Priority

### Phase 1: Core Infrastructure (Weeks 1-2)

- [ ] Reference detection regex library
- [ ] Background job queue for enrichment
- [ ] Entity link service (already exists, extend)
- [ ] Context resolution service (already exists, extend)

### Phase 2: High-Value Integrations (Weeks 3-6)

- [ ] **PagerDuty incidents** (via MCP, already configured)
- [ ] **Grafana alert definitions** (parse repo)
- [ ] **Artifact indexing** (scan ~/claude/projects/)
- [ ] **Project context loading** (parse claude.md files)

### Phase 3: Medium-Value Integrations (Weeks 7-10)

- [ ] **Google Drive documents** (index shared drives)
- [ ] **GitLab MRs** (via glab CLI)
- [ ] **Slack threads** (already spec'd separately)
- [ ] **Skills auto-suggestion**

### Phase 4: Proactive Warning Monitoring (Weeks 11-16)

**See**: [PROACTIVE-INCIDENT-RESPONSE-SPEC.md](./PROACTIVE-INCIDENT-RESPONSE-SPEC.md)

- [ ] **Real-time Slack monitoring** (Week 11)
  - [ ] SSE integration for `#compute-platform-warn`
  - [ ] Warning message parsing
  - [ ] Database schema (warning_events table)
- [ ] **Escalation detection** (Week 12)
  - [ ] Pattern matching (high/medium/low risk)
  - [ ] Escalation probability prediction
  - [ ] Standby context creation
- [ ] **Mitigation plan generation** (Weeks 13-14)
  - [ ] Artifact search integration
  - [ ] Runbook parsing
  - [ ] Plan template generation
  - [ ] Plan UI
- [ ] **Learning system** (Weeks 15-16)
  - [ ] Escalation metrics collection
  - [ ] Model training
  - [ ] Feedback collection

**Value**: 50% reduction in time-to-mitigation, predictive incident response

### Phase 5: Polish & Advanced Features (Weeks 17-18)

- [ ] Semantic artifact search (embeddings)
- [ ] Context completeness scoring
- [ ] Suggested actions
- [ ] Timeline visualization
- [ ] Warning monitor dashboard

### Deferred to Future

- [ ] Multi-team warning monitoring expansion
- [ ] Calendar integration
- [ ] Email integration
- [ ] Automated mitigation execution (high risk)

---

## Database Schema Summary

### New Tables Required

1. `pagerduty_incidents` — PagerDuty incident cache
2. `grafana_alert_definitions` — Alert definitions from repo
3. `grafana_alert_firings` — Alert firing history
4. `google_drive_documents` — Google Drive doc index
5. `gitlab_merge_requests` — GitLab MR cache
6. `artifacts` — ~/claude artifact index
7. `project_contexts` — Parsed project claude.md files
8. `skill_registry` — Skill metadata and triggers
9. `warning_events` — Real-time warning monitoring (proactive response)
10. `warning_escalation_metrics` — Escalation prediction model data
11. `mitigation_plan_feedback` — Learning system feedback

### Extended Tables

- `entity_links` — Add more link types (alert, pagerduty, gdoc, etc.)
- `summaries` — Add source type for auto-generated summaries
- `work_contexts` — Add health scoring, suggested skills, standby state (origin_warning_ts, escalation_probability, escalated_at)

---

## API Endpoints

### Detection & Enrichment

```
POST /api/contexts/:id/enrich
  → Trigger enrichment for context

POST /api/entities/:type/:id/detect-references
  → Scan entity for cross-references

GET /api/entities/:type/:id/enrichment-status
  → Check enrichment progress
```

### Reference Fetchers

```
POST /api/pagerduty/fetch-incident/:incident_id
GET  /api/grafana/alert-definition/:alert_name
POST /api/gdrive/index-document
POST /api/gitlab/fetch-mr/:repo/:mr_number
POST /api/artifacts/search
  ?keywords=...&project=...&date_range=...
```

### Context Queries

```
GET /api/contexts/:id/timeline
  → Unified timeline of all linked entities

GET /api/contexts/:id/health
  → Context health score and issues

GET /api/contexts/:id/suggestions
  → Suggested skills, actions, links
```

---

## Success Metrics

### Enrichment Coverage

- **80%+ of JIRA tickets** have auto-detected cross-references
- **90%+ of Slack threads** are parsed and summarized
- **100% of PagerDuty incidents** are auto-linked when mentioned

### Context Completeness

- **Context health score > 0.8** for active work
- **< 5% orphaned entities** (not linked to any context)
- **90%+ of incidents** have linked postmortems/artifacts

### User Experience

- **< 5 seconds** to enrich a new ticket
- **< 2 clicks** to see full context for any entity
- **Suggested skills match user intent 80%+ of the time**

### Proactive Response (Warning Monitoring)

- **< 2 minutes** to pre-assemble standby context from warning
- **50% reduction** in time-to-mitigation (pre-assembled vs. reactive)
- **80%+ escalation prediction accuracy** (warnings flagged do escalate)
- **< 20% false positive rate** (standby contexts never activated)
- **80%+ on-call satisfaction** with pre-assembled mitigation plans

---

## Open Questions

1. **Rate limiting**: How to handle API quotas for PagerDuty, GitLab, Google Drive?
2. **Privacy**: What data can we cache vs. must fetch real-time?
3. **Stale data**: How often to re-fetch external entities?
4. **Cost**: Embeddings for semantic search — worth the compute cost?
5. **Permissions**: How to handle private Slack channels, restricted docs?

---

## References

- **Slack Context Parser**: [SLACK-CONTEXT-PARSER-SPEC.md](./SLACK-CONTEXT-PARSER-SPEC.md)
- **Proactive Incident Response**: [PROACTIVE-INCIDENT-RESPONSE-SPEC.md](./PROACTIVE-INCIDENT-RESPONSE-SPEC.md)
- **Planet Commander Spec**: [PLANET-COMMANDER-SPEC.md](./PLANET-COMMANDER-SPEC.md)
- **Investigation Methodology**: `~/claude/investigation-methodology.md`
- **Team Directory**: `~/claude/teams/teams.md`
- **On-Call Directory**: `~/claude/teams/oncall.md`
- **Skills Registry**: `~/.claude/skills/REGISTRY.md`
