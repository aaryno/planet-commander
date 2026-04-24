# Grafana Alert Definitions Integration - 7-Day Plan

**Created**: March 18, 2026
**Purpose**: Index Grafana alert definitions for intelligent alert context enrichment
**Pattern**: Following PagerDuty and Artifact indexing precedent
**Estimated Duration**: 7 days (Days 1-7)

---

## Overview

Parse and index alert definitions from `~/code/build-deploy/planet-grafana-cloud-users/` repository to enable:

1. **Alert name → definition lookup** when alerts fire in Slack
2. **Runbook linking** from alert annotations
3. **Historical firing tracking** (via Grafana API)
4. **Query/threshold visibility** for debugging
5. **Team/project ownership** via directory structure
6. **Auto-linking** to JIRA issues and work contexts

**Value Proposition**: When an alert fires in `#compute-platform`, Commander instantly shows:
- Alert definition (PromQL/LogQL query)
- Thresholds (warning/critical)
- Runbook URL
- Prior investigations (artifacts with this alert name)
- Owning team
- Recent firing history

---

## Repository Structure

```
~/code/build-deploy/planet-grafana-cloud-users/
└── modules/
    ├── compute-team-jobs-alerts/
    │   ├── jobs-scheduler-low-runs.yaml
    │   ├── jobs-db-maint-workers.yaml
    │   └── ...
    ├── compute-team-wx-alerts/
    │   ├── wx-task-lease-expiration.yaml
    │   ├── wx-redis-memory-high.yaml
    │   └── ...
    ├── compute-team-g4-alerts/
    │   ├── g4-api-availability.yaml
    │   └── ...
    └── compute-team-temporal-alerts/
        └── ...
```

**Alert Definition Format** (YAML):
```yaml
# jobs-scheduler-low-runs.yaml
alert: jobs-scheduler-low-runs
expr: |
  rate(jobs_scheduler_runs_total[5m]) < 10
for: 5m
labels:
  severity: warning
  team: compute
  project: jobs
annotations:
  summary: "Jobs scheduler is running fewer than 10 tasks per 5min"
  runbook_url: "https://wiki.planet.com/jobs/runbook/scheduler-low-runs"
  description: "Current rate: {{ $value }} runs/5m"
```

---

## Database Schema

### Table: `grafana_alert_definitions`

**Purpose**: Store parsed alert definitions from repo

```sql
CREATE TABLE grafana_alert_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Alert identity
    alert_name VARCHAR(200) UNIQUE NOT NULL,
    file_path TEXT NOT NULL,  -- Path in repo

    -- Ownership
    team VARCHAR(100),  -- compute, datapipeline, hobbes
    project VARCHAR(100),  -- jobs, wx, g4, temporal

    -- Alert configuration
    alert_expr TEXT NOT NULL,  -- PromQL/LogQL query
    alert_for VARCHAR(50),  -- Duration (5m, 10m, etc.)

    -- Metadata
    labels JSONB,  -- { "severity": "warning", "team": "compute" }
    annotations JSONB,  -- { "summary": "...", "runbook_url": "..." }

    -- Parsed fields (for quick access)
    severity VARCHAR(10),  -- warning, critical
    runbook_url TEXT,
    summary TEXT,

    -- Sync metadata
    file_modified_at TIMESTAMPTZ,
    last_synced_at TIMESTAMPTZ DEFAULT now(),

    -- Soft delete
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_alert_defs_name ON grafana_alert_definitions(alert_name);
CREATE INDEX idx_alert_defs_team ON grafana_alert_definitions(team);
CREATE INDEX idx_alert_defs_project ON grafana_alert_definitions(project);
CREATE INDEX idx_alert_defs_severity ON grafana_alert_definitions(severity);
CREATE INDEX idx_alert_defs_labels ON grafana_alert_definitions USING GIN(labels);
```

### Table: `grafana_alert_firings`

**Purpose**: Track historical alert firings (fetched via Grafana API)

