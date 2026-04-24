# Slack Threads Integration Implementation Plan

**Created**: 2026-03-20
**Integration**: Slack Thread Context Parser
**Priority**: HIGH (Phase 3 - Medium-Value Integrations)
**Complexity**: Medium-High
**Impact**: High — Incident response and cross-reference intelligence

---

## Overview

Auto-parse Slack thread references from JIRA tickets and other contexts, fetch thread content, detect cross-references (PagerDuty, JIRA, MRs), generate summaries, and link to work contexts.

**Key Advantages**:
- Transforms Slack discussions into first-class linked artifacts
- Automatic cross-reference detection (PagerDuty, JIRA, GitLab MRs)
- Incident escalation detection
- Surrounding context fetching (±24h for incidents)
- Foundation for proactive warning monitoring (Phase 4)

---

## Architecture

### Data Flow

```
JIRA Ticket/Agent Chat (contains Slack link)
    ↓
SlackThreadService.extract_slack_links()
    ↓
Parse channel_id, thread_ts from URL
    ↓
SlackThreadService.fetch_thread() (via Slack API)
    ↓
Fetch messages, detect cross-references
    ↓
SlackThreadService.generate_summary() (via Claude API)
    ↓
Database (slack_threads table)
    ↓
Create entity links to JIRA/Agent
    ↓
API Endpoints (/api/slack/threads/*)
    ↓
React Components (SlackThreadCard, ThreadSummary)
```

### URL Detection Pattern

```regex
https://[a-z-]+\.slack\.com/archives/([A-Z0-9]+)/p(\d+)(?:\?thread_ts=(\d+\.\d+))?
```

**Examples**:
- `https://planet-labs.slack.com/archives/C03ABC123/p1709654321123456`
- `https://planet-labs.slack.com/archives/C03ABC123/p1709654321123456?thread_ts=1709654321.123456`

---

## Database Schema

### Table: slack_threads

```sql
CREATE TABLE slack_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source information
    channel_id VARCHAR(50) NOT NULL,
    channel_name VARCHAR(200),
    thread_ts VARCHAR(50) NOT NULL,
    permalink TEXT NOT NULL,
    
    -- Metadata
    participant_count INTEGER,
    message_count INTEGER,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    duration_hours FLOAT,
    
    -- Summary
    summary_id UUID REFERENCES summaries(id),
    title TEXT,
    summary_text TEXT,
    
    -- Context flags
    is_incident BOOLEAN DEFAULT FALSE,
    severity VARCHAR(10),
    incident_type VARCHAR(100),
    surrounding_context_fetched BOOLEAN DEFAULT FALSE,
    
    -- Cross-references (extracted from messages)
    jira_keys JSONB,  -- ["COMPUTE-1234", ...]
    pagerduty_incident_ids JSONB,  -- ["PD-ABC123", ...]
    gitlab_mr_refs JSONB,  -- ["wx/wx!123", ...]
    cross_channel_refs JSONB,  -- ["#compute-platform", ...]
    
    -- Raw data
    messages JSONB,  -- Full message list
    participants JSONB,  -- User list
    reactions JSONB,  -- Reaction summary
    
    -- Tracking
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(channel_id, thread_ts)
);

-- Indexes
CREATE INDEX idx_slack_threads_channel ON slack_threads(channel_id);
CREATE INDEX idx_slack_threads_incident ON slack_threads(is_incident) WHERE is_incident = TRUE;
CREATE INDEX idx_slack_threads_summary ON slack_threads(summary_id);
CREATE INDEX idx_slack_threads_start ON slack_threads(start_time DESC);
CREATE INDEX idx_slack_threads_jira_keys ON slack_threads USING GIN(jira_keys);
CREATE INDEX idx_slack_threads_pd_incidents ON slack_threads USING GIN(pagerduty_incident_ids);

-- Unique constraint
CREATE UNIQUE INDEX uq_slack_thread ON slack_threads(channel_id, thread_ts);
```

### Extended: entity_links

Add link types:
```python
# Slack thread enrichment
DISCUSSED_IN_SLACK = "discussed_in_slack"  # JIRA/PD/MR → Slack thread
REFERENCES_SLACK = "references_slack"      # Any entity → Slack thread
ESCALATED_FROM = "escalated_from"          # Incident → originating Slack thread
```

---

## Implementation Plan (6 Days)

### Day 1: Database Schema and Models ✅

**Goal**: Create slack_threads table and SlackThread model with computed properties

**Files**:
- `backend/alembic/versions/20260320_1000_create_slack_threads.py`
- `backend/app/models/slack_thread.py`
- `backend/app/models/entity_link.py` (extend LinkType enum)

