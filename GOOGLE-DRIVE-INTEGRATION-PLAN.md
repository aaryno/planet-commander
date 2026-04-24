# Google Drive Documents Integration - 6-Day Plan

**Created**: March 19, 2026
**Purpose**: Index Google Drive documents for auto-linking to incidents, RFDs, and planning
**Pattern**: Following PagerDuty, Artifact, Grafana Alerts, and Project Docs precedent
**Estimated Duration**: 6 days (Days 1-6)

---

## Overview

Index Google Drive documents from Compute Team shared drive to enable:

1. **Document → JIRA linking** when postmortems/RFDs reference tickets
2. **Incident → postmortem lookup** when similar incidents occur
3. **RFD → ticket association** for architecture planning
4. **Meeting notes → context linking** for decision history
5. **Document search** across all shared drive docs
6. **Content preview** for quick reference

**Value Proposition**: When investigating `PRODISSUE-574`, Commander instantly shows:
- Prior postmortem: "2024-02-28 Jobs elevated failure rate"
- Related RFD: "WX Cost Reporting Implementation"
- Meeting notes discussing similar issues
- On-call log entries
- JIRA tickets mentioned in docs

---

## Google Drive Structure

### Local Path (Google Drive for Desktop)

```
/Users/aaryn/Library/CloudStorage/GoogleDrive-aaryn@planet.com/Shared drives/
└── Compute Team/
    ├── Postmortems/
    │   ├── Completed/
    │   │   ├── 2020-05-14 - Datapipeline Jobs Postmortem.gdoc
    │   │   ├── 2021-05-04 GEE Delivery Acquired Timestamp Bug Postmortem.gdoc
    │   │   └── ...
    │   ├── PRODISSUE-224.gdoc
    │   ├── PRODISSUE-574 Postmortem - 2024-02-28 Jobs elevated failure rate.gdoc
    │   └── ...
    ├── RFCs   Design Docs/
    │   ├── RFC: Activation Orchestration 2.0.gdoc
    │   ├── RFC: Data Collect subsystem refactor.gdoc
    │   ├── RFD: WX Cost Reporting Implementation.gdoc
    │   └── ...
    ├── Meeting Notes/
    │   ├── 2024-01-15 Sprint Planning.gdoc
    │   ├── 2024-02-20 Architecture Review.gdoc
    │   └── ...
    ├── On-Call/
    │   ├── Compute On-Call Log.gdoc
    │   └── ...
    ├── WorkExchange/
    ├── Jobs/
    ├── G4/
    ├── Temporal/
    └── ...
```

### Google Doc File Format

Google Drive for Desktop stores `.gdoc` files as JSON:

```json
{
  "url": "https://docs.google.com/document/d/1a2b3c4d5e6f7g8h9i0j/edit?usp=drivesdk",
  "doc_id": "1a2b3c4d5e6f7g8h9i0j",
  "email": "aaryn@planet.com",
  "resource_id": "document:1a2b3c4d5e6f7g8h9i0j"
}
```

**Metadata from filesystem**:
- Filename: Contains title, date, JIRA key
- Modified time: `os.stat(path).st_mtime`
- Folder path: `/Shared drives/Compute Team/Postmortems/`

---

## Database Schema

### Table: `google_drive_documents`

**Purpose**: Store indexed Google Drive documents with metadata

