# Slack Context Parser - Technical Specification

**Created**: 2026-03-18
**Purpose**: Automatically parse, summarize, and contextualize Slack threads referenced in JIRA tickets
**Integration**: Planet Commander work context resolution

---

## Overview

When a Slack link appears in a JIRA ticket, Planet Commander should automatically:
1. Parse the Slack thread
2. Fetch surrounding context (±24 hours)
3. Follow cross-references (PagerDuty, PRODISSUE, other channels)
4. Generate a structured summary
5. Link the Slack discussion into the work context

This transforms Slack discussions from external references into first-class linked artifacts.

**Extension — Proactive Warning Monitoring**:
Planet Commander can also **monitor warning channels in real-time** (like `#compute-platform-warn`) to:
1. Detect escalation-prone warnings before they become critical alerts
2. Pre-assemble incident context and mitigation plans
3. Activate plans immediately when warnings escalate to `#compute-platform`
4. Reduce incident response time by 50%+

See [PROACTIVE-INCIDENT-RESPONSE-SPEC.md](./PROACTIVE-INCIDENT-RESPONSE-SPEC.md) for full details.

---

## Problem Statement

**Current state**:
- JIRA tickets contain Slack URLs like `https://planet-labs.slack.com/archives/C123ABC/p1234567890123456`
- These are opaque links that require manual click-through
- Context around the discussion is lost
- Cross-references to incidents, other channels, or PagerDuty are not surfaced
- No automatic summarization or linkage into Commander

**Desired state**:
- Slack threads are automatically detected in JIRA tickets
- Threads are parsed, summarized, and stored as linked artifacts
- Surrounding context (±24 hours) is included when relevant
- Cross-references are automatically followed and summarized
- Slack discussions become searchable, auditable work artifacts

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────┐
│                   JIRA Ticket                       │
│  (contains Slack link in description/comments)      │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│          SlackLinkDetectorService                   │
│  - Scan JIRA descriptions and comments              │
│  - Extract Slack URLs                               │
│  - Parse channel ID, thread timestamp               │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│         SlackContextFetcherService                  │
│  - Fetch primary thread messages                    │
│  - Fetch ±24hr context if configured                │
│  - Detect cross-references (PD, other channels)     │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│      SlackIntelligenceService (Advanced)            │
│  - Detect PagerDuty incident links                  │
│  - Detect PRODISSUE references                      │
│  - Detect cross-channel references                  │
│  - Follow references to other channels              │
│  - Build comprehensive context graph                │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│         SlackSummarizerService                      │
│  - Generate structured summary                      │
│  - Extract key decisions, blockers, owners          │
│  - Format as Planet Commander Summary artifact      │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│            Summary + EntityLink                     │
│  - Store as Summary artifact                        │
│  - Link to JIRA issue via EntityLink                │
│  - Include in work context                          │
└─────────────────────────────────────────────────────┘
```

---

## Slack Link Detection

### URL Patterns

Slack thread URLs follow these patterns:

```
# Thread link (most common)
https://planet-labs.slack.com/archives/{CHANNEL_ID}/p{THREAD_TS}

# Message in thread
https://planet-labs.slack.com/archives/{CHANNEL_ID}/p{THREAD_TS}?thread_ts={PARENT_TS}

# Example
https://planet-labs.slack.com/archives/C03ABC123/p1709654321123456
```

### Extraction Logic

```python
import re

SLACK_URL_PATTERN = re.compile(
    r'https://[a-z-]+\.slack\.com/archives/([A-Z0-9]+)/p(\d+)(?:\?thread_ts=(\d+\.\d+))?'
)

def extract_slack_links(text: str) -> List[SlackThreadRef]:
    """Extract Slack thread references from text."""
    matches = SLACK_URL_PATTERN.findall(text)
    return [
        SlackThreadRef(
            channel_id=match[0],
            thread_ts=format_timestamp(match[1]),
            parent_ts=match[2] if match[2] else None
        )
        for match in matches
    ]

def format_timestamp(slack_ts: str) -> str:
    """Convert Slack permalink timestamp to thread_ts format.

    Slack permalinks use format: p1234567890123456 (unix timestamp in microseconds)
    thread_ts format: 1234567890.123456 (unix timestamp with microseconds)
    """
    # Remove 'p' prefix, insert decimal point before last 6 digits
    ts = slack_ts.lstrip('p')
    return f"{ts[:-6]}.{ts[-6:]}"
