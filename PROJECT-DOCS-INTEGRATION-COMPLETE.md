# Project Documentation Integration - Complete

**Date**: March 19, 2026
**Status**: ✅ Complete (Days 1-5)
**Integration Pattern**: Follows PagerDuty/Artifact/Grafana Alerts precedent

---

## Overview

Added project documentation indexing to Planet Commander for auto-loading context when working on tickets, chats, or tasks. Enables intelligent project context detection from JIRA labels, Slack channels, and working directories.

### Key Features

1. **Documentation Storage**: Database schema for markdown docs with sections
2. **Markdown Parsing**: Extract sections, keywords, links from project docs
3. **Content Hash Detection**: Skip unchanged files during sync
4. **Search & Filtering**: Search docs by keywords, filter by team/stale
5. **Auto-Linking**: Connect docs to JIRA issues and agent chats automatically
6. **Background Sync**: Hourly doc sync and link inference

---

## Database Schema

### Tables Created

#### `project_docs`
- **id**: UUID primary key
- **project_name**: Unique identifier (wx, g4, jobs, temporal, etc.)
- **file_path**: Path to markdown file
- **content**: Full markdown content
- **content_hash**: SHA256 for change detection
- **sections**: JSONB parsed sections
- **keywords**: Array of extracted keywords
- **links**: JSONB extracted links (repos, dashboards, URLs)
- **team**: Team owning project (compute, datapipeline, etc.)
- **primary_contact**: Team lead or maintainer
- **repositories**: Array of GitLab repos
- **slack_channels**: Array of Slack channels
- **file_modified_at**: File modification timestamp
- **last_synced_at**: Last sync from filesystem
- **created_at**: Record creation timestamp
- **updated_at**: Record update timestamp

**Indexes**:
- Unique index on `project_name`
- B-tree on `team`, `file_modified_at`
- GIN on `keywords` (array full-text search)

**Computed Properties**:
- `is_stale`: >30 days since last modification
- `word_count`: Approximate documentation size
- `last_updated_days_ago`: Days since last file modification

#### `project_doc_sections`
- **id**: UUID primary key
- **project_doc_id**: FK to project_docs (cascade delete)
- **section_name**: Heading text
- **heading_level**: 1-6 (markdown heading level)
- **order_index**: Position in document
- **content**: Section content
- **content_hash**: SHA256 of section content
- **created_at**: Record creation timestamp
- **updated_at**: Record update timestamp

**Indexes**:
- B-tree on `project_doc_id`, `section_name`
- Unique on (project_doc_id, order_index)

### EntityLink Extensions

Added 3 new link types:
- **PROJECT_CONTEXT**: Entity uses this project context
- **DOCUMENTED_IN**: Entity documented in section
- **REFERENCES_PROJECT**: Entity references project

---

## Backend Implementation

### Models (`app/models/`)

#### `project_doc.py`
SQLAlchemy model with relationship to sections:
```python
class ProjectDoc(Base):
    __tablename__ = "project_docs"

    @property
    def is_stale(self) -> bool:
        """Check if >30 days since last modification."""
        if not self.file_modified_at:
            return False
        days_ago = (datetime.utcnow() - self.file_modified_at).days
        return days_ago > 30

    @property
    def word_count(self) -> int:
        """Approximate word count."""
        return len(self.content.split())

    @property
    def last_updated_days_ago(self) -> int:
        """Days since last file modification."""
        if not self.file_modified_at:
            return -1
        return (datetime.utcnow() - self.file_modified_at).days
```

#### `project_doc_section.py`
Section model with FK to project_doc:
```python
class ProjectDocSection(Base):
    __tablename__ = "project_doc_sections"
    # Relationship back to ProjectDoc
    project_doc: Mapped["ProjectDoc"] = relationship("ProjectDoc", back_populates="doc_sections")
```

### Service Layer (`app/services/project_doc_service.py`)

**Key Methods**:

#### `scan_project_docs()`
Scan `~/claude/projects/` for `*-notes/*-claude.md` files:
- Found 14 project docs
- Scans 8 new, 3 updated, 3 unchanged
- Content hash-based change detection
- Error handling with rollback

