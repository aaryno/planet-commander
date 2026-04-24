# Project Documentation Integration - 5-Day Plan

**Created**: March 19, 2026
**Purpose**: Index project documentation from `~/claude/projects/` for auto-loading context
**Pattern**: Following PagerDuty, Artifact, and Grafana Alerts precedent
**Estimated Duration**: 5 days (Days 1-5)

---

## Overview

Parse and index project documentation from `~/claude/projects/{project}-notes/{project}-claude.md` to enable:

1. **Project → documentation lookup** when tickets/chats reference projects
2. **Auto-load project context** based on JIRA ticket labels, Slack channels, working directory
3. **Documentation search** across all project docs
4. **Architecture/workflow visibility** for debugging
5. **Auto-linking** to work contexts, JIRA issues, agent chats
6. **Documentation freshness tracking** (last updated, staleness warnings)

**Value Proposition**: When working on `COMPUTE-1234` (labeled "wx"), Commander instantly shows:
- WX architecture overview
- Deployment procedures
- Common debug workflows
- Relevant monitoring dashboards
- Team contacts
- Recent doc updates

---

## Repository Structure

```
~/claude/projects/
├── wx-notes/
│   ├── wx-claude.md              # Main WX documentation
│   ├── artifacts/                # Investigation artifacts
│   ├── jira/                     # Ticket directories
│   ├── runbook/                  # Operational procedures
│   └── deploy/                   # Deployment docs
├── g4-notes/
│   ├── g4-claude.md
│   └── ...
├── jobs-notes/
│   ├── jobs-claude.md
│   └── ...
├── temporal-notes/
│   ├── temporal-claude.md
│   └── ...
└── projects-claude.md            # Cross-project index
```

**Project Claude Doc Format**:
```markdown
# Work Exchange (WX) Project Guide

## Architecture
- API: FastAPI + SQLAlchemy
- Database: PostgreSQL + Redis
- Deployment: Kubernetes (planet-node-pools)

## Key Repositories
- wx/wx - Main API
- wx/eso-golang - ESO worker

## Monitoring
- Grafana: https://planet.grafana.net/d/wx-overview/
- Logs: Loki (namespace: wx-staging, wx-production)

## Deployment
See deploy/deployment.md for full procedures
...
```

---

## Database Schema

### Table: `project_docs`

**Purpose**: Store parsed project documentation with metadata

```sql
CREATE TABLE project_docs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Project identity
    project_name VARCHAR(100) UNIQUE NOT NULL,  -- wx, g4, jobs, temporal
    file_path TEXT NOT NULL,  -- ~/claude/projects/wx-notes/wx-claude.md

    -- Content
    content TEXT NOT NULL,  -- Full markdown content
    content_hash VARCHAR(64),  -- SHA256 for change detection

    -- Metadata
    sections JSONB,  -- Parsed sections { "Architecture": "...", "Deployment": "..." }
    keywords TEXT[],  -- Extracted keywords for search
    links JSONB,  -- Extracted links { "repos": [...], "dashboards": [...] }

    -- Ownership
    team VARCHAR(100),  -- compute, datapipeline, hobbes
    primary_contact VARCHAR(200),  -- Team lead or primary maintainer

    -- Repository info
    repositories TEXT[],  -- Associated GitLab repos (wx/wx, wx/eso-golang)

    -- Slack channels
    slack_channels TEXT[],  -- Associated channels (#wx-dev, #wx-users)

    -- Timestamps
    file_modified_at TIMESTAMPTZ,
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_project_docs_name ON project_docs(project_name);
CREATE INDEX idx_project_docs_team ON project_docs(team);
CREATE INDEX idx_project_docs_modified ON project_docs(file_modified_at);
CREATE INDEX idx_project_docs_keywords ON project_docs USING GIN(keywords);
```

**Computed Properties** (in SQLAlchemy model):
- `is_stale`: file_modified_at > 30 days ago
- `word_count`: Approximate documentation size
- `last_updated_days_ago`: Days since last file modification

---

### Table: `project_doc_sections`

**Purpose**: Store individual sections for granular linking

