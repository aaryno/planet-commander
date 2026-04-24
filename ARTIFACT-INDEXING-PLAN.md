# Artifact Indexing — 7-Day Implementation Plan

**Created**: 2026-03-18
**Status**: Planning
**Priority**: HIGH (highest unique value)
**Effort**: 7 days (1 week)

---

## Overview

Auto-index all investigation artifacts from `~/claude/projects/*/artifacts/*.md` to enable:
- **"Similar investigations" suggestions** when working on JIRA tickets
- **Historical context** for incidents and debugging
- **Foundation for mitigation plan generation** (proactive incident response)
- **Searchable knowledge base** across all Compute team work

---

## Why Artifact Indexing First?

From AUTO-CONTEXT-ENRICHMENT-SPEC.md:

> **Priority**: MEDIUM | **Complexity**: Medium | **Impact**: High — prior investigations
>
> **Highest unique value** (leverage 100+ existing artifacts)

**Value Proposition**:
- **100+ existing artifacts** ready to index
- **Immediate value**: "Have we seen this before?" searches
- **Foundation for learning**: Pre-assembled mitigation plans based on past fixes
- **Unique to Compute team**: Other teams don't have this investigation corpus

**Why before Project Context Auto-Load**:
- Artifacts contain **actionable debugging steps** and **root causes**
- Project context files are **static documentation** (lower immediate value)
- Artifact search enables **incident response skill** improvements

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ File System (~/claude/projects/)                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  wx-notes/artifacts/20260211-1455-proximity-insights-mvp.md    │
│  g4-notes/artifacts/20260130-1200-chad-g4-cost-onboarding.md   │
│  jobs-notes/artifacts/20260219-1030-scheduler-alert-flap.md    │
│  temporal-notes/artifacts/20260203-0956-mastery-plan.md        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Background Job: Artifact Scanner (1 hour interval)              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Scan all artifact directories                               │
│  2. Parse metadata from filename + content                      │
│  3. Extract JIRA keys, keywords, entities                       │
│  4. Compute embedding (optional - Phase 2)                      │
│  5. Store in artifacts table                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Database (PostgreSQL)                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  artifacts                        entity_links                  │
│  - file_path                      - from: jira_issue           │
│  - filename                       - to: artifact                │
│  - project (wx, g4, jobs)         - link_type: references      │
│  - artifact_type (investigation)  - confidence: 0.90           │
│  - title, description, content    - auto-detected from JIRA    │
│  - jira_keys JSONB                                              │
│  - keywords JSONB                                               │
│  - created_at (from filename)                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ REST API (FastAPI)                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  GET /api/artifacts?project=wx&keywords=task,lease             │
│  GET /api/artifacts/{id}                                       │
│  GET /api/artifacts/search?jira_key=COMPUTE-1234               │
│  GET /api/artifacts/similar?artifact_id={id}                   │
│  POST /api/artifacts/{id}/refresh                              │
│  GET /api/artifacts/context/{context_id}                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Frontend (Next.js + React)                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  <ArtifactSection contextId={...} />                            │
│  <ArtifactCard artifact={...} />                                │
│  <ArtifactSearch keywords={...} />                              │
│                                                                  │
│  - Display related artifacts for JIRA ticket                    │
│  - Show "similar investigations" suggestions                    │
│  - Link to raw markdown files                                   │
│  - Preview first 200 chars                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7-Day Implementation Schedule

### Day 1: Database & Models (Tuesday)

**Goal**: Database schema and SQLAlchemy models

**Tasks**:
- [ ] Create Alembic migration `20260318_1700_create_artifacts.py`
- [ ] Define `Artifact` model with all fields
- [ ] Extend `EntityLink` with `REFERENCES_ARTIFACT` type
- [ ] Update `models/__init__.py` to export `Artifact`
- [ ] Run migration, verify table schema