```sql
CREATE TABLE grafana_alert_firings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to definition
    alert_definition_id UUID REFERENCES grafana_alert_definitions(id),
    alert_name VARCHAR(200) NOT NULL,

    -- Firing details
    fired_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ,
    state VARCHAR(50),  -- firing, resolved, pending

    -- Instance metadata
    labels JSONB,  -- Instance-specific labels
    annotations JSONB,  -- Instance-specific annotations
    fingerprint VARCHAR(100),  -- Grafana alert fingerprint

    -- Alert value
    value FLOAT,  -- Alert metric value at fire time

    -- External reference
    external_alert_id VARCHAR(100),  -- Grafana alert instance ID

    -- Metadata
    fetched_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_alert_firings_def ON grafana_alert_firings(alert_definition_id);
CREATE INDEX idx_alert_firings_name ON grafana_alert_firings(alert_name);
CREATE INDEX idx_alert_firings_fired ON grafana_alert_firings(fired_at DESC);
CREATE INDEX idx_alert_firings_state ON grafana_alert_firings(state);
CREATE INDEX idx_alert_firings_fingerprint ON grafana_alert_firings(fingerprint);
```

### Entity Link Extension

**Add to `LinkType` enum**:
```python
class LinkType(str, enum.Enum):
    # ... existing types
    TRIGGERED_ALERT = "triggered_alert"
    DISCUSSED_ALERT = "discussed_alert"
    REFERENCES_ALERT = "references_alert"
```

---

## 7-Day Implementation Plan

### Day 1: Database Schema & Models (Tuesday)

**Goal**: Create database schema and SQLAlchemy models

**Tasks**:
- [ ] Create Alembic migration: `20260319_0900_create_alert_definitions.py`
- [ ] Define `grafana_alert_definitions` table (9 columns, 5 indexes)
- [ ] Define `grafana_alert_firings` table (11 columns, 5 indexes)
- [ ] Create SQLAlchemy model: `backend/app/models/grafana_alert_definition.py`
- [ ] Create SQLAlchemy model: `backend/app/models/grafana_alert_firing.py`
- [ ] Extend `LinkType` enum in `entity_link.py`
- [ ] Run migration, verify schema

**Migration Code**:
```python
# backend/alembic/versions/20260319_0900_create_alert_definitions.py
def upgrade() -> None:
    # Create alert definitions table
    op.create_table(
        'grafana_alert_definitions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=func.gen_random_uuid()),
        sa.Column('alert_name', sa.String(200), unique=True, nullable=False),
        # ... (16 total columns)
    )

    # Create alert firings table
    op.create_table(
        'grafana_alert_firings',
        # ...
    )

    # Add alert link types to enum
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'triggered_alert'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'discussed_alert'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'references_alert'")
```

**Success Criteria**:
- Migration applies cleanly
- Tables created with all columns/indexes
- Models import correctly

**Estimated Time**: 2-3 hours

---

### Day 2: Alert Definition Parser (Wednesday)

**Goal**: Parse YAML alert definitions from repo

**Tasks**:
- [ ] Create `backend/app/services/grafana_alert_service.py`
- [ ] Implement YAML parsing for alert definitions
- [ ] Extract team/project from directory structure
- [ ] Parse labels and annotations
- [ ] Extract runbook URL, severity, summary
- [ ] Handle malformed YAML gracefully
- [ ] Write unit tests for parsing

**Service Structure**:
```python
# backend/app/services/grafana_alert_service.py
import yaml
from pathlib import Path
from typing import Dict, Optional

class GrafanaAlertService:
    """Service for parsing and indexing Grafana alert definitions."""

    REPO_PATH = Path("~/code/build-deploy/planet-grafana-cloud-users").expanduser()
    MODULES_PATH = REPO_PATH / "modules"

    def parse_alert_yaml(self, file_path: Path) -> Optional[Dict]:
        """Parse alert definition from YAML file.

        Returns:
            Dict with alert_name, expr, labels, annotations, etc.
        """
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)

        # Extract team/project from directory structure
        # modules/compute-team-jobs-alerts/... → team=compute, project=jobs
        parts = file_path.parent.name.split('-')
        team = parts[0] if len(parts) > 0 else None
        project = parts[-2] if len(parts) > 2 else None

        return {
            "alert_name": data.get("alert"),
            "alert_expr": data.get("expr"),
            "alert_for": data.get("for"),
            "labels": data.get("labels", {}),
            "annotations": data.get("annotations", {}),
            "team": team,
            "project": project,
            "severity": data.get("labels", {}).get("severity"),
            "runbook_url": data.get("annotations", {}).get("runbook_url"),
            "summary": data.get("annotations", {}).get("summary"),
        }

    async def scan_alert_repo(self) -> Dict[str, int]:
        """Scan alert repo and index all definitions.

        Returns:
            Stats dict with counts
        """
        stats = {
            "total_scanned": 0,
            "new_alerts": 0,
            "updated_alerts": 0,
            "errors": []
        }

        # Scan all YAML files in modules/
        for yaml_file in self.MODULES_PATH.glob("**/*.yaml"):
            try:
                alert_data = self.parse_alert_yaml(yaml_file)
                result = await self._index_alert(yaml_file, alert_data)
                stats["total_scanned"] += 1
                if result == "new":
                    stats["new_alerts"] += 1
                elif result == "updated":
                    stats["updated_alerts"] += 1
            except Exception as e:
                stats["errors"].append({"file": str(yaml_file), "error": str(e)})

        return stats
```