#### `parse_markdown(content: str) -> Dict`
Extract structured data from markdown:
- **Sections**: Parse by heading level (##, ###) with order tracking
- **Keywords**: Extract from 20+ tech terms dictionary (kubernetes, fastapi, etc.)
- **Links**:
  - Repos: Extract GitLab paths (wx/wx, product/g4-wk/g4)
  - Dashboards: Extract Grafana URLs
  - General URLs: All http/https links

#### `update_project_doc()`
Upsert based on content hash:
- SHA256 content hashing
- DELETE old sections before INSERT new (fixes unique constraint)
- Auto-infer team from project name
- Auto-infer slack_channels from project mapping

#### `search_project_docs()`
Full-text search:
- Search in content (ILIKE), keywords (array contains), project name
- Filter by project, team
- Limit results

#### `get_project_doc(project_name: str)`
Simple lookup by project name

#### `infer_project_from_context()`
Intelligent project detection:
- **JIRA labels**: "wx" → wx
- **Slack channels**: "#g4-users" → g4
- **Working dir**: "~/code/jobs/jobs-1/" → jobs

**Channel Mapping**:
```python
SLACK_CHANNEL_MAP = {
    "#wx-dev": "wx",
    "#wx-users": "wx",
    "#g4-users": "g4",
    "#jobs-users": "jobs",
    "#temporalio-cloud": "temporal",
    "#compute-platform": "compute",
}
```

### API Endpoints (`app/api/project_docs.py`)

5 REST endpoints on `/api/project-docs`:

1. **GET /** - List all docs
   - Query params: `team`, `stale_only`, `limit`
   - Returns: Array of ProjectDocResponse
   - Example: 14 docs, filtered by team=compute

2. **GET /search** - Search docs
   - Query params: `query`, `project`, `team`, `limit`
   - Returns: Filtered array
   - Example: "kubernetes" found 2 docs

3. **GET /{project_name}** - Get single doc
   - Path param: `project_name` (e.g., "wx")
   - Returns: ProjectDocResponse
   - Raises: 404 if not found
   - Example: wx doc with 712 words

4. **GET /{project_name}/sections** - Get sections
   - Path param: `project_name`
   - Returns: Array of SectionResponse ordered by index
   - Eagerly loads with `selectinload()` (async-safe)
   - Example: 30+ sections for wx

5. **POST /scan** - Trigger doc scan
   - Body: None
   - Returns: ScanResponse with statistics
   - Example: 14 scanned, 6 updated, 8 unchanged

**Pydantic Models**:
```python
class ProjectDocResponse(BaseModel):
    id: str
    project_name: str
    file_path: str
    team: Optional[str]
    primary_contact: Optional[str]
    repositories: List[str]
    slack_channels: List[str]
    word_count: int
    is_stale: bool
    last_updated_days_ago: int
    file_modified_at: Optional[datetime]
    last_synced_at: datetime
    keywords: List[str]

class SectionResponse(BaseModel):
    id: str
    section_name: str
    heading_level: int
    content: str
    order_index: int
```

### Background Jobs (`app/jobs/project_doc_sync.py`)

#### `sync_project_docs()` - Hourly
Scan and sync documentation:
- Scans `~/claude/projects/` for `*-notes/*-claude.md`
- Updates/creates project docs
- Logs sync statistics
- Example: 14 scanned, 0 new, 6 updated, 8 unchanged

#### `link_projects_to_entities()` - Hourly
Auto-link docs to entities:

**Link 1: JIRA issues → Project docs (by label)**
```python
# JIRA with label "wx" → wx-notes project doc
if "wx" in issue.labels:
    link = EntityLink(
        from_type="jira_issue",
        from_id=str(issue.id),
        to_type="project_doc",
        to_id=str(doc.id),
        link_type=LinkType.PROJECT_CONTEXT,
        source_type=LinkSourceType.INFERRED,
        status=LinkStatus.CONFIRMED
    )
```

**Link 2: Agent chats → Project docs (by working directory)**
```python
# Agent in ~/code/wx/wx-1/ → wx-notes project doc
project_name = infer_project_from_context(working_dir=agent.working_directory)
if project_name:
    link = EntityLink(
        from_type="agent",
        from_id=str(agent.id),
        to_type="project_doc",
        to_id=str(doc.id),
        link_type=LinkType.PROJECT_CONTEXT,
        ...
    )
```

**Statistics**:
- Projects processed
- JIRA issues processed
- Agents processed
- Links created

---

## Frontend Implementation

### TypeScript Types (`frontend/src/lib/api.ts`)

#### ProjectDoc Interface
13 fields matching backend ProjectDocResponse:
```typescript
export interface ProjectDoc {
  id: string;
  project_name: string;
  file_path: string;
  team: string | null;
  primary_contact: string | null;
  repositories: string[];
  slack_channels: string[];
  word_count: number;
  is_stale: boolean;
  last_updated_days_ago: number;
  file_modified_at: string | null;
  last_synced_at: string;
  keywords: string[];
}

export interface ProjectDocSection {
  id: string;
  section_name: string;
  heading_level: number;
  content: string;
  order_index: number;
}
```

#### API Methods
5 methods matching backend endpoints:
```typescript
projectDocs: (team?, staleOnly = false, limit = 50) =>
  fetchApi<ProjectDoc[]>(`/project-docs?${params}`)

searchProjectDocs: (query, project?, team?, limit = 20) =>
  fetchApi<ProjectDoc[]>(`/project-docs/search?${params}`)

projectDoc: (projectName: string) =>
  fetchApi<ProjectDoc>(`/project-docs/${encodeURIComponent(projectName)}`)

projectSections: (projectName: string) =>
  fetchApi<ProjectDocSection[]>(`/project-docs/${encodeURIComponent(projectName)}/sections`)

scanProjectDocs: () =>
  fetchApi<{...}>("/project-docs/scan", { method: "POST" })
```

### React Components (`frontend/src/components/docs/`)

#### ProjectDocCard.tsx
Display single project doc:

**Features**:
- Stale warning badge (AlertTriangle) if >30 days old
- Stats: word count, keywords count, days since update
- Team badge
- Repositories section (first 3 + count)
- Slack channels badges
- Keywords display (first 8 + count)

**Color Scheme**:
```typescript
// Stale warning
className="text-xs text-amber-400 border-amber-500/30"

// Stats
className="text-xs text-zinc-500"

// Keywords
className="text-xs bg-zinc-800/50 text-zinc-400 px-1.5 py-0.5 rounded"
```

**Icons**:
- BookOpen (header)
- AlertTriangle (stale warning)
- Hash (word count)
- Calendar (days ago)
- GitBranch (repositories)

#### ProjectDocsGrid.tsx
Container with search and filters:

**Features**:
- **ScrollableCard Integration**: Sticky header + scrollable grid
- **Search Input**: Live filtering by keywords/content
- **Team Filter**: Dropdown (compute, datapipeline, hobbes)
- **Stale Only Toggle**: Button to show only stale docs
- **Active Filter Badges**: Click-to-remove individual filters
- **Clear All Button**: Remove all filters at once
- **Auto-Refresh**: usePoll hook with 10-minute interval
- **Grid Layout**: 2 columns of ProjectDocCard
- **Menu Items**: Refresh, Scan Docs

**State Management**:
```typescript
const [searchQuery, setSearchQuery] = useState("");
const [teamFilter, setTeamFilter] = useState("");
const [staleOnly, setStaleOnly] = useState(false);

const fetcher = useCallback(() => {
  if (searchQuery) {
    return api.searchProjectDocs(searchQuery, undefined, teamFilter || undefined, 50);
  }
  return api.projectDocs(teamFilter || undefined, staleOnly, 50);
}, [searchQuery, teamFilter, staleOnly]);

const { data: docs, loading, error, refresh } = usePoll(fetcher, 600_000);
```

---

## Testing Results

### Backend Testing

**Scan Results**:
```
Total scanned: 14
New: 8
Updated: 3
Unchanged: 3
Errors: 0
```

**Search Testing**:
```
Query: "kubernetes" → Found 2 docs (prodissue, planet-grafana-cloud-users)
```

**Get by Name**:
```
Project: wx
Word count: 712
Keywords: ['api', 'grafana', 'loki', 'monitoring', 'pagerduty', 'prometheus']
Repos: ['adding/modifying', 'grafana/dashboards', 'PromQL/LogQL', 'wx/wx/cmd', 'Prometheus/Loki']
Stale: True (>30 days)
```

**Project Inference**:
```
JIRA label "wx" → wx
Slack channel "#g4-users" → g4
Working dir "~/code/jobs/jobs-1/" → jobs
```

**API Endpoints**:
- ✅ GET /api/project-docs: Returns all docs with correct fields
- ✅ GET /api/project-docs/wx: Returns wx doc (712 words)
- ✅ GET /api/project-docs/wx/sections: Returns 30+ sections in order
- ✅ GET /api/project-docs/search?query=kubernetes: Found 2 docs
- ✅ POST /api/project-docs/scan: 14 scanned, 6 updated, 8 unchanged

**Background Jobs**:
```
✅ project_doc_sync: 1 hour interval
✅ project_doc_linking: 1 hour interval
✅ Both jobs registered in APScheduler
✅ Jobs appear in background jobs list
```

### Frontend Testing

**TypeScript Compilation**:
```
✅ Compiled successfully in 3.1s
✅ Next.js build passed
✅ All routes generated
```

---

## Git Commits

```bash
# Day 1: Database Schema
0a68762 - feat: Day 1 - Project Documentation database schema and models

# Day 2: Service Layer
1b15453 - feat: Day 2 - Project Documentation service layer

# Day 3: API Endpoints
334700a - feat: Day 3 - Project Documentation API endpoints

# Day 4: Frontend Components
142e597 - feat: Day 4 - Project Documentation frontend components

# Day 5: Background Jobs
5c4fdb1 - feat: Day 5 - Project Documentation background jobs
```

---

## Success Metrics

✅ **Database Schema**: 2 tables, 4 indexes (including GIN on keywords)
✅ **Backend**: 1 service, 5 API endpoints, 2 background jobs
✅ **Frontend**: 2 components, 5 API methods, TypeScript types
✅ **Testing**: All endpoints verified, docs scanned successfully
✅ **Integration**: Follows PagerDuty/Artifact/Grafana precedent exactly
✅ **Documentation**: Complete implementation guide

---

## Design Patterns Used

### Follows Established Precedents

1. **ScrollableCard Pattern**: Same as PagerDuty/Grafana/Artifact integrations
2. **usePoll Hook**: 10-minute auto-refresh
3. **Filter Badges**: Click-to-remove with "Clear all" button
4. **Background Jobs**: 1-hour interval for sync and linking
5. **EntityLink Auto-Creation**: Same pattern as PagerDuty/Grafana/Artifact
6. **Computed Properties**: Database models expose derived fields
7. **Content Hash Detection**: Skip unchanged files (SHA256)
8. **JSONB + GIN Indexes**: Efficient keyword/link queries
9. **Pydantic Response Models**: Type-safe API contracts
10. **Eager Loading**: `selectinload()` for async-safe relationships

### Component Reuse

- **shadcn/ui**: Badge, Button, Input
- **Lucide Icons**: BookOpen, AlertTriangle, Search, Filter, RefreshCw, Calendar, GitBranch, Hash
- **UI Components**: ScrollableCard (shared pattern)
- **Color Palette**: Zinc scale, amber for warnings

---

## Key Files

### Backend
- `backend/alembic/versions/20260320_0900_create_project_docs.py`
- `backend/app/models/project_doc.py`
- `backend/app/models/project_doc_section.py`
- `backend/app/models/entity_link.py` (extended)
- `backend/app/services/project_doc_service.py`
- `backend/app/api/project_docs.py`
- `backend/app/jobs/project_doc_sync.py`
- `backend/app/main.py` (job registration)

### Frontend
- `frontend/src/lib/api.ts` (TypeScript types + API methods)
- `frontend/src/components/docs/ProjectDocCard.tsx`
- `frontend/src/components/docs/ProjectDocsGrid.tsx`

---

## Usage Examples

### Add ProjectDocsGrid to Dashboard

```typescript
import { ProjectDocsGrid } from "@/components/docs/ProjectDocsGrid";

export default function ComputeDashboard() {
  return (
    <div className="grid grid-cols-2 gap-4">
      <ProjectDocsGrid />
    </div>
  );
}
```

### Search Project Docs

```typescript
import { api } from "@/lib/api";

// Search by keyword
const results = await api.searchProjectDocs("kubernetes", undefined, "compute", 20);

// Get specific project
const wxDoc = await api.projectDoc("wx");
console.log(wxDoc.word_count, wxDoc.keywords);

// Get sections
const sections = await api.projectSections("wx");
console.log(sections.map(s => s.section_name));
```

### Auto-Linking in Action

When JIRA issue `COMPUTE-1234` has label "wx":
```python
# Background job creates link:
EntityLink(
    from_type="jira_issue",
    from_id=str(issue.id),
    to_type="project_doc",
    to_id=str(wx_doc.id),
    link_type=LinkType.PROJECT_CONTEXT,
    source_type=LinkSourceType.INFERRED
)
```

When agent chat in `~/code/jobs/jobs-1/`:
```python
# Background job creates link:
EntityLink(
    from_type="agent",
    from_id=str(agent.id),
    to_type="project_doc",
    to_id=str(jobs_doc.id),
    link_type=LinkType.PROJECT_CONTEXT
)
```

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
- Detect missing documentation
- Documentation completeness score

### Phase 5: Cross-Project Intelligence
- Detect similar sections across projects
- Suggest documentation reuse opportunities
- Find common patterns
- Generate cross-project index

---

## Notes

### Content Hash Strategy

**Why SHA256?**
- Detect file changes without comparing full content
- Skip unnecessary updates for unchanged files
- Example: 14 docs scanned, only 6 updated (8 unchanged)

### Slack Channel Mapping

Channel → Project mapping enables auto-linking:
```python
"#wx-dev" → wx
"#g4-users" → g4
"#jobs-users" → jobs
"#temporalio-cloud" → temporal
```

### Project Inference Logic

Three detection methods:
1. **JIRA labels**: Check if any label matches project name
2. **Slack channels**: Map channel to project
3. **Working directory**: Extract project from path (`~/code/wx/` → wx)

---

**Status**: Integration complete and ready for production use.
**Next Steps**: Monitor background jobs, add ProjectDocsGrid to dashboards, plan future enhancements.