```sql
CREATE TABLE google_drive_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Google Drive identity
    external_doc_id VARCHAR(100) UNIQUE NOT NULL,  -- From .gdoc file
    doc_type VARCHAR(50) NOT NULL,  -- document, spreadsheet, presentation
    url TEXT NOT NULL,

    -- File information
    title TEXT NOT NULL,
    file_path TEXT NOT NULL,  -- Local path via Drive for Desktop
    filename VARCHAR(500),  -- Original filename with extension

    -- Location
    shared_drive VARCHAR(200),  -- "Compute Team", "Fusion", "Hobbes"
    folder_path TEXT,  -- "Postmortems/Completed", "RFCs   Design Docs"

    -- Classification
    project VARCHAR(100),  -- wx, g4, jobs, temporal, etc.
    document_kind VARCHAR(100),  -- postmortem, rfd, meeting-notes, planning, on-call-log

    -- Metadata
    last_modified_at TIMESTAMPTZ,
    owner VARCHAR(200),  -- From .gdoc email field

    -- Extracted content
    jira_keys TEXT[],  -- Extracted JIRA keys from filename/URL
    keywords TEXT[],  -- Extracted keywords
    tags JSONB,  -- Additional metadata

    -- Timestamps
    last_indexed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_gdrive_docs_external ON google_drive_documents(external_doc_id);
CREATE INDEX idx_gdrive_docs_shared_drive ON google_drive_documents(shared_drive);
CREATE INDEX idx_gdrive_docs_project ON google_drive_documents(project);
CREATE INDEX idx_gdrive_docs_kind ON google_drive_documents(document_kind);
CREATE INDEX idx_gdrive_docs_modified ON google_drive_documents(last_modified_at);
CREATE INDEX idx_gdrive_docs_jira_keys ON google_drive_documents USING GIN(jira_keys);
CREATE INDEX idx_gdrive_docs_keywords ON google_drive_documents USING GIN(keywords);

-- Unique constraint
CREATE UNIQUE CONSTRAINT unique_external_doc_id ON google_drive_documents(external_doc_id);
```

**Computed Properties** (in SQLAlchemy model):
- `is_stale`: last_modified_at > 180 days ago (6 months)
- `is_postmortem`: document_kind == "postmortem"
- `is_rfd`: document_kind == "rfd"
- `has_jira_keys`: len(jira_keys) > 0
- `age_days`: Days since last modification

---

### EntityLink Extensions

Add new link types for Google Drive documents:

```python
class LinkType(str, enum.Enum):
    # ... existing types
    # Google Drive enrichment
    DOCUMENTED_IN_GDRIVE = "documented_in_gdrive"  # Entity documented in Google Doc
    POSTMORTEM_FOR = "postmortem_for"  # Postmortem for incident/issue
    RFD_FOR = "rfd_for"  # RFD/RFC for project/feature
    MEETING_NOTES_FOR = "meeting_notes_for"  # Meeting notes about topic
```

**Examples**:
- JIRA `PRODISSUE-574` → POSTMORTEM_FOR → "2024-02-28 Jobs elevated failure rate"
- JIRA `COMPUTE-1234` (label: "wx") → RFD_FOR → "WX Cost Reporting Implementation"
- Agent chat about "temporal migration" → MEETING_NOTES_FOR → "2024-01-15 Temporal Planning"

---

## Implementation Plan

### Day 1: Database Schema & Models (Tuesday)

**Goal**: Create tables and SQLAlchemy models

**Tasks**:
- [ ] Create Alembic migration `20260320_1000_create_google_drive_documents.py`
- [ ] Create `app/models/google_drive_document.py`
- [ ] Extend `app/models/entity_link.py` with new link types
- [ ] Run migration and verify schema

**Migration**:
```python
def upgrade() -> None:
    op.create_table('google_drive_documents', ...)

    # Extend LinkType enum
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'documented_in_gdrive'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'postmortem_for'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'rfd_for'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'meeting_notes_for'")
```

**Models**:
```python
class GoogleDriveDocument(Base):
    __tablename__ = "google_drive_documents"

    @property
    def is_stale(self) -> bool:
        """Check if >180 days since last modification."""
        if not self.last_modified_at:
            return False
        days_ago = (datetime.utcnow() - self.last_modified_at).days
        return days_ago > 180

    @property
    def is_postmortem(self) -> bool:
        return self.document_kind == "postmortem"

    @property
    def is_rfd(self) -> bool:
        return self.document_kind in ("rfd", "rfc")

    @property
    def has_jira_keys(self) -> bool:
        return bool(self.jira_keys)

    @property
    def age_days(self) -> int:
        """Days since last modification."""
        if not self.last_modified_at:
            return -1
        return (datetime.utcnow() - self.last_modified_at).days
```