**Model Computed Properties**:
```python
@property
def is_active(self) -> bool:
    """Check if thread is recent (last 7 days)."""
    
@property
def has_cross_references(self) -> bool:
    """Check if thread contains cross-references."""
    
@property
def duration_display(self) -> str:
    """Human-readable duration (2h 34m, 3d 2h, etc.)."""
    
@property
def reference_count(self) -> int:
    """Total count of all cross-references."""
```

**Acceptance**: Migration runs, model imports, computed properties work

---

### Day 2: Service Layer (Slack API Integration) ✅

**Goal**: SlackThreadService with Slack API integration, URL parsing, reference extraction

**Files**:
- `backend/app/services/slack_thread_service.py`

**Service Methods**:

```python
class SlackThreadService:
    """Service for Slack thread parsing and enrichment."""
    
    SLACK_URL_PATTERN = re.compile(...)
    
    async def extract_slack_links(self, text: str) -> List[Dict]:
        """Extract Slack thread URLs from text.
        
        Returns list of {channel_id, thread_ts, permalink}
        """
        
    async def fetch_thread(
        self,
        channel_id: str,
        thread_ts: str,
        include_surrounding: bool = False
    ) -> Dict:
        """Fetch thread messages from Slack API.
        
        Includes:
        - All messages in thread
        - User info (names, profiles)
        - Reactions
        - File attachments (metadata)
        - ±24h context if include_surrounding=True
        """
        
    async def sync_thread(self, thread_data: Dict) -> SlackThread:
        """Sync thread to database.
        
        - Parse messages
        - Extract cross-references
        - Detect incident patterns
        - Insert/update in DB
        """
        
    async def detect_cross_references(self, messages: List[Dict]) -> Dict:
        """Extract cross-references from messages.
        
        Detects:
        - JIRA keys (COMPUTE-*, WX-*, etc.)
        - PagerDuty incidents (PD-*, URLs)
        - GitLab MRs (!123, MR URLs)
        - Channel refs (#compute-platform)
        """
        
    async def detect_incident_pattern(self, thread: Dict) -> Dict:
        """Detect if thread is incident-related.
        
        Checks for:
        - Severity mentions (SEV1, SEV2)
        - On-call pings (@oncall, @here)
        - PagerDuty incident creation
        - Escalation keywords
        """
        
    async def generate_summary(self, thread: SlackThread) -> Summary:
        """Generate summary using Claude API.
        
        Creates Summary object with:
        - Title extracted from first message
        - Key points, decisions, action items
        - Blockers, owners
        - Links to referenced entities
        """
        
    async def get_thread_by_url(self, slack_url: str) -> Optional[SlackThread]:
        """Get thread from cache by URL."""
        
    async def search_threads(
        self,
        channel_id: str = None,
        is_incident: bool = None,
        has_jira_key: str = None,
        since: datetime = None,
        limit: int = 50
    ) -> List[SlackThread]:
        """Search threads with filters."""
```

**Slack API Integration**:
- Use existing `SlackService` from `slack_service.py`
- Extend with thread-specific methods
- Handle rate limiting (tier-based)
- Cache messages (24h TTL)

**Acceptance**: Can fetch threads via Slack API, extract references, detect incidents

---

### Day 3: API Endpoints ✅

**Goal**: 6 REST endpoints for thread parsing, fetching, searching

**Files**:
- `backend/app/api/slack_threads.py` (new router)
- `backend/app/main.py` (register router)

**Endpoints**:

```python
@router.post("/parse-jira/{jira_key}")
async def parse_jira_ticket(jira_key: str, ...):
    """Scan JIRA ticket for Slack links and parse all threads."""
    
@router.post("/parse-url")
async def parse_slack_url(slack_url: str, ...):
    """Parse a single Slack thread URL."""
    
@router.get("/threads")
async def list_threads(...):
    """List Slack threads with filters."""
    
@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    """Get detailed thread info including summary."""
    
@router.post("/threads/{thread_id}/refresh")
async def refresh_thread(thread_id: str):
    """Re-fetch thread from Slack API."""
    
@router.get("/threads/by-jira/{jira_key}")
async def get_threads_by_jira(jira_key: str):
    """Get all threads linked to a JIRA ticket."""
```

**Acceptance**: All endpoints work, can parse/fetch/search threads

---

### Day 4: Frontend Components ✅

**Goal**: React components for displaying Slack threads and summaries

**Files**:
- `frontend/src/lib/api.ts` (add SlackThread types and methods)
- `frontend/src/components/slack/SlackThreadCard.tsx`
- `frontend/src/components/slack/SlackThreadSummary.tsx`
- `frontend/src/components/slack/JiraSlackThreadsSection.tsx`

**Components**:

1. **SlackThreadCard** - Compact thread display
   - Channel name, thread timestamp
   - Participant count, message count
   - Duration
   - Incident badge if is_incident=true
   - Cross-reference badges (JIRA, PD, MRs)
   - Link to Slack (external)
   
