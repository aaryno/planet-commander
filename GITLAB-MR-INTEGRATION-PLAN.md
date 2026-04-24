# GitLab Merge Requests — 6-Day Implementation Plan

**Created**: 2026-03-19
**Status**: Planning
**Priority**: MEDIUM
**Effort**: 6 days (1 week)

---

## Overview

Auto-index and link GitLab merge requests to enable:
- **Code context for JIRA tickets** — see MRs linked to tickets
- **Review status tracking** — approval status, CI/CD pipeline state
- **Cross-system linking** — MRs → JIRA, branches, work contexts
- **MR discovery** — find MRs by branch, project, author, or JIRA key

---

## Why GitLab MR Integration?

From AUTO-CONTEXT-ENRICHMENT-SPEC.md:

> **Priority**: MEDIUM | **Complexity**: Low | **Impact**: Medium — code review context

**Value Proposition**:
- **Code changes linked to work** — see what code changes are associated with tickets
- **Review workflow visibility** — track approval status, CI/CD pipeline
- **Cross-team collaboration** — discover related MRs across repos
- **glab CLI already available** — no API token management needed

**Use Cases**:
1. JIRA ticket links MR → Fetch MR details, show approval/CI status
2. Branch has open MR → Auto-link to work context
3. Slack discusses MR → Link MR, show CI status
4. Agent working on ticket → Check for existing MRs

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ GitLab (via glab CLI)                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Planet GitLab: hello.planet.com/code                           │
│  - wx/wx MRs                                                    │
│  - product/g4-wk/g4 MRs                                         │
│  - temporal/temporalio-cloud MRs                                │
│  - jobs/jobs MRs                                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Background Job: GitLab MR Scanner (30 minute interval)          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. For each tracked repository (wx, g4, jobs, temporal):       │
│     a. glab mr list --state=opened --limit=100                  │
│     b. Parse MR metadata (title, author, reviewers, CI)         │
│     c. Extract JIRA keys from title/description                 │
│     d. Check approval status                                    │
│     e. Upsert to gitlab_merge_requests table                    │
│  2. Mark stale MRs (merged/closed > 30 days ago)                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Background Job: MR Auto-Linking (30 minute interval)            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Link MRs to JIRA issues (by key in title/description)       │
│  2. Link MRs to git branches (by source_branch)                 │
│  3. Link MRs to work contexts (via JIRA links)                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Database (PostgreSQL)                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  gitlab_merge_requests                entity_links              │
│  - external_mr_id (MR number)         - from: jira_issue       │
│  - repository (wx/wx, g4, etc.)       - to: gitlab_mr          │
│  - title, description                 - link_type:             │
│  - source_branch, target_branch         implemented_by         │
│  - author, reviewers JSONB            - confidence: 0.95       │
│  - approval_status (approved/pending) - auto-detected from     │
│  - ci_status (passed/failed/running)    JIRA key in MR title  │
│  - state (opened/merged/closed)                                │
│  - url, jira_keys JSONB                                         │
│  - created_at, updated_at                                       │
│  - merged_at, closed_at                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6-Day Implementation Plan

### Day 1: Database Schema and Models

**Goal**: Create database tables and SQLAlchemy models

**Tasks**:
1. Create Alembic migration `20260320_1100_create_gitlab_mrs.py`
   - `gitlab_merge_requests` table
   - Extend `LinkType` enum with MR link types
   - Indexes on repository, state, source_branch, jira_keys

2. Create `backend/app/models/gitlab_merge_request.py`
   - SQLAlchemy model with all fields
   - Computed properties: `is_approved`, `is_ci_passing`, `is_stale`, `age_days`

3. Update `backend/app/models/__init__.py`
   - Export GitLabMergeRequest model

**Deliverable**: Database schema ready, models defined

---

### Day 2: Service Layer

**Goal**: Implement GitLab MR fetching and parsing via glab CLI