```sql
CREATE TABLE project_doc_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    project_doc_id UUID NOT NULL REFERENCES project_docs(id) ON DELETE CASCADE,

    -- Section identity
    section_name VARCHAR(200) NOT NULL,  -- "Architecture", "Deployment", etc.
    heading_level INT NOT NULL,  -- 1-6 (markdown heading level)
    order_index INT NOT NULL,  -- Position in document

    -- Content
    content TEXT NOT NULL,
    content_hash VARCHAR(64),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_doc_sections_project ON project_doc_sections(project_doc_id);
CREATE INDEX idx_doc_sections_name ON project_doc_sections(section_name);
CREATE UNIQUE INDEX idx_doc_sections_order ON project_doc_sections(project_doc_id, order_index);
```

**Use Case**: Link directly to specific sections
- "See Architecture section in wx-claude.md" → Direct section link
- "Check Deployment procedures" → Link to Deployment section

---

### EntityLink Extensions

Add new link types for project documentation:

```python
class LinkType(str, enum.Enum):
    # ... existing types
    PROJECT_CONTEXT = "project_context"  # Entity uses this project context
    DOCUMENTED_IN = "documented_in"      # Entity documented in section
    REFERENCES_PROJECT = "references_project"  # Entity references project
```

**Examples**:
- JIRA `COMPUTE-1234` (label: "wx") → PROJECT_CONTEXT → wx-notes
- Agent chat in `~/code/wx/wx-1/` → PROJECT_CONTEXT → wx-notes
- Slack message in `#wx-dev` → PROJECT_CONTEXT → wx-notes

---

## Implementation Plan

### Day 1: Database Schema & Models (Tuesday)

**Goal**: Create tables and SQLAlchemy models

**Tasks**:
- [ ] Create Alembic migration `20260320_0900_create_project_docs.py`
- [ ] Create `app/models/project_doc.py`
- [ ] Create `app/models/project_doc_section.py`
- [ ] Extend `app/models/entity_link.py` with new link types
- [ ] Run migration and verify schema

**Migration**:
```python
def upgrade() -> None:
    op.create_table('project_docs', ...)
    op.create_table('project_doc_sections', ...)
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'project_context'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'documented_in'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'references_project'")
```

**Models**:
```python
class ProjectDoc(Base):
    __tablename__ = "project_docs"

    @property
    def is_stale(self) -> bool:
        if not self.file_modified_at:
            return False
        days_ago = (datetime.utcnow() - self.file_modified_at).days
        return days_ago > 30

    @property
    def word_count(self) -> int:
        return len(self.content.split())
```

**Success Criteria**:
- Migration runs successfully
- Models import without errors
- Can create test ProjectDoc records

**Estimated Time**: 2-3 hours

---

### Day 2: Service Layer (Wednesday)

**Goal**: Parse and index project documentation files

**Tasks**:
- [ ] Create `app/services/project_doc_service.py`
- [ ] Implement `scan_project_docs()` — Scan `~/claude/projects/`
- [ ] Implement `parse_markdown()` — Extract sections, keywords, links
- [ ] Implement `update_project_doc()` — Upsert based on content hash
- [ ] Implement `search_project_docs()` — Full-text search
- [ ] Write unit tests

**Service Methods**:

```python
class ProjectDocService:
    """Service for parsing and indexing project documentation."""

    PROJECTS_DIR = Path.home() / "claude" / "projects"

    async def scan_project_docs(self) -> Dict:
        """Scan ~/claude/projects/ for *-notes/*-claude.md files.

        Returns:
            Dict with scan statistics
        """

    def parse_markdown(self, content: str) -> Dict:
        """Parse markdown content into sections.

        Returns:
            {
                "sections": [{"name": "Architecture", "level": 2, "content": "..."}],
                "keywords": ["wx", "kubernetes", "fastapi"],
                "links": {"repos": [...], "dashboards": [...]}
            }
        """

    async def update_project_doc(self, project_name: str, file_path: Path) -> ProjectDoc:
        """Update or create project doc from file.

        Uses content hash to detect changes (skip unchanged files).
        """

    async def search_project_docs(
        self,
        query: str,
        project: Optional[str] = None,
        team: Optional[str] = None,
        limit: int = 20
    ) -> List[ProjectDoc]:
        """Search project docs by keywords/content."""

    async def infer_project_from_context(
        self,
        jira_labels: Optional[List[str]] = None,
        slack_channel: Optional[str] = None,
        working_dir: Optional[str] = None
    ) -> Optional[str]:
        """Infer project name from context clues.

        Examples:
        - JIRA label "wx" → "wx"
        - Slack channel "#wx-dev" → "wx"
        - Working dir "~/code/wx/wx-1/" → "wx"
        """
```