**Database Schema**:
```sql
CREATE TABLE artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- File information
    file_path TEXT UNIQUE NOT NULL,
    filename VARCHAR(500) NOT NULL,
    file_size INTEGER,

    -- Metadata from filename
    project VARCHAR(100),  -- wx, g4, jobs, temporal, prodissue
    artifact_type VARCHAR(100),  -- investigation, plan, handoff, analysis, complete
    created_at TIMESTAMPTZ NOT NULL,  -- Parsed from filename YYYYMMDD-HHMM

    -- Content
    title TEXT,  -- Extracted from first heading
    description TEXT,  -- From filename description
    content TEXT,  -- Full markdown content

    -- Extracted entities
    jira_keys JSONB,  -- ["COMPUTE-1234", "WX-567"]
    keywords JSONB,  -- ["task", "lease", "expiration", "oom"]
    entities JSONB,  -- { "systems": ["G4", "DataCollect"], "people": ["aaryn"], "alerts": ["jobs-scheduler-low-runs"] }

    -- Timestamps
    file_modified_at TIMESTAMPTZ,
    indexed_at TIMESTAMPTZ DEFAULT now(),

    -- Soft delete
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_artifacts_project ON artifacts(project);
CREATE INDEX idx_artifacts_type ON artifacts(artifact_type);
CREATE INDEX idx_artifacts_created ON artifacts(created_at DESC);
CREATE INDEX idx_artifacts_jira_keys ON artifacts USING GIN(jira_keys);
CREATE INDEX idx_artifacts_keywords ON artifacts USING GIN(keywords);
CREATE INDEX idx_artifacts_file_path ON artifacts(file_path);
```

**Entity Link Extension**:
```python
class LinkType(str, Enum):
    # ... existing types
    REFERENCES_ARTIFACT = "references_artifact"
    MENTIONED_IN_ARTIFACT = "mentioned_in_artifact"
```

**Success Criteria**:
- Migration applies cleanly
- Table created with 14 columns, 6 indexes
- Model imports correctly

**Estimated Time**: 2-3 hours

---

### Day 2: Detection & Parsing Service (Wednesday)

**Goal**: Service to scan filesystem and parse artifact metadata

**Tasks**:
- [ ] Create `ArtifactService` class in `backend/app/services/artifact_service.py`
- [ ] Implement filename parsing (YYYYMMDD-HHMM-description.md)
- [ ] Implement content parsing (title extraction, JIRA key detection)
- [ ] Implement keyword extraction (from description + content)
- [ ] Implement entity extraction (systems, alerts, people)
- [ ] Write unit tests for parsing logic

**ArtifactService Interface**:
```python
class ArtifactService:
    """Service for indexing and searching artifacts."""

    # Filename pattern: YYYYMMDD-HHMM-{description}.md
    FILENAME_PATTERN = re.compile(
        r'^(\d{8})-(\d{4})-(.+)\.md$'
    )

    # JIRA key pattern
    JIRA_KEY_PATTERN = re.compile(
        r'\b(COMPUTE|WX|JOBS|TEMPORAL|G4|PRODISSUE)-\d+\b'
    )

    def __init__(self, db: AsyncSession):
        self.db = db

    async def scan_artifacts(
        self, base_path: str = "~/claude/projects"
    ) -> List[Artifact]:
        """Scan all artifact directories and index."""

    def parse_filename(self, filename: str) -> dict:
        """Extract metadata from filename.

        Returns:
            {
                "created_at": datetime,
                "description": str,
                "artifact_type": str  # inferred from description
            }
        """

    async def parse_content(self, file_path: str) -> dict:
        """Extract metadata from markdown content.

        Returns:
            {
                "title": str,  # First heading
                "content": str,
                "jira_keys": List[str],
                "keywords": List[str],
                "entities": dict
            }
        """

    def infer_artifact_type(self, description: str) -> str:
        """Infer artifact type from description.

        Types: investigation, plan, handoff, analysis,
               complete, findings, summary
        """

    def extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text (simple TF-IDF approach)."""

    def extract_entities(self, content: str) -> dict:
        """Extract systems, alerts, people from content.

        Returns:
            {
                "systems": ["WX", "G4", "Jobs"],
                "alerts": ["jobs-scheduler-low-runs"],
                "people": ["aaryn", "dharma"]
            }
        """
```

**Artifact Type Inference**:
```python
TYPE_PATTERNS = {
    "investigation": r"investigation|incident|debug|stuck|failure",
    "plan": r"plan|implementation|roadmap|strategy",
    "handoff": r"handoff|transition|summary",
    "analysis": r"analysis|audit|findings|review",
    "complete": r"complete|done|finished",
    "summary": r"summary|report|overview"
}
```