**Success Criteria**:
- Correctly parse 50+ alert definitions
- Extract team/project from directory structure
- Handle all annotation/label variations
- Gracefully skip non-alert YAML files

**Estimated Time**: 3-4 hours

---

### Day 3: Repository Scanning & Indexing (Thursday)

**Goal**: Scan repo and populate database

**Tasks**:
- [ ] Implement incremental scanning (file mtime tracking)
- [ ] Database CRUD operations (create/update alerts)
- [ ] Handle alert deletions (soft delete)
- [ ] Scan entire repo, verify indexing
- [ ] Test alert lookup by name

**Incremental Scanning**:
```python
async def _index_alert(self, file_path: Path, alert_data: Dict) -> str:
    """Index single alert definition.

    Returns:
        "new", "updated", or "skipped"
    """
    # Check if already indexed
    existing = await self.get_alert_by_name(alert_data["alert_name"])

    # Check file mtime
    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)

    if existing and existing.file_modified_at >= file_mtime:
        return "skipped"  # Up-to-date

    if existing:
        # Update existing
        existing.alert_expr = alert_data["alert_expr"]
        existing.labels = alert_data["labels"]
        # ... update all fields
        existing.file_modified_at = file_mtime
        existing.last_synced_at = datetime.now(timezone.utc)
        await self.db.commit()
        return "updated"
    else:
        # Create new
        alert = GrafanaAlertDefinition(
            alert_name=alert_data["alert_name"],
            file_path=str(file_path),
            # ... all fields
        )
        self.db.add(alert)
        await self.db.commit()
        return "new"
```

**Success Criteria**:
- Scan completes in <5 seconds for 100+ alerts
- Incremental scanning works (skips unchanged files)
- Database populated with all alerts
- Can query alert by name

**Estimated Time**: 3-4 hours

---

### Day 4: API Endpoints (Friday)

**Goal**: REST API for alert queries

**Tasks**:
- [ ] Create `backend/app/api/grafana_alerts.py`
- [ ] Implement 6 async endpoints
- [ ] Add Pydantic response models
- [ ] Test all endpoints with curl

**API Endpoints**:
```python
# backend/app/api/grafana_alerts.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database import get_db
from app.services.grafana_alert_service import GrafanaAlertService

router = APIRouter(prefix="/api/grafana/alerts", tags=["grafana-alerts"])

@router.get("", response_model=List[AlertDefinitionResponse])
async def list_alerts(
    team: Optional[str] = None,
    project: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List alert definitions with filters."""

@router.get("/{alert_name}", response_model=AlertDefinitionResponse)
async def get_alert_definition(
    alert_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Get single alert definition by name."""

@router.get("/search", response_model=List[AlertDefinitionResponse])
async def search_alerts(
    query: str,
    team: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search alerts by name or summary."""

@router.get("/{alert_name}/firings", response_model=List[AlertFiringResponse])
async def get_alert_firings(
    alert_name: str,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get recent firings for alert."""

@router.post("/scan", response_model=ScanResponse)
async def scan_alert_repo(
    db: AsyncSession = Depends(get_db),
):
    """Trigger alert repo scan."""

@router.post("/{alert_name}/fetch-history", response_model=FetchHistoryResponse)
async def fetch_alert_history(
    alert_name: str,
    days: int = Query(7, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Fetch firing history from Grafana API."""
```