**Markdown Parsing Strategy**:
1. Split on headings (`##`, `###`, etc.)
2. Extract section names and content
3. Extract keywords (from headings + common tech terms)
4. Extract links (URLs, file paths, repo names)

**Success Criteria**:
- Can scan `~/claude/projects/` and find all `*-claude.md` files
- Can parse markdown into sections
- Can detect file changes via content hash
- Can search across all docs

**Estimated Time**: 4-5 hours

---

### Day 3: API Endpoints (Thursday)

**Goal**: REST API for project documentation

**Tasks**:
- [ ] Create `app/api/project_docs.py`
- [ ] Implement 5 endpoints (list, get, search, scan, sections)
- [ ] Add Pydantic response models
- [ ] Register router in `app/main.py`
- [ ] Test all endpoints

**API Endpoints**:

```python
@router.get("", response_model=List[ProjectDocResponse])
async def list_project_docs(
    team: Optional[str] = None,
    stale_only: bool = False,
    limit: int = Query(50, le=100),
):
    """List all project documentation."""

@router.get("/{project_name}", response_model=ProjectDocResponse)
async def get_project_doc(project_name: str):
    """Get project documentation by name (e.g., 'wx')."""

@router.get("/{project_name}/sections", response_model=List[SectionResponse])
async def get_project_sections(project_name: str):
    """Get all sections for a project."""

@router.get("/search", response_model=List[ProjectDocResponse])
async def search_project_docs(
    query: str,
    project: Optional[str] = None,
    team: Optional[str] = None,
    limit: int = Query(20, le=100),
):
    """Search project documentation."""

@router.post("/scan", response_model=ScanResponse)
async def scan_project_docs():
    """Trigger project docs scan."""
```

**Pydantic Models**:
```python
class ProjectDocResponse(BaseModel):
    id: str
    project_name: str
    file_path: str
    team: str | None
    repositories: List[str]
    slack_channels: List[str]
    word_count: int
    is_stale: bool
    last_updated_days_ago: int
    file_modified_at: datetime | None
    last_synced_at: datetime

class SectionResponse(BaseModel):
    id: str
    section_name: str
    heading_level: int
    content: str
    order_index: int
```

**Success Criteria**:
- All 5 endpoints functional
- Can list/search/get project docs
- Scan endpoint triggers repo sync
- Sections endpoint returns parsed markdown

**Estimated Time**: 3-4 hours

---

### Day 4: Frontend Components (Friday)

**Goal**: UI components for project documentation display

**Tasks**:
- [ ] Add TypeScript types to `frontend/src/lib/api.ts`
- [ ] Create `ProjectDocCard` component
- [ ] Create `ProjectDocSection` component
- [ ] Create `ProjectDocsGrid` component (shows all projects)
- [ ] Test TypeScript compilation and Next.js build

**TypeScript Interface**:
```typescript
export interface ProjectDoc {
  id: string;
  project_name: string;
  file_path: string;
  team: string | null;
  repositories: string[];
  slack_channels: string[];
  word_count: number;
  is_stale: boolean;
  last_updated_days_ago: number;
  file_modified_at: string | null;
  last_synced_at: string;
}

export interface ProjectDocSection {
  id: string;
  section_name: string;
  heading_level: number;
  content: string;
  order_index: number;
}

// API methods
export const api = {
  // ... existing methods
  projectDocs: (team?, staleOnly = false, limit = 50) =>
    fetchApi<ProjectDoc[]>(`/project-docs?${params}`),

  projectDoc: (projectName: string) =>
    fetchApi<ProjectDoc>(`/project-docs/${projectName}`),

  projectSections: (projectName: string) =>
    fetchApi<ProjectDocSection[]>(`/project-docs/${projectName}/sections`),

  searchProjectDocs: (query, project?, team?, limit = 20) =>
    fetchApi<ProjectDoc[]>(`/project-docs/search?${params}`),

  scanProjectDocs: () =>
    fetchApi<{...}>("/project-docs/scan", { method: "POST" }),
};
```