**Success Criteria**:
- Parse 100+ existing artifacts correctly
- Detect JIRA keys accurately (>95% precision)
- Infer artifact types correctly (>80% accuracy)
- Unit tests pass

**Estimated Time**: 4-5 hours

---

### Day 3: Filesystem Scanning (Thursday)

**Goal**: Scan artifact directories and populate database

**Tasks**:
- [ ] Implement `scan_artifacts()` method
- [ ] Handle project detection from directory structure
- [ ] Implement incremental scanning (only new/modified files)
- [ ] Create or update artifacts in database
- [ ] Test scanning all project artifact directories

**Scanning Strategy**:
```python
async def scan_artifacts(
    self, base_path: str = "~/claude/projects"
) -> dict:
    """Scan all artifact directories.

    Returns:
        {
            "total_scanned": 150,
            "new_artifacts": 12,
            "updated_artifacts": 3,
            "errors": []
        }
    """
    base_path = Path(base_path).expanduser()
    stats = {"total_scanned": 0, "new_artifacts": 0, "updated_artifacts": 0, "errors": []}

    # Scan each project directory
    for project_dir in base_path.glob("*-notes"):
        project = project_dir.name.replace("-notes", "")
        artifacts_dir = project_dir / "artifacts"

        if not artifacts_dir.exists():
            continue

        # Scan all .md files
        for file_path in artifacts_dir.glob("*.md"):
            try:
                await self._index_artifact(file_path, project)
                stats["total_scanned"] += 1
            except Exception as e:
                stats["errors"].append({
                    "file": str(file_path),
                    "error": str(e)
                })

    return stats
```

**Incremental Scanning**:
```python
async def _index_artifact(
    self, file_path: Path, project: str
) -> Artifact:
    """Index a single artifact file."""

    # Check if already indexed
    result = await self.db.execute(
        select(Artifact).where(Artifact.file_path == str(file_path))
    )
    existing = result.scalar_one_or_none()

    # Check if file modified since last index
    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)

    if existing and existing.file_modified_at >= file_mtime:
        # Already indexed and up-to-date
        return existing

    # Parse and index
    filename_meta = self.parse_filename(file_path.name)
    content_meta = await self.parse_content(str(file_path))

    if existing:
        # Update existing
        artifact = self._update_artifact(existing, filename_meta, content_meta)
    else:
        # Create new
        artifact = self._create_artifact(file_path, project, filename_meta, content_meta)

    await self.db.commit()
    return artifact
```

**Success Criteria**:
- Scan 100+ artifacts successfully
- Correctly detect projects (wx, g4, jobs, temporal)
- Incremental scanning works (doesn't re-index unchanged files)
- Database populated with artifact records

**Estimated Time**: 3-4 hours

---

### Day 4: API Endpoints (Friday)

**Goal**: REST API for artifact queries

**Tasks**:
- [ ] Create `backend/app/api/artifacts.py`
- [ ] Implement 6 async endpoints
- [ ] Add Pydantic response models
- [ ] Test all endpoints with curl

**API Endpoints**:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.db import get_db
from app.services.artifact_service import ArtifactService

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])