**Success Criteria**:
- Migration runs successfully
- Models import without errors
- Can create test GoogleDriveDocument records

**Estimated Time**: 2-3 hours

---

### Day 2: Service Layer (Wednesday)

**Goal**: Parse .gdoc files and index documents

**Tasks**:
- [ ] Create `app/services/google_drive_service.py`
- [ ] Implement `scan_google_drive()` — Scan shared drives
- [ ] Implement `parse_gdoc_file()` — Extract metadata from .gdoc JSON
- [ ] Implement `infer_document_metadata()` — Classify doc type, project, extract JIRA keys
- [ ] Implement `search_documents()` — Full-text search
- [ ] Write unit tests

**Service Methods**:

```python
class GoogleDriveService:
    """Service for indexing Google Drive documents."""

    GDRIVE_BASE = Path.home() / "Library" / "CloudStorage"
    COMPUTE_TEAM = "GoogleDrive-aaryn@planet.com/Shared drives/Compute Team"

    # Document kind patterns
    POSTMORTEM_PATTERNS = ["postmortem", "post-mortem", "prodissue-", "incident"]
    RFD_PATTERNS = ["rfd:", "rfc:", "adr:"]
    MEETING_NOTES_PATTERNS = ["meeting notes", "sprint planning", "retrospective"]

    # JIRA key pattern
    JIRA_KEY_PATTERN = re.compile(r"\b(COMPUTE|PRODISSUE|WX|JOBS|G4|TEMPORAL)-\d+\b", re.IGNORECASE)

    async def scan_google_drive(self) -> Dict:
        """Scan Google Drive shared drives for .gdoc files.

        Returns:
            Dict with scan statistics
        """

    def parse_gdoc_file(self, file_path: Path) -> Dict:
        """Parse .gdoc JSON file.

        Returns:
            {
                "external_doc_id": "1a2b3c4d5e6f7g8h9i0j",
                "url": "https://docs.google.com/document/d/...",
                "doc_type": "document",
                "owner": "aaryn@planet.com"
            }
        """

    def infer_document_metadata(self, file_path: Path, gdoc_data: Dict) -> Dict:
        """Infer metadata from file path and name.

        Returns:
            {
                "title": "PRODISSUE-574 Postmortem - 2024-02-28 Jobs elevated failure rate",
                "shared_drive": "Compute Team",
                "folder_path": "Postmortems",
                "document_kind": "postmortem",
                "project": "jobs",
                "jira_keys": ["PRODISSUE-574"],
                "keywords": ["jobs", "failure", "rate"]
            }
        """

    async def update_document(self, file_path: Path) -> str:
        """Update or create document from file.

        Returns:
            "new", "updated", or "unchanged"
        """

    async def search_documents(
        self,
        query: str,
        shared_drive: Optional[str] = None,
        document_kind: Optional[str] = None,
        project: Optional[str] = None,
        limit: int = 20
    ) -> List[GoogleDriveDocument]:
        """Search documents by keywords/content."""
```

**Metadata Inference Logic**:

```python
def infer_document_metadata(self, file_path: Path, gdoc_data: Dict) -> Dict:
    """Infer metadata from file path and name."""

    # Extract from path
    parts = file_path.parts
    shared_drive_idx = parts.index("Shared drives") if "Shared drives" in parts else -1

    if shared_drive_idx >= 0:
        shared_drive = parts[shared_drive_idx + 1]  # "Compute Team"
        folder_path = "/".join(parts[shared_drive_idx + 2:-1])  # "Postmortems/Completed"

    # Extract from filename
    filename = file_path.stem  # Remove .gdoc extension
    filename_lower = filename.lower()

    # Determine document kind
    document_kind = None
    if any(p in filename_lower for p in self.POSTMORTEM_PATTERNS):
        document_kind = "postmortem"
    elif any(p in filename_lower for p in self.RFD_PATTERNS):
        document_kind = "rfd"
    elif any(p in filename_lower for p in self.MEETING_NOTES_PATTERNS):
        document_kind = "meeting-notes"
    elif "on-call" in filename_lower or "oncall" in filename_lower:
        document_kind = "on-call-log"

    # Extract JIRA keys
    jira_keys = list(set(self.JIRA_KEY_PATTERN.findall(filename)))

    # Infer project from folder or JIRA keys
    project = None
    if "WorkExchange" in folder_path or "wx" in filename_lower:
        project = "wx"
    elif "Jobs" in folder_path or "jobs" in filename_lower:
        project = "jobs"
    elif "G4" in folder_path or "g4" in filename_lower:
        project = "g4"
    elif "Temporal" in folder_path or "temporal" in filename_lower:
        project = "temporal"

    # Extract keywords
    keywords = []
    # Common tech terms from filename
    for word in filename_lower.split():
        if word in ["kubernetes", "postgres", "redis", "api", "database", "incident"]:
            keywords.append(word)

    return {
        "title": filename,
        "shared_drive": shared_drive,
        "folder_path": folder_path,
        "document_kind": document_kind,
        "project": project,
        "jira_keys": jira_keys,
        "keywords": keywords
    }
```

**Success Criteria**:
- Can scan Compute Team shared drive
- Can parse .gdoc JSON files
- Can extract JIRA keys from filenames
- Can infer document type from path/filename
- Can search across all docs

**Estimated Time**: 4-5 hours

---

### Day 3: API Endpoints (Thursday)

**Goal**: REST API for Google Drive documents

**Tasks**:
- [ ] Create `app/api/google_drive.py`
- [ ] Implement 6 endpoints (list, get, search, by-jira, scan, postmortems)
- [ ] Add Pydantic response models
- [ ] Register router in `app/main.py`
- [ ] Test all endpoints

**API Endpoints**:

```python
@router.get("", response_model=List[GoogleDriveDocResponse])
async def list_documents(
    shared_drive: Optional[str] = None,
    document_kind: Optional[str] = None,
    project: Optional[str] = None,
    stale_only: bool = False,
    limit: int = Query(50, le=100),
):
    """List all Google Drive documents."""

@router.get("/search", response_model=List[GoogleDriveDocResponse])
async def search_documents(
    query: str,
    shared_drive: Optional[str] = None,
    document_kind: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = Query(20, le=100),
):
    """Search Google Drive documents."""

@router.get("/by-jira/{jira_key}", response_model=List[GoogleDriveDocResponse])
async def get_documents_by_jira(jira_key: str):
    """Get documents mentioning JIRA key."""

@router.get("/postmortems", response_model=List[GoogleDriveDocResponse])
async def list_postmortems(
    project: Optional[str] = None,
    limit: int = Query(50, le=100),
):
    """List all postmortems."""

@router.get("/{doc_id}", response_model=GoogleDriveDocResponse])
async def get_document(doc_id: str):
    """Get document by external_doc_id."""

@router.post("/scan", response_model=ScanResponse)
async def scan_google_drive():
    """Trigger Google Drive scan."""
```

**Pydantic Models**:
```python
class GoogleDriveDocResponse(BaseModel):
    id: str
    external_doc_id: str
    doc_type: str
    url: str
    title: str
    file_path: str
    shared_drive: str
    folder_path: str
    project: Optional[str]
    document_kind: Optional[str]
    last_modified_at: Optional[datetime]
    owner: Optional[str]
    jira_keys: List[str]
    keywords: List[str]
    is_stale: bool
    is_postmortem: bool
    is_rfd: bool
    has_jira_keys: bool
    age_days: int
    last_indexed_at: datetime

class ScanResponse(BaseModel):
    total_scanned: int
    new_docs: int
    updated_docs: int
    unchanged_docs: int
    error_count: int
    note: Optional[str]
```