**Pydantic Models**:
```python
class AlertDefinitionResponse(BaseModel):
    id: str
    alert_name: str
    alert_expr: str
    alert_for: Optional[str]
    team: Optional[str]
    project: Optional[str]
    severity: Optional[str]
    runbook_url: Optional[str]
    summary: Optional[str]
    labels: dict
    annotations: dict
    last_synced_at: datetime

    class Config:
        from_attributes = True
```

**Success Criteria**:
- All 6 endpoints functional
- Can list/search/get alerts
- Firing history endpoint ready (will fetch from Grafana later)
- Scan endpoint triggers repo sync

**Estimated Time**: 3-4 hours

---

### Day 5: Frontend Components (Monday)

**Goal**: UI components for alert display

**Tasks**:
- [ ] Create `frontend/src/lib/api.ts` types and methods
- [ ] Create `AlertDefinitionCard` component
- [ ] Create `AlertFiringTimeline` component
- [ ] Create `AlertSection` component (with search/filters)
- [ ] Test TypeScript compilation

**TypeScript Interface**:
```typescript
// frontend/src/lib/api.ts
export interface GrafanaAlertDefinition {
  id: string;
  alert_name: string;
  alert_expr: string;
  alert_for: string | null;
  team: string | null;
  project: string | null;
  severity: string | null;
  runbook_url: string | null;
  summary: string | null;
  labels: Record<string, string>;
  annotations: Record<string, string>;
  last_synced_at: string;
}

export interface AlertFiring {
  id: string;
  alert_name: string;
  fired_at: string;
  resolved_at: string | null;
  state: string;
  value: number | null;
  labels: Record<string, string>;
}

// API methods
export const api = {
  // ... existing methods

  // Grafana alerts
  alertDefinitions: (team?, project?, severity?, limit = 100) =>
    fetchApi<GrafanaAlertDefinition[]>(`/grafana/alerts?${params}`),

  alertDefinition: (alertName: string) =>
    fetchApi<GrafanaAlertDefinition>(`/grafana/alerts/${alertName}`),

  searchAlerts: (query: string, team?, project?, limit = 20) =>
    fetchApi<GrafanaAlertDefinition[]>(`/grafana/alerts/search?${params}`),

  alertFirings: (alertName: string, limit = 20) =>
    fetchApi<AlertFiring[]>(`/grafana/alerts/${alertName}/firings?limit=${limit}`),

  scanAlerts: () =>
    fetchApi<{total_scanned: number, new_alerts: number}>("/grafana/alerts/scan", { method: "POST" }),
};
```

**AlertDefinitionCard Component**:
```tsx
// frontend/src/components/grafana/AlertDefinitionCard.tsx
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExternalLink, AlertTriangle, BookOpen } from "lucide-react";
import type { GrafanaAlertDefinition } from "@/lib/api";

interface AlertDefinitionCardProps {
  alert: GrafanaAlertDefinition;
  showQuery?: boolean;
}

export function AlertDefinitionCard({ alert, showQuery = false }: AlertDefinitionCardProps) {
  const severityColor = {
    critical: "bg-red-500/20 text-red-400",
    warning: "bg-amber-500/20 text-amber-400",
    info: "bg-blue-500/20 text-blue-400",
  }[alert.severity || ""] || "bg-zinc-500/20 text-zinc-400";

  return (
    <div className="p-3 rounded border border-zinc-800 hover:border-zinc-700 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <AlertTriangle className="w-4 h-4 text-zinc-500 flex-shrink-0" />
          <h4 className="text-sm font-medium text-zinc-200 truncate">
            {alert.alert_name}
          </h4>
        </div>
        {alert.runbook_url && (
          <a
            href={alert.runbook_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-zinc-500 hover:text-zinc-400 flex-shrink-0"
            title="Open runbook"
          >
            <BookOpen className="w-4 h-4" />
          </a>
        )}
      </div>

      {/* Summary */}
      {alert.summary && (
        <p className="text-xs text-zinc-400 mt-1">{alert.summary}</p>
      )}

      {/* Badges */}
      <div className="flex items-center gap-2 mt-2 flex-wrap">
        {alert.severity && (
          <Badge className={severityColor}>{alert.severity}</Badge>
        )}
        {alert.team && (
          <Badge variant="outline" className="text-xs">{alert.team}</Badge>
        )}
        {alert.project && (
          <Badge variant="outline" className="text-xs">{alert.project}</Badge>
        )}
        {alert.alert_for && (
          <span className="text-xs text-zinc-500">for {alert.alert_for}</span>
        )}
      </div>

      {/* Query (expandable) */}
      {showQuery && alert.alert_expr && (
        <div className="mt-2">
          <pre className="text-xs bg-zinc-900 p-2 rounded overflow-x-auto">
            <code className="text-zinc-300">{alert.alert_expr}</code>
          </pre>
        </div>
      )}
    </div>
  );
}
```