**Components**:

```tsx
// ProjectDocCard.tsx - Display single project doc
interface ProjectDocCardProps {
  doc: ProjectDoc;
  showSections?: boolean;
}

export function ProjectDocCard({ doc, showSections = false }) {
  // Show project name, team, repos, slack channels
  // Word count badge
  // Stale warning badge if is_stale
  // Expandable sections if showSections
}
```

```tsx
// ProjectDocsGrid.tsx - Grid of all project docs
export function ProjectDocsGrid() {
  const { data: docs, loading, error, refresh } = usePoll(
    () => api.projectDocs(),
    600_000 // 10 min
  );

  return (
    <ScrollableCard
      title="Project Documentation"
      icon={<BookOpen />}
      menuItems={[{ label: "Refresh", onClick: refresh }]}
    >
      <div className="grid grid-cols-2 gap-4">
        {docs?.map(doc => <ProjectDocCard key={doc.id} doc={doc} />)}
      </div>
    </ScrollableCard>
  );
}
```

**Success Criteria**:
- Can display all project docs in grid
- Can view individual project with sections
- Stale warning shows for >30 day old docs
- TypeScript compiles without errors

**Estimated Time**: 3-4 hours

---

### Day 5: Background Jobs & Auto-Linking (Monday)

**Goal**: Automated sync and intelligent linking

**Tasks**:
- [ ] Create `app/jobs/project_doc_sync.py`
- [ ] Implement `sync_project_docs()` background job
- [ ] Implement `link_projects_to_entities()` auto-linking
- [ ] Register jobs in `app/main.py`
- [ ] Test background job execution
- [ ] Documentation and testing

**Background Jobs**:

```python
# app/jobs/project_doc_sync.py

async def sync_project_docs() -> Dict:
    """Sync project docs from ~/claude/projects/.

    Runs every 1 hour.
    Scans for *-notes/*-claude.md files.
    Updates docs if content hash changed.
    """

async def link_projects_to_entities() -> Dict:
    """Auto-link project docs to work contexts.

    Runs every 1 hour.

    Links created:
    1. JIRA issue (label "wx") → PROJECT_CONTEXT → wx-notes
    2. Agent chat (cwd ~/code/wx/) → PROJECT_CONTEXT → wx-notes
    3. Slack message (#wx-dev) → PROJECT_CONTEXT → wx-notes
    4. Artifact (path mentions wx) → PROJECT_CONTEXT → wx-notes
    """
```

**Auto-Linking Logic**:

1. **JIRA → Project**:
   - Check JIRA issue labels
   - If label matches project name (wx, g4, jobs, temporal) → Link

2. **Agent → Project**:
   - Check agent chat working directory
   - Extract project from path (`~/code/wx/` → wx, `~/workspaces/g4/` → g4)
   - Link to project doc

3. **Slack → Project**:
   - Channel mapping:
     - `#wx-dev`, `#wx-users` → wx
     - `#g4-users` → g4
     - `#jobs-users` → jobs
     - `#temporalio-cloud` → temporal
   - Link messages to project doc

4. **Artifact → Project**:
   - Check artifact file path
   - If path contains `wx-notes`, `g4-notes`, etc. → Link to project

**Job Registration**:
```python
# app/main.py

job_service.add_interval_job(
    sync_project_docs,
    job_id="project_doc_sync",
    hours=1
)

job_service.add_interval_job(
    link_projects_to_entities,
    job_id="project_doc_linking",
    hours=1
)
```

**Success Criteria**:
- Background jobs run without errors
- Project docs sync every hour
- Auto-linking creates appropriate entity_links
- Can query project context from any entity

**Estimated Time**: 3-4 hours

---

## Success Metrics

### Data Quality
- **All projects indexed**: wx, g4, jobs, temporal, prodissue, etc.
- **Sections parsed**: 100+ sections across all docs
- **Links extracted**: Repos, dashboards, runbooks
- **Keywords indexed**: 500+ unique keywords

### Performance
- **< 2 seconds** to scan all project docs
- **< 50ms** to query project by name
- **< 100ms** to search across all docs