```

### Detection Triggers

Slack link detection should run:
1. **On JIRA sync** - When tickets are fetched/updated
2. **On demand** - Via API endpoint or UI action
3. **Background job** - Periodic scan of active tickets
4. **On ticket creation** - Real-time detection for new tickets

---

## Context Fetching Rules

### Primary Thread

Always fetch:
- Thread parent message
- All replies in thread
- Reactions to messages
- User mentions
- File attachments (metadata only)

### Surrounding Context (±24 hours)

Fetch messages in same channel within 24 hours if:
- Thread mentions PagerDuty incident
- Thread mentions PRODISSUE
- Thread contains severity indicator (SEV1, SEV2, etc.)
- Thread originated from an on-call alert
- Manual override flag is set

**Rationale**: Incidents often have discussion spread across multiple threads in the same timeframe. Capturing this provides critical context.

### Rate Limiting

- Use Slack API tier-based rate limiting
- Cache fetched messages (24 hour TTL)
- Batch requests when possible
- Respect Slack API quotas

---

## Cross-Reference Intelligence

### Patterns to Detect

#### 1. PagerDuty Incidents

```regex
# PagerDuty URLs
https://planet-labs\.pagerduty\.com/incidents/[A-Z0-9]+

# PagerDuty incident IDs in text
PD-[A-Z0-9]{6,}
incident #[A-Z0-9]{6,}
```

**Actions**:
- Extract incident ID
- Fetch incident details via PagerDuty API
- Include incident timeline in context
- Link related PagerDuty alerts

#### 2. PRODISSUE References

```regex
# PRODISSUE ticket references
PRODISSUE-\d+
prodissue-\d+

# Google Drive PRODISSUE links
https://docs\.google\.com/document/d/[a-zA-Z0-9_-]+
```

**Actions**:
- Extract PRODISSUE ticket number
- Fetch from incident tracking system
- Include incident summary
- Link postmortem if available

#### 3. Cross-Channel References

```regex
# Slack channel mentions
<#([A-Z0-9]+)\|([a-z-]+)>

# Slack message links from other channels
https://planet-labs\.slack\.com/archives/([A-Z0-9]+)/p\d+
```

**Actions**:
- Follow references to other channels
- Fetch referenced messages
- Build relationship graph
- Detect if cross-posted from alerts channel

#### 4. JIRA Ticket References

```regex
# JIRA tickets
[A-Z]+-\d+

# JIRA URLs
https://hello\.planet\.com/browse/[A-Z]+-\d+
```

**Actions**:
- Extract ticket keys
- Link to JIRA issues
- Check if already in same work context
- Suggest EntityLink if not linked

#### 5. GitLab References

```regex
# GitLab MR URLs
https://hello\.planet\.com/code/[a-z0-9-]+/[a-z0-9-]+/-/merge_requests/\d+

# Commit SHAs
\b[0-9a-f]{7,40}\b
```

**Actions**:
- Extract MR numbers and repos
- Link to merge requests
- Include in work context

---

## Slack Intelligence Service (Advanced Skill)

### Purpose

The `SlackIntelligenceService` is an advanced analyzer that goes beyond simple thread fetching. It builds a comprehensive understanding of Slack discussions by:

1. **Following the conversation graph** across channels
2. **Detecting incident patterns** (PagerDuty, alerts, escalations)
3. **Identifying key participants** and their roles
4. **Extracting decisions and action items**
5. **Building temporal context** (what happened before/after)

### Detection Rules

#### Rule 1: Alert Channel Cross-Posts

```python
def detect_alert_crosspost(message: SlackMessage) -> Optional[CrossPostRef]:
    """Detect if message was cross-posted from an alert channel."""
    # Check for bot users that cross-post alerts
    ALERT_BOTS = ['PagerDuty', 'Grafana', 'Datadog', 'OpsGenie']

    if message.bot_id and message.username in ALERT_BOTS:
        # This is likely a cross-posted alert
        return CrossPostRef(
            source_channel='alerts',
            alert_type=message.username,
            severity=extract_severity(message.text)
        )

    # Check for forwarded messages
    if 'Originally posted in' in message.text:
        channel_ref = extract_channel_from_text(message.text)
        return CrossPostRef(
            source_channel=channel_ref,
            alert_type='manual_crosspost'
        )

    return None