**Tasks**:
1. Create `backend/app/services/gitlab_mr_service.py`
   - `scan_repository_mrs()` — Use `glab mr list` to fetch open MRs
   - `fetch_mr_details()` — Use `glab mr view` for MR details
   - `parse_mr_output()` — Parse glab JSON output
   - `extract_jira_keys()` — Regex extraction from title/description
   - `update_mr()` — Upsert MR to database
   - `search_mrs()` — Query MRs by filters
   - `get_mr_by_number()` — Fetch single MR
   - `get_mrs_by_jira()` — Find MRs by JIRA key
   - `get_mrs_by_branch()` — Find MRs by branch name

2. Test with `glab` CLI
   - Verify glab configured (`~/.config/glab-cli/config.yml`)
   - Test MR listing for wx, g4, jobs repositories
   - Verify JSON parsing

**Deliverable**: Service layer can fetch and parse MRs from GitLab

---

### Day 3: API Endpoints

**Goal**: Create REST API for GitLab MRs

**Tasks**:
1. Create `backend/app/api/gitlab_mrs.py`
   - `GET /api/gitlab/mrs` — List MRs with filters
     - Query params: `repository`, `state`, `author`, `jira_key`, `limit`
   - `GET /api/gitlab/mrs/search` — Full-text search
     - Query params: `q`, `repository`, `state`, `limit`
   - `GET /api/gitlab/mrs/{repository}/{mr_number}` — Get single MR
   - `GET /api/gitlab/mrs/jira/{jira_key}` — Find MRs by JIRA key
   - `GET /api/gitlab/mrs/branch/{branch_name}` — Find MRs by branch
   - `POST /api/gitlab/mrs/scan` — Trigger manual scan

2. Update `backend/app/main.py`
   - Register gitlab_mrs router

3. Create Pydantic response models
   - `GitLabMRResponse` — Full MR with computed properties
   - `GitLabMRListResponse` — List wrapper with total count
   - `GitLabMRScanStatsResponse` — Scan statistics

**Deliverable**: REST API endpoints working

---

### Day 4: Frontend Components

**Goal**: Create React components for viewing GitLab MRs

**Tasks**:
1. Update `frontend/src/lib/api.ts`
   - Add API methods for GitLab MRs
   - Add TypeScript types (GitLabMR, GitLabMRListResponse, etc.)

2. Create `frontend/src/components/gitlab/GitLabMRCard.tsx`
   - Display MR title (clickable to GitLab)
   - Show approval status badge (approved/pending)
   - Show CI/CD status badge (passed/failed/running)
   - Display author, reviewers
   - Show source → target branch
   - Display JIRA keys (clickable badges)
   - Show age and state (opened/merged/closed)

3. Create `frontend/src/components/gitlab/GitLabMRsGrid.tsx`
   - ScrollableCard with search/filter bar
   - Filters: repository, state, author, JIRA key
   - Auto-refresh every 10 minutes
   - Menu: Refresh, Scan MRs
   - 2-column grid layout

4. Create `frontend/src/components/gitlab/JiraMRsSection.tsx`
   - Dedicated view for MRs linked to a JIRA ticket
   - Shows all MRs mentioning the JIRA key
   - Vertical list layout

**Deliverable**: Frontend components display GitLab MRs

---

### Day 5: Background Jobs and Auto-Linking

**Goal**: Implement periodic syncing and auto-linking

**Tasks**:
1. Create `backend/app/jobs/gitlab_mr_sync.py`
   - `sync_gitlab_mrs()` — Scan configured repositories
     - For each repo (wx/wx, g4, jobs, temporal):
       - Run `glab mr list --state=opened`
       - Parse MRs, extract JIRA keys
       - Upsert to database
     - Return stats: total_scanned, new_mrs, updated_mrs, unchanged_mrs, errors

   - `link_mrs_to_jira()` — Auto-link MRs to JIRA issues
     - For each MR with jira_keys:
       - Check if JIRA issue exists in cache
       - Create entity link: jira_issue → gitlab_mr
       - Link type: `implemented_by`
       - Confidence: 0.95 (high for title match)
     - Return stats: mrs_processed, links_created, links_skipped, errors

2. Update `backend/app/main.py`
   - Register gitlab MR sync job (30min interval)
   - Register MR → JIRA linking job (30min interval)
   - Add to startup logging