### Integration
- **Auto-linking** to JIRA (by label), agents (by cwd), Slack (by channel)
- **Entity links** created between projects and work contexts
- **Ready for context loading** when work starts

---

## Project → Entity Mapping

### High-Value Auto-Link Scenarios

| Entity Type | Detection | Project Link | Use Case |
|-------------|-----------|--------------|----------|
| **JIRA Issue** | Label "wx" | wx-notes | Load WX context when ticket opened |
| **Agent Chat** | cwd ~/code/wx/ | wx-notes | Auto-load WX docs in chat |
| **Slack Message** | Channel #wx-dev | wx-notes | Link channel discussions to project |
| **Artifact** | Path wx-notes/ | wx-notes | Connect investigations to project |
| **MR** | Repo wx/wx | wx-notes | Link code changes to project |
| **Alert** | Name wx-* | wx-notes | Connect alerts to project docs |

---

## Future Enhancements

### Phase 2: Section Linking
- Link JIRA tickets to specific doc sections
- "See Architecture section" → Direct link to section
- Section-level staleness tracking

### Phase 3: Documentation Validation
- Detect broken links in docs
- Validate dashboard URLs exist
- Check runbook links are accessible
- Flag outdated procedures

### Phase 4: Documentation Suggestions
- Suggest doc updates when incidents occur
- Auto-generate runbook entries from incident resolutions
- Detect missing documentation (projects without docs)
- Documentation completeness score

### Phase 5: Cross-Project Intelligence
- Detect similar sections across projects
- Suggest documentation reuse opportunities
- Find common patterns (all projects use K8s, FastAPI, etc.)
- Generate cross-project index

---

## Files to Create/Modify

### Backend (7 files)
- `backend/alembic/versions/20260320_0900_create_project_docs.py`
- `backend/app/models/project_doc.py`
- `backend/app/models/project_doc_section.py`
- `backend/app/models/entity_link.py` (extend LinkType)
- `backend/app/services/project_doc_service.py`
- `backend/app/api/project_docs.py`
- `backend/app/jobs/project_doc_sync.py`
- `backend/app/main.py` (register jobs)

### Frontend (4 files)
- `frontend/src/lib/api.ts` (types + methods)
- `frontend/src/components/docs/ProjectDocCard.tsx`
- `frontend/src/components/docs/ProjectDocSection.tsx`
- `frontend/src/components/docs/ProjectDocsGrid.tsx`

**Total**: ~11 files, ~1,150 lines of code

---

## Status

**✅ COMPLETE** - All Days 1-5 finished (March 19, 2026)

See [PROJECT-DOCS-INTEGRATION-COMPLETE.md](./PROJECT-DOCS-INTEGRATION-COMPLETE.md) for full implementation details, testing results, and usage examples.

---

## Comparison to Previous Integrations

| Feature | PagerDuty | Artifacts | Grafana Alerts | Project Docs |
|---------|-----------|-----------|----------------|--------------|
| Database tables | 1 | 1 | 2 | 2 |
| Service layer | ✅ | ✅ | ✅ | ✅ |
| API endpoints | 6 | 7 | 6 | 5 |
| Frontend components | 1 card | 2 cards | 2 cards | 3 cards |
| Background jobs | 1 (30min) | 2 (1h each) | 2 (1h each) | 2 (1h each) |
| Entity linking | ✅ | ✅ | ✅ | ✅ |
| Search/filter | ✅ | ✅ | ✅ | ✅ |

**Pattern Consistency**: 100% — Following exact same structure

---

## Next Integration After This

After Project Docs, the next high-value integration from AUTO-CONTEXT-ENRICHMENT-SPEC is:

**Google Drive Docs** — Index RFDs, postmortems, and planning docs from Compute Team shared drive for incident context and architecture decisions.

---

## Notes

- Project docs location: `~/claude/projects/{project}-notes/{project}-claude.md`
- Directory structure: `{project}-notes/` (standardized)
- Markdown format: CommonMark with extensions
- Content hash: SHA256 for change detection (skip unchanged files)
- Some projects may not have all sections (gracefully handle)
- Cross-project index: `~/claude/projects/projects-claude.md`

---

**Status**: Ready to implement
**Next Step**: Day 1 - Database Schema & Models