```

#### Rule 2: Incident Escalation Detection

```python
def detect_escalation_pattern(thread: SlackThread) -> Optional[EscalationContext]:
    """Detect if thread shows an incident escalation pattern."""

    escalation_signals = []

    # Check for severity mentions
    if any(re.search(r'SEV[1-3]|severity [1-3]', msg.text, re.I) for msg in thread.messages):
        escalation_signals.append('severity_mentioned')

    # Check for on-call pings
    if any('@oncall' in msg.text or '@here' in msg.text for msg in thread.messages):
        escalation_signals.append('oncall_paged')

    # Check for PagerDuty incident creation
    if any('pagerduty.com/incidents' in msg.text for msg in thread.messages):
        escalation_signals.append('pd_incident_created')

    # Check for escalation keywords
    escalation_keywords = ['escalate', 'escalating', 'page', 'urgent', 'critical']
    if any(any(kw in msg.text.lower() for kw in escalation_keywords) for msg in thread.messages):
        escalation_signals.append('escalation_keywords')

    if len(escalation_signals) >= 2:
        return EscalationContext(
            signals=escalation_signals,
            likely_incident=True,
            fetch_surrounding_context=True
        )

    return None
```

#### Rule 3: Multi-Channel Investigation

```python
def should_follow_cross_channel(message: SlackMessage, context: AnalysisContext) -> bool:
    """Determine if a cross-channel reference should be followed."""

    # Always follow if it's an incident-related channel
    INCIDENT_CHANNELS = ['compute-platform', 'incidents', 'on-call']
    if message.channel_name in INCIDENT_CHANNELS:
        return True

    # Follow if message contains incident markers
    if context.incident_detected:
        return True

    # Follow if referenced in same timeframe as known incident
    if context.within_incident_window:
        return True

    # Follow if multiple people reference same channel
    if context.channel_reference_count > 2:
        return True

    return False
```

---

## Summary Generation

### Structured Output Format

```typescript
interface SlackThreadSummary {
  id: string;
  title: string;
  kind: "slack_thread" | "slack_incident" | "slack_discussion";

  // Source information
  source: {
    channel_id: string;
    channel_name: string;
    thread_ts: string;
    permalink: string;
    fetched_at: string;
  };

  // Thread metadata
  metadata: {
    participant_count: number;
    message_count: number;
    start_time: string;
    end_time: string;
    duration_hours: number;
  };

  // Extracted content
  content: {
    summary: string;
    key_points: string[];
    decisions: string[];
    action_items: string[];
    blockers: string[];
    owners: string[];
  };

  // Cross-references
  references: {
    jira_tickets: string[];
    pagerduty_incidents: string[];
    prodissues: string[];
    merge_requests: string[];
    other_channels: string[];
  };

  // Context
  context: {
    is_incident: boolean;
    severity?: "SEV1" | "SEV2" | "SEV3" | "SEV4";
    incident_type?: string;
    surrounding_context_included: boolean;
  };

  // Raw messages (for audit trail)
  messages: SlackMessage[];
}
```

### Summary Prompts

Use Claude to generate summaries with specialized prompts:

```typescript
const SLACK_SUMMARY_PROMPT = `
You are analyzing a Slack thread from a Planet Labs engineering channel.

Thread context:
- Channel: {channel_name}
- Participants: {participant_count}
- Duration: {duration}
- Messages: {message_count}

Thread messages:
{messages}

Cross-references found:
{references}

Generate a structured summary with:

1. **Title** (10 words max): Concise description of what was discussed
2. **Summary** (2-3 sentences): High-level overview
3. **Key Points** (bullet list): Main technical points or findings
4. **Decisions** (bullet list): Any decisions made or agreed upon
5. **Action Items** (bullet list): Specific actions assigned to people
6. **Blockers** (bullet list): Any blockers or issues raised
7. **Owners** (list): People who own action items or decisions

If this appears to be an incident response:
- Identify the severity if mentioned
- Summarize the incident timeline
- List mitigation steps taken
- Note if postmortem is needed

Format as JSON matching the SlackThreadSummary interface.
`;
```

---

## Database Schema

### SlackThread Table

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

    -- Summary
    summary_id UUID REFERENCES summaries(id),

    -- Context flags
    is_incident BOOLEAN DEFAULT FALSE,
    severity VARCHAR(10),
    surrounding_context_fetched BOOLEAN DEFAULT FALSE,

    -- Raw data
    messages_json JSONB,
    references_json JSONB,

    -- Tracking
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(channel_id, thread_ts)
);

CREATE INDEX idx_slack_threads_channel ON slack_threads(channel_id);
CREATE INDEX idx_slack_threads_incident ON slack_threads(is_incident) WHERE is_incident = TRUE;
CREATE INDEX idx_slack_threads_summary ON slack_threads(summary_id);
```