3. Configure repositories to track
   - Environment variable or config file: `GITLAB_TRACKED_REPOS`
   - Default: `wx/wx,product/g4-wk/g4,jobs/jobs,temporal/temporalio-cloud`

**Deliverable**: Background jobs sync MRs every 30 minutes

---

### Day 6: Testing and Documentation

**Goal**: Verify all components and document integration

**Tasks**:
1. Test database migrations
   - Run `make db-migrate`
   - Verify tables created with indexes

2. Test service layer
   - Write test script to fetch MRs via glab
   - Verify JIRA key extraction
   - Test MR upsert logic

3. Test API endpoints
   - List MRs for each repository
   - Search MRs by JIRA key
   - Fetch single MR details
   - Trigger manual scan

4. Test frontend components
   - Verify MRCard displays correctly
   - Test search/filter functionality
   - Verify auto-refresh works

5. Test background jobs
   - Run manual scan, verify stats
   - Run auto-linking, verify entity links created

6. Create `GITLAB-MR-INTEGRATION-COMPLETE.md`
   - Architecture overview
   - Database schema documentation
   - Service layer API reference
   - REST API endpoints with examples
   - Frontend component guide
   - Background jobs documentation
   - Testing results
   - Usage examples
   - Troubleshooting guide

**Deliverable**: Complete integration with documentation

---

## Database Schema

### gitlab_merge_requests Table

```sql
CREATE TABLE gitlab_merge_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- GitLab identity
    external_mr_id INTEGER NOT NULL,         -- MR number (e.g., 1234)
    repository VARCHAR(200) NOT NULL,        -- wx/wx, product/g4-wk/g4, etc.

    -- MR metadata
    title TEXT NOT NULL,
    description TEXT,
    url TEXT NOT NULL,

    -- Branches
    source_branch VARCHAR(200) NOT NULL,
    target_branch VARCHAR(200) NOT NULL,

    -- People
    author VARCHAR(200) NOT NULL,            -- email or username
    reviewers JSONB,                         -- Array of reviewer names

    -- Status
    approval_status VARCHAR(50),             -- approved, pending, changes_requested
    ci_status VARCHAR(50),                   -- passed, failed, running, skipped
    state VARCHAR(50) NOT NULL,              -- opened, merged, closed

    -- Extracted metadata
    jira_keys TEXT[],                        -- JIRA keys from title/description

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    merged_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(repository, external_mr_id)
);

-- Indexes
CREATE INDEX idx_gitlab_mr_repo ON gitlab_merge_requests(repository);
CREATE INDEX idx_gitlab_mr_state ON gitlab_merge_requests(state);
CREATE INDEX idx_gitlab_mr_source_branch ON gitlab_merge_requests(source_branch);
CREATE INDEX idx_gitlab_mr_author ON gitlab_merge_requests(author);
CREATE INDEX idx_gitlab_mr_jira_keys ON gitlab_merge_requests USING GIN (jira_keys);
CREATE INDEX idx_gitlab_mr_created ON gitlab_merge_requests(created_at);
```

### entity_links Extensions

```sql
-- New LinkType enum values
ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'implemented_by';      -- JIRA → MR
ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'implements';          -- MR → JIRA
ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'reviewed_in';         -- Branch → MR
ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'merged_to_branch';    -- MR → Branch
```

---

## glab CLI Integration

### glab Configuration

**Config location**: `~/.config/glab-cli/config.yml`

```yaml
hosts:
  hello.planet.com/code:
    token: glpat-...
    api_protocol: https
    git_protocol: ssh
```

**Verify configuration**:
```bash
glab auth status
glab repo view wx/wx
```

### glab Commands Used

#### List Open MRs
```bash
glab mr list \
  --repo wx/wx \
  --state opened \
  --per-page 100 \
  --output json
```