**AlertSection Component**:
```tsx
// frontend/src/components/grafana/AlertSection.tsx
import { useState, useCallback, useMemo } from "react";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { AlertDefinitionCard } from "./AlertDefinitionCard";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { AlertTriangle, Search, RefreshCw } from "lucide-react";

interface AlertSectionProps {
  team?: string;
  project?: string;
  title?: string;
}

export function AlertSection({ team, project, title = "Alert Definitions" }: AlertSectionProps) {
  const [searchQuery, setSearchQuery] = useState("");

  const fetcher = useCallback(() => {
    if (searchQuery) {
      return api.searchAlerts(searchQuery, team, project, 50);
    }
    return api.alertDefinitions(team, project, undefined, 100);
  }, [searchQuery, team, project]);

  const { data: alerts, loading, error, refresh } = usePoll(fetcher, 600_000); // 10 min

  const stickyHeader = (
    <div className="space-y-2">
      <div className="relative">
        <Search className="absolute left-2 top-2 h-4 w-4 text-zinc-500" />
        <Input
          placeholder="Search alerts..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-8"
        />
      </div>
      <div className="text-xs text-zinc-500">
        {alerts?.length || 0} alert{alerts?.length !== 1 ? "s" : ""}
      </div>
    </div>
  );

  const menuItems = [
    {
      label: "Refresh",
      onClick: refresh,
      icon: <RefreshCw className="w-3 h-3" />,
    },
  ];

  return (
    <ScrollableCard
      title={title}
      icon={<AlertTriangle className="w-5 h-5" />}
      menuItems={menuItems}
      stickyHeader={stickyHeader}
    >
      {loading && <p className="text-xs text-zinc-500">Loading alerts...</p>}
      {error && <p className="text-xs text-red-400">Error loading alerts</p>}
      {alerts && alerts.length === 0 && (
        <p className="text-xs text-zinc-500">No alerts found</p>
      )}
      {alerts && alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((alert) => (
            <AlertDefinitionCard key={alert.id} alert={alert} />
          ))}
        </div>
      )}
    </ScrollableCard>
  );
}
```

**Success Criteria**:
- TypeScript compiles without errors
- Next.js builds successfully
- Components render correctly
- Alert cards display all metadata

**Estimated Time**: 3-4 hours

---

### Day 6: Background Jobs & Auto-Linking (Tuesday)

**Goal**: Background sync and entity linking

**Tasks**:
- [ ] Create `backend/app/jobs/grafana_sync.py`
- [ ] Implement alert repo sync job (1 hour interval)
- [ ] Implement auto-linking to JIRA issues (scan for alert names)
- [ ] Register jobs in `main.py`
- [ ] Test end-to-end sync flow