---

## API Endpoints

### Parse Slack Links from JIRA

```
POST /api/slack/parse-from-jira/:jira_key
```

**Request**:
```json
{
  "include_surrounding_context": true,
  "follow_cross_references": true
}
```

**Response**:
```json
{
  "jira_key": "COMPUTE-1234",
  "slack_links_found": 3,
  "threads_parsed": [
    {
      "thread_id": "uuid",
      "channel": "compute-platform",
      "summary_id": "uuid",
      "is_incident": true,
      "cross_references": {
        "pagerduty": ["PD-ABC123"],
        "other_threads": 2
      }
    }
  ],
  "entity_links_created": 3
}
```

### Manual Parse Slack URL

```
POST /api/slack/parse-url
```

**Request**:
```json
{
  "slack_url": "https://planet-labs.slack.com/archives/C123/p1234567890",
  "context_id": "optional-uuid",
  "options": {
    "include_surrounding_context": true,
    "follow_cross_references": true
  }
}
```

### Get Thread Summary

```
GET /api/slack/threads/:thread_id
```

**Response**: `SlackThreadSummary` object

---

## Integration with Planet Commander

### Entity Linking

Slack threads should be linked to work contexts via `EntityLink`:

```typescript
// Link Slack thread to JIRA issue
await entityLinkService.createLink({
  from_type: "jira_issue",
  from_id: jiraIssue.id,
  to_type: "slack_thread",
  to_id: slackThread.id,
  link_type: "discussed_in",
  source_type: "agent",
  confidence_score: 0.95
});

// Link Slack thread to work context
await entityLinkService.createLink({
  from_type: "work_context",
  from_id: context.id,
  to_type: "slack_thread",
  to_id: slackThread.id,
  link_type: "references",
  source_type: "inferred"
});
```

### Context Resolution

When resolving a work context, include Slack threads:

```typescript
interface WorkContextResolution {
  // ... existing fields
  slack_threads: SlackThreadSummary[];
  slack_thread_count: number;
}
```

### Audit Integration

Slack threads should inform audits:

**Context Completeness Audit**:
- Check if Slack discussions exist but aren't linked
- Suggest parsing unlinked Slack URLs

**Chat Alignment Audit**:
- Compare Slack discussion to JIRA ticket scope
- Flag misalignments

---

## Background Job Configuration

```yaml
background_jobs:
  slack_link_scanner:
    enabled: true
    schedule_hours: 6
    config:
      scan_active_tickets: true
      scan_recent_tickets_days: 7
      include_surrounding_context: true
      follow_cross_references: true
      batch_size: 50
```

---

## Advanced Skill Interface

### Slack Advanced Skill (~/skills/slack-advanced.md)

```markdown
# Slack Advanced - Intelligent Thread Analysis

**Purpose**: Parse Slack threads with cross-reference intelligence

**When to use**:
- JIRA ticket contains Slack URLs
- Investigating incidents with Slack discussion
- Building work context from chat threads
- Following multi-channel investigations

**Capabilities**:
- Automatic Slack URL detection
- Thread parsing with ±24hr context
- PagerDuty incident correlation
- PRODISSUE reference extraction
- Cross-channel investigation
- Incident pattern detection
- Structured summary generation

**Usage**:
```bash
# Parse Slack links from JIRA ticket
slack-advanced parse-jira COMPUTE-1234

# Parse specific Slack URL with full context
slack-advanced parse-url "https://planet-labs.slack.com/..." --context --cross-refs

# Analyze incident discussion
slack-advanced analyze-incident --channel compute-platform --date 2026-03-17
```

**Configuration**:
See `~/tools/slack/slack-advanced-config.yaml`

**Cross-reference detection**:
- PagerDuty incidents
- PRODISSUE tickets
- Cross-posted alerts
- Multi-channel discussions
- GitLab MRs
- JIRA tickets
```

---

## Implementation Phases

### Phase 1: Basic Detection & Parsing (1 week)