2. **SlackThreadSummary** - Expanded summary view
   - Title
   - Summary text
   - Key points, decisions, action items
   - Blockers, owners
   - Full cross-reference list
   - Message timeline (expandable)
   
3. **JiraSlackThreadsSection** - Threads for a JIRA ticket
   - Shows all Slack threads linked to ticket
   - Parse button to scan for new threads
   - Vertical list layout

**Acceptance**: Components render, show threads, filters work

---

### Day 5: Background Jobs and Auto-Linking ✅

**Goal**: Automated thread parsing and entity linking

**Files**:
- `backend/app/jobs/slack_thread_sync.py`
- `backend/app/jobs/slack_thread_enrichment.py`
- `backend/app/main.py` (register jobs)

**Jobs**:

1. **slack_thread_sync** (every 1 hour)
   - Scan 500 most recent JIRA issues
   - Extract Slack URLs
   - Fetch and sync threads
   - Returns stats: jira_scanned, threads_found, threads_synced
   
2. **slack_thread_enrichment** (every 1 hour)
   - For each thread, create entity links
   - Link to referenced JIRA tickets
   - Link to referenced PagerDuty incidents
   - Link to referenced GitLab MRs
   - Returns stats: threads_processed, links_created

**Link Types Created**:
- `JIRA → DISCUSSED_IN_SLACK → SlackThread` (confidence: 0.95)
- `PagerDuty → DISCUSSED_IN_SLACK → SlackThread` (confidence: 0.90)
- `GitLabMR → DISCUSSED_IN_SLACK → SlackThread` (confidence: 0.85)

**Acceptance**: Jobs run, parse threads, create links

---

### Day 6: Testing and Documentation ✅

**Goal**: Comprehensive testing and documentation

**Testing**:
1. Database migration
2. Service layer (URL parsing, Slack API, cross-reference detection)
3. API endpoints (parse, fetch, search)
4. Frontend components
5. Background jobs

**Documentation**:
- Create `SLACK-THREADS-INTEGRATION-COMPLETE.md`
- Include: architecture, schema, service methods, API examples
- Testing results, usage examples, troubleshooting

**Acceptance**: All tests pass, documentation complete

---

## Success Criteria

- [ ] Can parse Slack URLs from JIRA descriptions
- [ ] Threads fetched from Slack API and stored in DB
- [ ] Cross-references auto-detected (JIRA, PD, MRs)
- [ ] Incident patterns detected (severity, on-call pings)
- [ ] Summaries generated via Claude API
- [ ] Entity links created automatically
- [ ] Frontend displays threads with summaries
- [ ] Background jobs parse and link threads

---

## Timeline

- **Day 1** (3 hours): Database schema, models
- **Day 2** (6 hours): Service layer, Slack API, cross-reference detection
- **Day 3** (4 hours): API endpoints
- **Day 4** (6 hours): Frontend components
- **Day 5** (4 hours): Background jobs, auto-linking
- **Day 6** (3 hours): Testing, documentation

**Total**: ~26 hours (~3-4 days)

---

## Slack API Requirements

### Authentication

Use existing Slack token from `~/.config/slack-token` or environment variable.

### API Methods Needed

```
conversations.history - Fetch channel messages
conversations.replies - Fetch thread replies
users.info - Get user details
reactions.get - Get message reactions
```

### Rate Limits

- Tier 3: 50+ requests per minute
- Use batch requests when possible
- Cache messages for 24 hours

---

## Integration with Existing Code

### Use Existing SlackService

Extend `backend/app/services/slack_service.py` with thread-specific methods:

```python
from app.services.slack_service import SlackService

class SlackThreadService(SlackService):
    """Extends SlackService with thread parsing."""
    
    # New methods for thread parsing
    # Reuse existing Slack API client
```

### Leverage Existing Entity Linking

Use `EntityLinkService` from `backend/app/services/entity_link.py`:

```python
from app.services.entity_link import EntityLinkService

# Create links between Slack threads and other entities
await link_service.create_link(
    from_type="jira_issue",
    from_id=jira_id,
    to_type="slack_thread",
    to_id=thread_id,
    link_type=LinkType.DISCUSSED_IN_SLACK,
    ...
)
```

---

## References

- **Slack Context Parser Spec**: [SLACK-CONTEXT-PARSER-SPEC.md](./SLACK-CONTEXT-PARSER-SPEC.md)
- **Auto-Context Enrichment Spec**: [AUTO-CONTEXT-ENRICHMENT-SPEC.md](./AUTO-CONTEXT-ENRICHMENT-SPEC.md)
- **Pattern Reference**: [PAGERDUTY-INTEGRATION-COMPLETE.md](./PAGERDUTY-INTEGRATION-COMPLETE.md)
- **Existing Slack Code**: `backend/app/services/slack_service.py`, `backend/app/api/slack.py`