**Success Criteria**:
- All 6 endpoints functional
- Can list/search/filter documents
- By-JIRA endpoint returns docs with key
- Scan endpoint triggers indexing

**Estimated Time**: 3-4 hours

---

### Day 4: Frontend Components (Friday)

**Goal**: UI components for Google Drive document display

**Tasks**:
- [ ] Add TypeScript types to `frontend/src/lib/api.ts`
- [ ] Create `GoogleDriveDocCard` component
- [ ] Create `PostmortemsSection` component
- [ ] Create `GoogleDriveDocsGrid` component
- [ ] Test TypeScript compilation and Next.js build

**TypeScript Interface**:
```typescript
export interface GoogleDriveDoc {
  id: string;
  external_doc_id: string;
  doc_type: string;
  url: string;
  title: string;
  file_path: string;
  shared_drive: string;
  folder_path: string;
  project: string | null;
  document_kind: string | null;
  last_modified_at: string | null;
  owner: string | null;
  jira_keys: string[];
  keywords: string[];
  is_stale: boolean;
  is_postmortem: boolean;
  is_rfd: boolean;
  has_jira_keys: boolean;
  age_days: number;
  last_indexed_at: string;
}

// API methods
export const api = {
  // ... existing methods
  googleDriveDocs: (sharedDrive?, documentKind?, project?, staleOnly = false, limit = 50) =>
    fetchApi<GoogleDriveDoc[]>(`/google-drive?${params}`),

  searchGoogleDriveDocs: (query, sharedDrive?, documentKind?, project?, limit = 20) =>
    fetchApi<GoogleDriveDoc[]>(`/google-drive/search?${params}`),

  googleDriveDocsByJira: (jiraKey: string) =>
    fetchApi<GoogleDriveDoc[]>(`/google-drive/by-jira/${jiraKey}`),

  postmortems: (project?, limit = 50) =>
    fetchApi<GoogleDriveDoc[]>(`/google-drive/postmortems?${params}`),

  googleDriveDoc: (docId: string) =>
    fetchApi<GoogleDriveDoc>(`/google-drive/${docId}`),

  scanGoogleDrive: () =>
    fetchApi<{...}>("/google-drive/scan", { method: "POST" }),
};
```

**Components**:

```tsx
// GoogleDriveDocCard.tsx - Display single document
interface GoogleDriveDocCardProps {
  doc: GoogleDriveDoc;
}

export function GoogleDriveDocCard({ doc }: GoogleDriveDocCardProps) {
  // Show title, type badge, JIRA keys, age, folder
  // Click to open URL in new tab
  // Stale warning if >180 days
  // Document kind badge (Postmortem, RFD, Meeting Notes)
}
```

```tsx
// PostmortemsSection.tsx - Dedicated postmortems view
export function PostmortemsSection({ project }: { project?: string }) {
  const { data: docs, loading, error, refresh } = usePoll(
    () => api.postmortems(project),
    600_000 // 10 min
  );

  return (
    <ScrollableCard
      title="Postmortems"
      icon={<AlertTriangle />}
      menuItems={[{ label: "Refresh", onClick: refresh }]}
    >
      {docs?.map(doc => (
        <GoogleDriveDocCard key={doc.id} doc={doc} />
      ))}
    </ScrollableCard>
  );
}
```

```tsx
// GoogleDriveDocsGrid.tsx - Full search/filter view
export function GoogleDriveDocsGrid() {
  const [searchQuery, setSearchQuery] = useState("");
  const [driveFilter, setDriveFilter] = useState("");
  const [kindFilter, setKindFilter] = useState("");
  const [projectFilter, setProjectFilter] = useState("");

  // ScrollableCard with search, filters, grid of docs
}
```