@router.get("", response_model=List[ArtifactResponse])
async def list_artifacts(
    project: Optional[str] = None,
    artifact_type: Optional[str] = None,
    keywords: Optional[str] = None,  # Comma-separated
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List artifacts with optional filters."""

@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get single artifact by ID."""

@router.get("/search", response_model=List[ArtifactResponse])
async def search_artifacts(
    jira_key: Optional[str] = None,
    keywords: Optional[str] = None,
    project: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search artifacts by JIRA key, keywords, or date range."""

@router.get("/similar/{artifact_id}", response_model=List[ArtifactResponse])
async def find_similar_artifacts(
    artifact_id: str,
    limit: int = Query(5, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Find similar artifacts based on keywords and entities.

    Phase 1: Keyword overlap + JIRA key overlap
    Phase 2: Embedding similarity (future)
    """

@router.post("/{artifact_id}/refresh", response_model=ArtifactResponse)
async def refresh_artifact(
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Force re-index of specific artifact."""

@router.get("/context/{context_id}", response_model=List[ArtifactResponse])
async def get_context_artifacts(
    context_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all artifacts linked to a work context."""
```

**Pydantic Models**:
```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ArtifactResponse(BaseModel):
    id: str
    file_path: str
    filename: str
    project: Optional[str]
    artifact_type: Optional[str]
    title: Optional[str]
    description: Optional[str]
    content_preview: str  # First 200 chars
    jira_keys: List[str]
    keywords: List[str]
    created_at: datetime
    file_modified_at: datetime
    indexed_at: datetime

    class Config:
        from_attributes = True
```

**Success Criteria**:
- All 6 endpoints working
- Search by JIRA key works
- Search by keywords works
- Similar artifacts returns relevant results

**Estimated Time**: 3-4 hours

---

### Day 5: Frontend Components (Monday)

**Goal**: React components for artifact display

**Tasks**:
- [ ] Add TypeScript types to `frontend/src/lib/api.ts`
- [ ] Add 6 artifact API methods
- [ ] Create `ArtifactCard` component
- [ ] Create `ArtifactSection` component
- [ ] Create `ArtifactSearch` component
- [ ] Verify TypeScript compilation and Next.js build

**TypeScript Types** (frontend/src/lib/api.ts):
```typescript
export interface Artifact {
  id: string;
  file_path: string;
  filename: string;
  project?: string;
  artifact_type?: string;
  title?: string;
  description?: string;
  content_preview: string;
  jira_keys: string[];
  keywords: string[];
  created_at: string;
  file_modified_at: string;
  indexed_at: string;
}

// Add to api object:
export const api = {
  // ... existing methods

  // Artifacts
  artifacts: (project?: string, type?: string, keywords?: string, limit = 50) =>
    fetchApi<Artifact[]>(`/artifacts?${params}`),

  artifact: (artifactId: string) =>
    fetchApi<Artifact>(`/artifacts/${artifactId}`),

  searchArtifacts: (jiraKey?: string, keywords?: string, project?: string, dateFrom?: string, dateTo?: string, limit = 20) =>
    fetchApi<Artifact[]>(`/artifacts/search?${params}`),

  similarArtifacts: (artifactId: string, limit = 5) =>
    fetchApi<Artifact[]>(`/artifacts/similar/${artifactId}?limit=${limit}`),

  refreshArtifact: (artifactId: string) =>
    fetchApi<Artifact>(`/artifacts/${artifactId}/refresh`, { method: "POST" }),

  contextArtifacts: (contextId: string) =>
    fetchApi<Artifact[]>(`/artifacts/context/${contextId}`),
};
```

**ArtifactCard Component**:
```tsx
// frontend/src/components/artifacts/ArtifactCard.tsx
import { Badge } from "@/components/ui/badge";
import { ExternalLink, FileText } from "lucide-react";
import type { Artifact } from "@/lib/api";

interface ArtifactCardProps {
  artifact: Artifact;
}

export function ArtifactCard({ artifact }: ArtifactCardProps) {
  // Format date: "Jan 15, 2026"
  const createdDate = new Date(artifact.created_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric"
  });

  // Type badge color
  const typeColor = {
    investigation: "bg-blue-500/20 text-blue-400",
    plan: "bg-purple-500/20 text-purple-400",
    handoff: "bg-amber-500/20 text-amber-400",
    analysis: "bg-emerald-500/20 text-emerald-400",
    complete: "bg-green-500/20 text-green-400"
  }[artifact.artifact_type || ""] || "bg-zinc-500/20 text-zinc-400";

  return (
    <div className="p-3 rounded border border-zinc-800 hover:border-zinc-700 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="w-4 h-4 text-zinc-500 flex-shrink-0" />
          <h4 className="text-sm font-medium text-zinc-200 truncate">
            {artifact.title || artifact.filename}
          </h4>
        </div>
        <a
          href={`file://${artifact.file_path}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-zinc-500 hover:text-zinc-400"
        >
          <ExternalLink className="w-4 h-4" />
        </a>
      </div>

      {artifact.description && (
        <p className="text-xs text-zinc-400 mt-1">{artifact.description}</p>
      )}

      <div className="flex items-center gap-2 mt-2 flex-wrap">
        <Badge className={typeColor}>{artifact.artifact_type}</Badge>
        {artifact.project && (
          <Badge variant="outline" className="text-xs">{artifact.project}</Badge>
        )}
        <span className="text-xs text-zinc-500">{createdDate}</span>
      </div>

      {artifact.jira_keys.length > 0 && (
        <div className="flex items-center gap-1 mt-2 flex-wrap">
          {artifact.jira_keys.map(key => (
            <Badge key={key} variant="outline" className="text-xs">
              {key}
            </Badge>
          ))}
        </div>
      )}

      {artifact.content_preview && (
        <p className="text-xs text-zinc-500 mt-2 line-clamp-2">
          {artifact.content_preview}
        </p>
      )}
    </div>
  );
}
```

**ArtifactSection Component**:
```tsx
// frontend/src/components/artifacts/ArtifactSection.tsx
import { useState, useCallback } from "react";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { ArtifactCard } from "./ArtifactCard";
import { Input } from "@/components/ui/input";
import { FileText, Search } from "lucide-react";

interface ArtifactSectionProps {
  contextId?: string;
  jiraKey?: string;
  project?: string;
  title?: string;
  emptyMessage?: string;
}

export function ArtifactSection({
  contextId,
  jiraKey,
  project,
  title = "Related Artifacts",
  emptyMessage = "No artifacts found"
}: ArtifactSectionProps) {
  const [keywordFilter, setKeywordFilter] = useState("");

  const fetcher = useCallback(() => {
    if (contextId) {
      return api.contextArtifacts(contextId);
    } else if (jiraKey) {
      return api.searchArtifacts(jiraKey);
    } else {
      return api.artifacts(project, undefined, keywordFilter || undefined);
    }
  }, [contextId, jiraKey, project, keywordFilter]);

  const { data: artifacts, loading, error, refetch } = usePoll(fetcher, 600_000); // 10 min

  const filteredArtifacts = artifacts?.filter(a => {
    if (!keywordFilter) return true;
    const searchText = `${a.title} ${a.description} ${a.keywords.join(" ")}`.toLowerCase();
    return searchText.includes(keywordFilter.toLowerCase());
  });

  const stickyHeader = (
    <div className="space-y-2">
      <div className="relative">
        <Search className="absolute left-2 top-2 h-4 w-4 text-zinc-500" />
        <Input
          placeholder="Filter by keywords..."
          value={keywordFilter}
          onChange={(e) => setKeywordFilter(e.target.value)}
          className="pl-8"
        />
      </div>
      <div className="flex justify-between items-center text-xs">
        <span className="text-zinc-500">
          {filteredArtifacts?.length || 0} artifact{filteredArtifacts?.length !== 1 ? 's' : ''}
        </span>
      </div>
    </div>
  );

  return (
    <ScrollableCard
      title={title}
      icon={<FileText className="w-5 h-5" />}
      menuItems={[{ label: "Refresh", onClick: refetch }]}
      stickyHeader={stickyHeader}
    >
      {loading && <p className="text-xs text-zinc-500">Loading artifacts...</p>}
      {error && <p className="text-xs text-red-400">Error loading artifacts</p>}
      {!loading && filteredArtifacts?.length === 0 && (
        <p className="text-xs text-zinc-500">{emptyMessage}</p>
      )}
      {filteredArtifacts && filteredArtifacts.length > 0 && (
        <div className="space-y-2">
          {filteredArtifacts.map(artifact => (
            <ArtifactCard key={artifact.id} artifact={artifact} />
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
- Artifact cards display all metadata

**Estimated Time**: 3-4 hours

---

### Day 6: Enrichment Integration (Tuesday)

**Goal**: Background job and auto-linking to JIRA issues

**Tasks**:
- [ ] Create `backend/app/jobs/artifact_indexing.py` background job
- [ ] Implement auto-linking logic (scan JIRA issues for artifact references)
- [ ] Register job in `main.py` (1 hour interval)
- [ ] Create migration to add artifact link types
- [ ] Test end-to-end enrichment flow

**Background Job**:
```python
# backend/app/jobs/artifact_indexing.py
import logging
from sqlalchemy import select
from app.db import async_session
from app.services.artifact_service import ArtifactService
from app.models.jira_issue import JiraIssue
from app.models.entity_link import EntityLink, LinkType, LinkSourceType, LinkStatus

logger = logging.getLogger(__name__)

async def index_artifacts():
    """Scan filesystem for artifacts and index to database.

    Runs every 1 hour to pick up new/modified artifacts.
    """
    async with async_session() as db:
        service = ArtifactService(db)

        logger.info("Starting artifact indexing scan")

        # Scan all artifact directories
        stats = await service.scan_artifacts()

        logger.info(
            f"Artifact indexing complete: {stats['total_scanned']} scanned, "
            f"{stats['new_artifacts']} new, {stats['updated_artifacts']} updated"
        )

        if stats['errors']:
            logger.warning(f"{len(stats['errors'])} errors during scan")
            for error in stats['errors'][:5]:  # Log first 5 errors
                logger.error(f"  {error['file']}: {error['error']}")

        return stats

async def link_artifacts_to_jira():
    """Auto-link artifacts to JIRA issues based on JIRA keys in filenames/content.

    Runs after artifact indexing to create entity_links.
    """
    async with async_session() as db:
        logger.info("Starting artifact → JIRA auto-linking")

        # Get all artifacts with JIRA keys
        result = await db.execute(
            select(Artifact).where(Artifact.jira_keys != None)
        )
        artifacts = result.scalars().all()

        links_created = 0

        for artifact in artifacts:
            if not artifact.jira_keys:
                continue

            for jira_key in artifact.jira_keys:
                # Find JIRA issue
                jira_result = await db.execute(
                    select(JiraIssue).where(JiraIssue.external_key == jira_key)
                )
                jira_issue = jira_result.scalar_one_or_none()

                if not jira_issue:
                    continue

                # Check if link already exists
                link_result = await db.execute(
                    select(EntityLink).where(
                        EntityLink.from_type == "jira_issue",
                        EntityLink.from_id == str(jira_issue.id),
                        EntityLink.to_type == "artifact",
                        EntityLink.to_id == str(artifact.id)
                    )
                )
                existing_link = link_result.scalar_one_or_none()

                if existing_link:
                    continue

                # Create entity link
                link = EntityLink(
                    from_type="jira_issue",
                    from_id=str(jira_issue.id),
                    to_type="artifact",
                    to_id=str(artifact.id),
                    link_type=LinkType.REFERENCES_ARTIFACT,
                    source_type=LinkSourceType.INFERRED,
                    confidence_score=0.90,  # High confidence from filename
                    status=LinkStatus.CONFIRMED
                )

                db.add(link)
                links_created += 1
                logger.info(f"Linked artifact {artifact.filename} → {jira_key}")

        await db.commit()
        logger.info(f"Artifact auto-linking complete: {links_created} links created")

        return {"links_created": links_created}
```

**Job Registration** (backend/app/main.py):
```python
from app.jobs.artifact_indexing import index_artifacts, link_artifacts_to_jira

# Artifact indexing: every 1 hour
job_service.add_interval_job(
    index_artifacts,
    job_id="artifact_indexing",
    hours=1
)

# Artifact → JIRA linking: every 1 hour (after indexing)
job_service.add_interval_job(
    link_artifacts_to_jira,
    job_id="artifact_jira_linking",
    hours=1
)
```

**Migration for Link Types**:
```python
# backend/alembic/versions/20260318_1800_add_artifact_link_types.py
def upgrade() -> None:
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'references_artifact'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'mentioned_in_artifact'")
```

**Success Criteria**:
- Background job runs successfully
- Artifacts indexed from filesystem
- Auto-links created to JIRA issues
- No duplicate links created

**Estimated Time**: 3-4 hours

---

### Day 7: Testing & Documentation (Wednesday)

**Goal**: End-to-end testing, documentation, polish

**Tasks**:
- [ ] Create comprehensive documentation (`ARTIFACT-INDEXING-COMPLETE.md`)
- [ ] Test full workflow:
  - [ ] Scan artifacts → Database populated
  - [ ] API endpoints → Search works
  - [ ] Frontend → Cards display correctly
  - [ ] Auto-linking → JIRA issues linked
- [ ] Test "similar artifacts" feature
- [ ] Verify performance (100+ artifacts)
- [ ] Clean up test files
- [ ] Update `PROGRESS.md`
- [ ] Final commit

**Documentation** (ARTIFACT-INDEXING-COMPLETE.md):
- Architecture diagram
- Usage guide (API + Frontend)
- Database schema
- Artifact type detection patterns
- Search strategies
- Configuration (scan interval, paths)
- Performance characteristics
- Troubleshooting guide
- Success criteria

**Test Scenarios**:
1. **Scan artifacts**: Verify 100+ artifacts indexed
2. **Search by JIRA key**: Find artifacts for COMPUTE-1234
3. **Search by keywords**: Find "task lease" artifacts
4. **Similar artifacts**: Find similar to OOM investigation
5. **Auto-linking**: Verify JIRA → artifact links created
6. **Frontend display**: Artifact cards show all metadata

**Success Criteria**:
- All tests pass
- Documentation complete
- PROGRESS.md updated
- Final commit pushed

**Estimated Time**: 3-4 hours

---

## Database Schema

### artifacts Table

```sql
CREATE TABLE artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- File information
    file_path TEXT UNIQUE NOT NULL,
    filename VARCHAR(500) NOT NULL,
    file_size INTEGER,

    -- Metadata from filename
    project VARCHAR(100),  -- wx, g4, jobs, temporal, prodissue
    artifact_type VARCHAR(100),  -- investigation, plan, handoff, analysis, complete
    created_at TIMESTAMPTZ NOT NULL,  -- Parsed from filename YYYYMMDD-HHMM

    -- Content
    title TEXT,  -- Extracted from first heading
    description TEXT,  -- From filename description
    content TEXT,  -- Full markdown content

    -- Extracted entities
    jira_keys JSONB,  -- ["COMPUTE-1234", "WX-567"]
    keywords JSONB,  -- ["task", "lease", "expiration", "oom"]
    entities JSONB,  -- { "systems": [...], "alerts": [...] }

    -- Timestamps
    file_modified_at TIMESTAMPTZ,
    indexed_at TIMESTAMPTZ DEFAULT now(),

    -- Soft delete
    deleted_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_artifacts_project ON artifacts(project);
CREATE INDEX idx_artifacts_type ON artifacts(artifact_type);
CREATE INDEX idx_artifacts_created ON artifacts(created_at DESC);
CREATE INDEX idx_artifacts_jira_keys ON artifacts USING GIN(jira_keys);
CREATE INDEX idx_artifacts_keywords ON artifacts USING GIN(keywords);
CREATE INDEX idx_artifacts_file_path ON artifacts(file_path);
```

**24 columns total, 6 indexes**

---

## Success Metrics

### Indexing Coverage
- **100+ artifacts indexed** from existing corpus
- **90%+ JIRA key detection accuracy**
- **80%+ artifact type inference accuracy**

### Search Quality
- **< 1 second** search response time
- **Top 5 results relevant** for keyword searches
- **"Similar artifacts" precision > 70%**

### Auto-Linking
- **80%+ of artifacts linked** to JIRA issues
- **No duplicate links** created
- **< 5% false positive** link rate

### User Experience
- **< 2 clicks** to see related artifacts for JIRA ticket
- **Artifact preview** shows enough context
- **Search filters work** (project, type, keywords)

---

## Next Steps (After Artifact Indexing)

From AUTO-CONTEXT-ENRICHMENT-SPEC.md:

1. **Project Context Auto-Load** (Week 6)
   - Parse all `{project}-claude.md` files
   - Auto-load context when project detected

2. **Grafana Alert Definitions** (Weeks 7-8)
   - Index alert definitions from repo
   - Link alerts to incidents

3. **GitLab MRs** (Weeks 9-10)
   - Fetch MR details via `glab` CLI
   - Auto-link MRs to contexts

---

## Open Questions

1. **Embeddings**: Add semantic search with embeddings now or later?
   - **Later**: Start with keyword + JIRA key overlap (Phase 1)
   - **Future**: Add embeddings for semantic similarity (Phase 2)

2. **Scan frequency**: 1 hour interval good enough?
   - **Yes**: Artifacts created infrequently, 1 hour is fine
   - **Alternative**: Watch filesystem for changes (more complex)

3. **Content size**: Index full content or just preview?
   - **Full content**: Enable full-text search later
   - **Storage**: 100 artifacts × 10KB = 1MB (negligible)

4. **File paths**: Store absolute or relative paths?
   - **Absolute**: Easier to link to files
   - **Relative**: More portable (but base path known)

---

## References

- **AUTO-CONTEXT-ENRICHMENT-SPEC.md**: Overall enrichment strategy
- **PAGERDUTY-INTEGRATION-COMPLETE.md**: Reference implementation
- **Existing artifacts**: `~/claude/projects/*/artifacts/*.md`