**Output**:
```json
[
  {
    "iid": 1234,
    "title": "feat(COMPUTE-5678): Add new feature",
    "state": "opened",
    "author": {"username": "aaryn"},
    "source_branch": "ao/COMPUTE-5678-new-feature",
    "target_branch": "main",
    "web_url": "https://hello.planet.com/code/wx/wx/-/merge_requests/1234",
    "created_at": "2026-03-19T10:00:00Z",
    "updated_at": "2026-03-19T15:00:00Z"
  }
]
```

#### Get MR Details
```bash
glab mr view 1234 \
  --repo wx/wx \
  --output json
```

**Output includes**:
- Full description
- Reviewers
- Approvals
- CI/CD pipeline status
- Comments count

#### Check CI Status
```bash
glab mr check 1234 --repo wx/wx
```

---

## Auto-Linking Strategy

### JIRA Key Extraction

**Pattern**: Extract JIRA keys from MR title and description

```python
JIRA_KEY_PATTERN = re.compile(
    r'\b(?:COMPUTE|PRODISSUE|WX|JOBS|G4|TEMPORAL|ESO)-\d+\b',
    re.IGNORECASE
)

# Example: "feat(COMPUTE-5678): Add new feature"
# Extracts: ["COMPUTE-5678"]
```

### Link Types

| From | To | Link Type | Confidence | Trigger |
|------|----|-----------|-----------| --------|
| JIRA Issue | GitLab MR | `implemented_by` | 0.95 | JIRA key in MR title |
| GitLab MR | JIRA Issue | `implements` | 0.95 | JIRA key in MR title |
| Git Branch | GitLab MR | `reviewed_in` | 1.0 | source_branch match |
| GitLab MR | Git Branch | `merged_to_branch` | 1.0 | target_branch match |

### Auto-Link Conditions

1. **JIRA → MR**: If MR title/description contains JIRA key
   - High confidence (0.95) — explicit reference
   - Link type: `implemented_by`

2. **Branch → MR**: If MR source_branch exists in git_branches table
   - Exact match (confidence: 1.0)
   - Link type: `reviewed_in`

3. **MR → Target Branch**: Always link to target branch
   - Usually "main" or "master"
   - Link type: `merged_to_branch`

---

## Frontend Design

### GitLabMRCard

**Layout**:
```
┌─────────────────────────────────────────────────────┐
│ [MR] feat(COMPUTE-5678): Add new feature           │ ← Title (clickable)
│      aaryn → main                                   │ ← Source → Target
│                                                     │
│ [✓ Approved] [✓ CI Passed] [COMPUTE-5678]         │ ← Status badges
│                                                     │
│ 📝 3 reviewers | 🕒 2d ago                         │ ← Metadata
│ ao/COMPUTE-5678-new-feature                        │ ← Source branch
└─────────────────────────────────────────────────────┘
```

**Status Badge Colors**:
- **Approval**: `approved` (green), `pending` (amber), `changes_requested` (red)
- **CI**: `passed` (green), `running` (blue), `failed` (red), `skipped` (gray)
- **State**: `opened` (blue), `merged` (green), `closed` (gray)

### GitLabMRsGrid

**Filters**:
- Repository: wx, g4, jobs, temporal, all
- State: opened, merged, closed, all
- Author: dropdown (from MRs)
- JIRA key: text input

**Search**: Full-text search across title and description

---

## Expected Results

### Initial Scan

After first `sync_gitlab_mrs()` run:

```python
{
  "total_scanned": 250,      # ~50 MRs per repo × 5 repos
  "new_mrs": 250,
  "updated_mrs": 0,
  "unchanged_mrs": 0,
  "errors": []
}
```

### Auto-Linking Results

After first `link_mrs_to_jira()` run:

```python
{
  "mrs_processed": 250,
  "links_created": ~200,     # ~80% of MRs have JIRA keys in title
  "links_skipped": ~50,      # No JIRA key or not in cache
  "errors": []
}
```

### Performance

- **Scan time**: ~30 seconds for 5 repositories
- **Link time**: ~5 seconds for 250 MRs
- **API response**: < 100ms for filtered queries
- **Frontend render**: < 200ms for 50 MRs

---

## Tracked Repositories

**Default tracked repos** (configurable):