**Success Criteria**:
- Can display docs with all metadata
- Postmortems section shows only postmortems
- JIRA keys displayed as clickable badges
- TypeScript compiles without errors

**Estimated Time**: 4-5 hours

---

### Day 5: Background Jobs & Auto-Linking (Monday)

**Goal**: Automated sync and intelligent linking

**Tasks**:
- [ ] Create `app/jobs/google_drive_sync.py`
- [ ] Implement `sync_google_drive_documents()` background job
- [ ] Implement `link_documents_to_entities()` auto-linking
- [ ] Register jobs in `app/main.py`
- [ ] Test background job execution

**Background Jobs**:

```python
# app/jobs/google_drive_sync.py

async def sync_google_drive_documents() -> Dict:
    """Sync Google Drive docs from shared drives.

    Runs every 6 hours (less frequent than other syncs).
    Scans .gdoc files in Google Drive for Desktop mount.
    """

async def link_documents_to_entities() -> Dict:
    """Auto-link Google Drive docs to work contexts.

    Runs every 6 hours.

    Links created:
    1. JIRA issue (PRODISSUE-574) → POSTMORTEM_FOR → Postmortem doc
    2. JIRA issue (COMPUTE-1234) → RFD_FOR → RFD doc
    3. Agent chat (mentions doc title) → DOCUMENTED_IN_GDRIVE → Doc
    4. Artifact (same date as postmortem) → POSTMORTEM_FOR → Postmortem
    """
```

**Auto-Linking Logic**:

1. **JIRA → Postmortem** (by JIRA key in filename):
   ```python
   if "PRODISSUE-574" in doc.jira_keys and doc.is_postmortem:
       link = EntityLink(
           from_type="jira_issue",
           from_id=str(issue.id),
           to_type="google_drive_document",
           to_id=str(doc.id),
           link_type=LinkType.POSTMORTEM_FOR,
           ...
       )
   ```

2. **JIRA → RFD** (by project + RFD type):
   ```python
   if issue.project == doc.project and doc.is_rfd:
       link = EntityLink(
           from_type="jira_issue",
           to_type="google_drive_document",
           link_type=LinkType.RFD_FOR,
           ...
       )
   ```

3. **Agent → Document** (by title mention):
   ```python
   if doc.title.lower() in agent_chat_content.lower():
       link = EntityLink(
           from_type="agent",
           to_type="google_drive_document",
           link_type=LinkType.DOCUMENTED_IN_GDRIVE,
           ...
       )
   ```

**Job Registration**:
```python
# app/main.py

job_service.add_interval_job(
    sync_google_drive_documents,
    job_id="google_drive_sync",
    hours=6  # Less frequent than other syncs
)

job_service.add_interval_job(
    link_documents_to_entities,
    job_id="google_drive_linking",
    hours=6
)
```

**Success Criteria**:
- Background jobs run without errors
- Docs sync every 6 hours
- Auto-linking creates appropriate entity_links
- Can query doc context from any entity

**Estimated Time**: 4-5 hours

---

### Day 6: Testing & Documentation (Tuesday)

**Goal**: Comprehensive testing and documentation

**Tasks**:
- [ ] Test all API endpoints with real data
- [ ] Test document scanning (Compute Team shared drive)
- [ ] Test auto-linking to JIRA issues
- [ ] Test frontend components
- [ ] Create `GOOGLE-DRIVE-INTEGRATION-COMPLETE.md`
- [ ] Update `GOOGLE-DRIVE-INTEGRATION-PLAN.md` status

**Testing Checklist**:
- [ ] Scan finds 100+ postmortems in Compute Team drive
- [ ] JIRA key extraction works for PRODISSUE-, COMPUTE- prefixes
- [ ] Document kind inference correct (postmortem, rfd, meeting-notes)
- [ ] Search by keyword finds relevant docs
- [ ] By-JIRA endpoint returns correct docs
- [ ] Auto-linking creates POSTMORTEM_FOR links
- [ ] Frontend displays docs with correct metadata
- [ ] Stale warning shows for >180 day old docs