**Background Jobs**:
```python
# backend/app/jobs/grafana_sync.py
import logging
from sqlalchemy import select
from app.database import async_session
from app.services.grafana_alert_service import GrafanaAlertService
from app.models.jira_issue import JiraIssue
from app.models.entity_link import EntityLink, LinkType, LinkSourceType, LinkStatus

logger = logging.getLogger(__name__)

async def sync_alert_definitions():
    """Scan alert repo and sync definitions to database.

    Runs every 1 hour to pick up new/modified alerts.
    """
    async with async_session() as db:
        service = GrafanaAlertService(db)

        logger.info("Starting Grafana alert definition sync")
        stats = await service.scan_alert_repo()

        logger.info(
            f"Alert sync complete: {stats['total_scanned']} scanned, "
            f"{stats['new_alerts']} new, {stats['updated_alerts']} updated"
        )

        if stats['errors']:
            logger.warning(f"{len(stats['errors'])} errors during scan")

        return stats

async def link_alerts_to_jira():
    """Auto-link alert definitions to JIRA issues mentioning alert names.

    Searches JIRA issue descriptions/comments for alert names.
    """
    async with async_session() as db:
        logger.info("Starting alert → JIRA auto-linking")

        # Get all JIRA issues
        result = await db.execute(select(JiraIssue))
        issues = result.scalars().all()

        links_created = 0

        for issue in issues:
            # Search for alert names in title/description
            content = f"{issue.title or ''} {issue.description or ''}"

            # Find alert names (lowercase-with-dashes pattern)
            alert_name_pattern = r'\b([a-z0-9]+-){2,}[a-z0-9]+\b'
            potential_alerts = re.findall(alert_name_pattern, content)

            for alert_name in potential_alerts:
                # Check if alert definition exists
                alert_result = await db.execute(
                    select(GrafanaAlertDefinition).where(
                        GrafanaAlertDefinition.alert_name == alert_name
                    )
                )
                alert_def = alert_result.scalar_one_or_none()

                if not alert_def:
                    continue

                # Check if link exists
                link_result = await db.execute(
                    select(EntityLink).where(
                        EntityLink.from_type == "jira_issue",
                        EntityLink.from_id == str(issue.id),
                        EntityLink.to_type == "alert",
                        EntityLink.to_id == str(alert_def.id)
                    )
                )
                existing = link_result.scalar_one_or_none()

                if existing:
                    continue

                # Create link
                link = EntityLink(
                    from_type="jira_issue",
                    from_id=str(issue.id),
                    to_type="alert",
                    to_id=str(alert_def.id),
                    link_type=LinkType.DISCUSSED_ALERT,
                    source_type=LinkSourceType.INFERRED,
                    confidence_score=0.85,
                    status=LinkStatus.CONFIRMED
                )
                db.add(link)
                links_created += 1

        await db.commit()
        logger.info(f"Alert auto-linking complete: {links_created} links created")

        return {"links_created": links_created}
```

**Job Registration** (main.py):
```python
from app.jobs.grafana_sync import sync_alert_definitions, link_alerts_to_jira

# Alert sync: every 1 hour
job_service.add_interval_job(
    sync_alert_definitions,
    job_id="grafana_alert_sync",
    hours=1
)

# Alert → JIRA linking: every 1 hour
job_service.add_interval_job(
    link_alerts_to_jira,
    job_id="alert_jira_linking",
    hours=1
)
```

**Success Criteria**:
- Background jobs run successfully
- Alerts synced from repo
- Auto-links created to JIRA issues
- No duplicate links

**Estimated Time**: 3-4 hours

---

### Day 7: Testing & Documentation (Wednesday)

**Goal**: End-to-end testing, documentation, polish

**Tasks**:
- [ ] Create completion documentation
- [ ] Test full workflow:
  - [ ] Scan alerts → Database populated
  - [ ] API endpoints → Search works
  - [ ] Frontend → Cards display correctly
  - [ ] Auto-linking → JIRA issues linked
- [ ] Verify performance (100+ alerts)
- [ ] Update PROGRESS.md
- [ ] Clean up any test files

**Testing Checklist**:

1. **Backend API**:
   ```bash
   curl -X POST http://localhost:9000/api/grafana/alerts/scan
   curl "http://localhost:9000/api/grafana/alerts?team=compute&limit=5"
   curl "http://localhost:9000/api/grafana/alerts/jobs-scheduler-low-runs"
   curl "http://localhost:9000/api/grafana/alerts/search?query=scheduler"
   ```

2. **Database Verification**:
   ```sql
   SELECT COUNT(*) FROM grafana_alert_definitions;
   SELECT alert_name, team, project, severity FROM grafana_alert_definitions LIMIT 10;
   SELECT COUNT(*) FROM entity_links WHERE link_type = 'discussed_alert';
   ```