| Repository | Project | Namespace |
|------------|---------|-----------|
| `wx/wx` | WX | wx |
| `product/g4-wk/g4` | G4 | product/g4-wk |
| `jobs/jobs` | Jobs | jobs |
| `temporal/temporalio-cloud` | Temporal | temporal |
| `eso/eso-golang` | ESO | eso |

**Configuration**:
```python
# backend/app/config.py or environment variable
GITLAB_TRACKED_REPOS = [
    "wx/wx",
    "product/g4-wk/g4",
    "jobs/jobs",
    "temporal/temporalio-cloud",
    "eso/eso-golang"
]
```

---

## Success Metrics

### Coverage
- **80%+ of open MRs** indexed within 30 minutes
- **90%+ JIRA → MR links** auto-created
- **100% of MRs** with JIRA keys linked

### Accuracy
- **95%+ JIRA key extraction accuracy**
- **< 5% false positives** (incorrect links)
- **Approval/CI status synced** within 30 minutes

### Performance
- **< 1 minute** to scan all repositories
- **< 50ms** API response for filtered queries
- **< 200ms** frontend render for 50 MRs

---

## Troubleshooting

### glab Not Configured

**Symptom**: `glab mr list` fails with "not authenticated"

**Solution**:
```bash
# Verify glab config
cat ~/.config/glab-cli/config.yml

# Re-authenticate if needed
glab auth login
```

### No MRs Found

**Symptom**: `total_scanned: 0`

**Causes**:
1. Repository path incorrect
2. No open MRs in repository
3. glab permission issues

**Solution**:
```bash
# Test manually
glab mr list --repo wx/wx --state opened

# Check repository access
glab repo view wx/wx
```

### JIRA Keys Not Extracted

**Symptom**: `jira_keys: []` for MRs with JIRA keys in title

**Cause**: Regex pattern issue

**Solution**: Verify regex with test:
```python
pattern = re.compile(r'\b(?:COMPUTE|PRODISSUE|WX|JOBS|G4|TEMPORAL|ESO)-\d+\b', re.IGNORECASE)
test_title = "feat(COMPUTE-5678): Add new feature"
matches = pattern.findall(test_title)
print(matches)  # Should output: ['COMPUTE-5678']
```

---

## Files to Create

### Backend
- `backend/alembic/versions/20260320_1100_create_gitlab_mrs.py` (NEW)
- `backend/app/models/gitlab_merge_request.py` (NEW)
- `backend/app/services/gitlab_mr_service.py` (NEW)
- `backend/app/api/gitlab_mrs.py` (NEW)
- `backend/app/jobs/gitlab_mr_sync.py` (NEW)
- `backend/app/main.py` (MODIFIED - router + jobs)
- `backend/app/models/__init__.py` (MODIFIED - exports)
- `backend/app/models/entity_link.py` (MODIFIED - link types enum)

### Frontend
- `frontend/src/lib/api.ts` (MODIFIED - API methods + types)
- `frontend/src/components/gitlab/GitLabMRCard.tsx` (NEW)
- `frontend/src/components/gitlab/GitLabMRsGrid.tsx` (NEW)
- `frontend/src/components/gitlab/JiraMRsSection.tsx` (NEW)

### Documentation
- `GITLAB-MR-INTEGRATION-COMPLETE.md` (NEW - Day 6)

---

## Summary

This integration completes the GitLab MR component of the AUTO-CONTEXT-ENRICHMENT-SPEC, enabling:

✅ **MR Discovery**: Find MRs by repository, branch, JIRA key, author
✅ **Auto-Linking**: Automatic linking to JIRA issues via entity graph
✅ **Status Tracking**: Approval status, CI/CD pipeline state
✅ **Code Context**: See code changes associated with work contexts
✅ **Cross-System Links**: MRs ↔ JIRA ↔ Branches ↔ Contexts

**Total LOC**: ~2,000 lines
**Integration Time**: 6 days
**MRs Indexed**: 200-300 open MRs across 5 repositories
**Auto-Links Created**: 150-200 JIRA → MR links

**Next Integration**: Skills Auto-Suggestion or Slack Threads (separate spec)