**Documentation**:
- Complete implementation guide
- Database schema details
- API endpoint specifications
- Frontend component usage
- Background job details
- Auto-linking examples

**Success Criteria**:
- All endpoints tested and working
- Documentation complete
- Integration ready for production

**Estimated Time**: 3-4 hours

---

## Success Metrics

### Data Quality
- **All shared drives indexed**: Compute Team, Fusion, Hobbes, etc.
- **Document types recognized**: Postmortem, RFD, Meeting Notes, On-Call Log
- **JIRA keys extracted**: 100+ documents with JIRA references
- **Keywords indexed**: 500+ unique keywords

### Performance
- **< 30 seconds** to scan Compute Team shared drive
- **< 50ms** to query document by ID
- **< 100ms** to search across all docs
- **< 200ms** to get docs by JIRA key

### Integration
- **Auto-linking** to JIRA (by key), agents (by title), artifacts (by date)
- **Entity links** created between docs and work contexts
- **Ready for incident response** (quick postmortem lookup)

---

## Comparison to Previous Integrations

| Feature | PagerDuty | Artifacts | Grafana Alerts | Project Docs | Google Drive |
|---------|-----------|-----------|----------------|--------------|--------------|
| Database tables | 1 | 1 | 2 | 2 | 1 |
| Service layer | ✅ | ✅ | ✅ | ✅ | ✅ |
| API endpoints | 6 | 7 | 6 | 5 | 6 |
| Frontend components | 1 card | 2 cards | 2 cards | 2 cards | 3 cards |
| Background jobs | 1 (30min) | 2 (1h each) | 2 (1h each) | 2 (1h each) | 2 (6h each) |
| Entity linking | ✅ | ✅ | ✅ | ✅ | ✅ |
| Search/filter | ✅ | ✅ | ✅ | ✅ | ✅ |

**Pattern Consistency**: 100% — Following exact same structure

**Key Difference**: 6-hour sync interval (vs 1-hour) because Google Drive docs change less frequently

---

## Files to Create/Modify

### Backend (7 files)
- `backend/alembic/versions/20260320_1000_create_google_drive_documents.py`
- `backend/app/models/google_drive_document.py`
- `backend/app/models/entity_link.py` (extend LinkType)
- `backend/app/services/google_drive_service.py`
- `backend/app/api/google_drive.py`
- `backend/app/jobs/google_drive_sync.py`
- `backend/app/main.py` (register jobs)

### Frontend (4 files)
- `frontend/src/lib/api.ts` (types + methods)
- `frontend/src/components/gdrive/GoogleDriveDocCard.tsx`
- `frontend/src/components/gdrive/PostmortemsSection.tsx`
- `frontend/src/components/gdrive/GoogleDriveDocsGrid.tsx`

**Total**: ~11 files, ~1,200 lines of code

---

## Next Integration After This

After Google Drive, the next high-value integration from AUTO-CONTEXT-ENRICHMENT-SPEC is:

**Slack Context Parser** — Parse Slack messages for cross-references (JIRA keys, PagerDuty incidents, alert names, document links) and auto-create entity links.

---

## Notes

- **Google Drive for Desktop required**: Integration depends on local mount
- **Environment variable**: May need `$COMPUTE_TEAM` env var for path
- **.gdoc format**: JSON files with `doc_id` and `url` fields
- **Metadata from filename**: Rich information in filenames (dates, JIRA keys, projects)
- **Read-only**: This integration only reads docs, doesn't modify them
- **Privacy**: Only indexes Compute Team shared drive (team-accessible docs)

---

**Status**: Ready to implement
**Next Step**: Day 1 - Database Schema & Models