- [ ] Slack URL regex detection
- [ ] Primary thread fetching
- [ ] Basic summary generation
- [ ] Entity linking to JIRA
- [ ] API endpoints

### Phase 2: Context Fetching (1 week)

- [ ] ±24hr context fetching
- [ ] Surrounding message filtering
- [ ] Time-based relevance scoring
- [ ] Context inclusion logic

### Phase 3: Cross-Reference Intelligence (2 weeks)

- [ ] PagerDuty detection and fetching
- [ ] PRODISSUE extraction
- [ ] Cross-channel reference following
- [ ] Multi-channel investigation logic
- [ ] Incident pattern detection

### Phase 4: Advanced Analysis (1 week)

- [ ] Incident severity detection
- [ ] Escalation pattern recognition
- [ ] Decision extraction
- [ ] Action item tracking
- [ ] Owner identification

### Phase 5: UI & Integration (1 week)

- [ ] Context panel Slack thread display
- [ ] Thread summary cards
- [ ] Cross-reference visualization
- [ ] Manual parse controls
- [ ] Background job monitoring

### Phase 6: Proactive Warning Monitoring (6 weeks)

**See**: [PROACTIVE-INCIDENT-RESPONSE-SPEC.md](./PROACTIVE-INCIDENT-RESPONSE-SPEC.md)

- [ ] Real-time monitoring of `#compute-platform-warn` via SSE (1 week)
- [ ] Warning message parsing and classification (1 week)
- [ ] Escalation probability prediction (2 weeks)
  - [ ] Pattern matching (high/medium/low risk)
  - [ ] Historical escalation rate analysis
  - [ ] Time-of-day and context factors
- [ ] Standby context pre-assembly (2 weeks)
  - [ ] Auto-fetch artifacts, alert definitions, runbooks
  - [ ] Generate mitigation plan templates
  - [ ] Create standby work contexts
- [ ] Escalation detection and activation (1 week)
  - [ ] Detect when warning → critical alert
  - [ ] Activate standby context
  - [ ] Notify on-call with pre-assembled plan
- [ ] Learning system (ongoing)
  - [ ] Track escalation accuracy
  - [ ] Collect mitigation plan feedback
  - [ ] Model improvement

**Value**:
- Pre-assemble incident context while still in warning state
- 50% reduction in time-to-mitigation
- On-call gets mitigation plan immediately when alert fires

---

## Success Metrics

**Detection accuracy**:
- 95%+ Slack URL detection rate
- < 5% false positives on URL extraction

**Context quality**:
- 90%+ user satisfaction with summaries
- Cross-references detected in 80%+ of incident threads
- ±24hr context included when relevant

**Integration value**:
- 50%+ reduction in "click to Slack" actions
- Slack discussions visible in 80%+ of JIRA-originated contexts
- Incident context completeness score > 0.8

---

## Security & Privacy

### Access Control

- Respect Slack channel permissions
- Only fetch threads user has access to
- Store channel membership metadata
- Implement row-level security on slack_threads

### Data Retention

- Cache messages for 30 days
- Purge raw messages after summary creation
- Keep summaries indefinitely
- Allow manual purge for sensitive threads

### API Tokens

- Use Slack app with minimal scopes required
- Rotate tokens quarterly
- Store in secure secrets manager
- Audit token usage monthly

---

## Open Questions

1. **Rate limiting**: How to handle large batch scans without hitting Slack API limits?
2. **Private channels**: Should we parse private channels? Access control?
3. **Historical depth**: Should we ever fetch > 24hr context? When?
4. **Update frequency**: How often to re-fetch active threads?
5. **Cost**: Slack API costs for high-volume usage?

---

## References

- **Slack API**: https://api.slack.com/methods
- **PagerDuty API**: https://developer.pagerduty.com/api-reference
- **Planet Commander Spec**: [PLANET-COMMANDER-SPEC.md](./PLANET-COMMANDER-SPEC.md)
- **Proactive Incident Response**: [PROACTIVE-INCIDENT-RESPONSE-SPEC.md](./PROACTIVE-INCIDENT-RESPONSE-SPEC.md)
- **Auto-Context Enrichment**: [AUTO-CONTEXT-ENRICHMENT-SPEC.md](./AUTO-CONTEXT-ENRICHMENT-SPEC.md)
- **Slack Tools**: `~/tools/slack/`