3. **Frontend Components**:
   - Visit http://localhost:3000
   - Add `<AlertSection team="compute" />` to test page
   - Verify alerts display with badges
   - Test search functionality
   - Test runbook links

**Documentation**:
- Create `20260319-1700-grafana-alerts-complete.md`
- Summary of implementation
- Files modified/created
- Testing results
- Usage examples

**Success Criteria**:
- 100+ alerts indexed
- All API endpoints functional
- Frontend components working
- Documentation complete

**Estimated Time**: 2-3 hours

---

## Success Metrics

### Coverage
- **100+ alert definitions** indexed from repo
- **90%+ team/project** ownership detected from directory structure
- **All Compute team alerts** (jobs, wx, g4, temporal) indexed

### Performance
- **< 5 seconds** to scan entire alert repo
- **< 50ms** to query alert by name
- **< 100ms** to search alerts

### Integration
- **Auto-linking** to JIRA issues mentioning alert names
- **Entity links** created between alerts and issues
- **Ready for Slack integration** (alert name → definition lookup)

---

## Future Enhancements

### Phase 2: Historical Firing Data
- Integrate with Grafana API to fetch firing history
- Store in `grafana_alert_firings` table
- Show timeline of recent firings
- Correlate firings with JIRA issues/incidents

### Phase 3: Slack Integration
- Parse `[FIRING]` messages in `#compute-platform`
- Auto-link to alert definition
- Show runbook in Slack thread
- Pre-fetch relevant artifacts

### Phase 4: Alert Health Monitoring
- Track firing frequency
- Detect flapping alerts
- Identify noisy/ineffective alerts
- Suggest threshold adjustments

---

## Files to Create/Modify

### Backend (8 files)
- ✅ `backend/alembic/versions/20260319_0900_create_alert_definitions.py`
- ✅ `backend/app/models/grafana_alert_definition.py`
- ✅ `backend/app/models/grafana_alert_firing.py`
- ✅ `backend/app/models/entity_link.py` (extend LinkType)
- ✅ `backend/app/services/grafana_alert_service.py`
- ✅ `backend/app/api/grafana_alerts.py`
- ✅ `backend/app/jobs/grafana_sync.py`
- ✅ `backend/app/main.py` (register jobs)

### Frontend (3 files)
- ✅ `frontend/src/lib/api.ts` (types + methods)
- ✅ `frontend/src/components/grafana/AlertDefinitionCard.tsx`
- ✅ `frontend/src/components/grafana/AlertSection.tsx`
- 🔮 `frontend/src/components/grafana/AlertFiringTimeline.tsx` (Phase 2 - Grafana API integration)

**Total**: ~11 files, ~1,150 lines of code

---

## Status

**✅ COMPLETE** - All Days 1-7 finished (March 19, 2026)

See [GRAFANA-ALERTS-INTEGRATION-COMPLETE.md](./GRAFANA-ALERTS-INTEGRATION-COMPLETE.md) for full implementation details, testing results, and usage examples.

---

## Comparison to Previous Integrations

| Feature | PagerDuty | Artifacts | Grafana Alerts |
|---------|-----------|-----------|----------------|
| Database tables | 1 | 1 | 2 |
| Service layer | ✅ | ✅ | ✅ |
| API endpoints | 6 | 7 | 6 |
| Frontend components | 1 card | 2 cards | 3 cards |
| Background jobs | 1 (30min) | 2 (1h each) | 2 (1h each) |
| Entity linking | ✅ | ✅ | ✅ |
| Search/filter | ✅ | ✅ | ✅ |

**Pattern Consistency**: 100% — Following exact same structure

---

## Next Integration After This

After Grafana Alerts, the next high-value integration from AUTO-CONTEXT-ENRICHMENT-SPEC is:

**Project Context Loading** — Parse and index `~/claude/projects/{project}-notes/{project}-claude.md` files for auto-loading project context when tickets/chats reference projects.

---

## Notes

- Alert repo location: `~/code/build-deploy/planet-grafana-cloud-users/`
- Directory structure encodes ownership: `compute-team-{project}-alerts/`
- YAML format is standard Grafana/Prometheus alert format
- Runbook URLs stored in annotations
- Some alerts may not have runbooks (gracefully handle)
