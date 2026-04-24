# PagerDuty Integration Implementation Plan

**Created**: 2026-03-19
**Integration**: PagerDuty Incidents
**Priority**: HIGH (Phase 2)
**Complexity**: Low
**Impact**: High — Incident context enrichment

---

## Overview

Auto-link PagerDuty incidents to work contexts, fetch incident timelines, and enrich JIRA/Slack/Agent contexts with incident metadata.

**Key Advantages**:
- MCP already configured (`~/.cursor/mcp.json`)
- PagerDuty MCP provides full incident API
- Detection patterns straightforward
- High value for incident response workflows

---

## Architecture

### Data Flow

```
PagerDuty API (via MCP)
    ↓
PagerDutyService
    ↓
Database (pagerduty_incidents)
    ↓
EntityLinkService (auto-link to JIRA/Slack/Agents)
    ↓
API Endpoints
    ↓
React Components (Incident cards, timeline)
```

### Detection Patterns

```regex
# PagerDuty URLs
https://planet-labs\.pagerduty\.com/incidents/([A-Z0-9]+)

# PagerDuty incident IDs in text
PD-[A-Z0-9]{6,}
incident #?[A-Z0-9]{6,}
```

### MCP Functions Available

From `~/.cursor/mcp.json`:
- `mcp_pagerduty-mcp_list_oncalls` — Get on-call contacts
- `mcp_pagerduty-mcp_get_escalation_policy` — Get escalation details
- `mcp_pagerduty-mcp_list_incidents` — Query incidents by status/date/service

---

## Database Schema

### Table: pagerduty_incidents

```sql
CREATE TABLE pagerduty_incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_incident_id VARCHAR(50) UNIQUE NOT NULL,
    incident_number INTEGER,
    title TEXT NOT NULL,
    status VARCHAR(50) NOT NULL,  -- triggered, acknowledged, resolved
    urgency VARCHAR(20),  -- high, low
    priority JSONB,  -- {id, summary, description}
    service_id VARCHAR(50),
    service_name VARCHAR(200),
    escalation_policy_id VARCHAR(50),
    escalation_policy_name VARCHAR(200),
    assigned_to JSONB,  -- [{id, email, name}]
    teams JSONB,  -- [{id, name}]
    triggered_at TIMESTAMPTZ NOT NULL,
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    last_status_change_at TIMESTAMPTZ,
    incident_url TEXT,
    html_url TEXT,
    incident_key VARCHAR(200),
    description TEXT,
    acknowledgements JSONB,  -- [{at, by}]
    assignments JSONB,  -- Full assignment history
    log_entries JSONB,  -- Timeline events
    alerts JSONB,  -- Alert details
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_synced_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_pd_incidents_external ON pagerduty_incidents(external_incident_id);
CREATE INDEX idx_pd_incidents_number ON pagerduty_incidents(incident_number);
CREATE INDEX idx_pd_incidents_status ON pagerduty_incidents(status);
CREATE INDEX idx_pd_incidents_urgency ON pagerduty_incidents(urgency);
CREATE INDEX idx_pd_incidents_service ON pagerduty_incidents(service_id);
CREATE INDEX idx_pd_incidents_triggered ON pagerduty_incidents(triggered_at DESC);
CREATE INDEX idx_pd_incidents_resolved ON pagerduty_incidents(resolved_at) WHERE resolved_at IS NOT NULL;
CREATE INDEX idx_pd_incidents_team ON pagerduty_incidents USING GIN(teams);

-- Unique constraint
CREATE UNIQUE INDEX uq_pd_incident_external ON pagerduty_incidents(external_incident_id);
```

### Extended: entity_links

Add link types:
```python
# PagerDuty enrichment
TRIGGERED_BY = "triggered_by"        # Alert → PD incident
ESCALATED_TO = "escalated_to"        # JIRA → PD incident
DISCUSSED_IN = "discussed_in"        # PD incident → Slack thread
INCIDENT_FOR = "incident_for"        # PD incident → JIRA ticket
```

---

## Implementation Phases

Following the proven 6-day pattern from GitLab MR integration.

### Day 1: Database Schema and Models ✅

**Goal**: Create pagerduty_incidents table and SQLAlchemy model with computed properties

### Day 2: Service Layer (MCP Integration) 🔄

**Goal**: PagerDutyService with MCP integration, incident fetching, reference extraction

### Day 3: API Endpoints

**Goal**: 6 REST endpoints for listing, filtering, and syncing incidents

### Day 4: Frontend Components

**Goal**: React components for displaying incidents with status colors and filters

### Day 5: Background Jobs

**Goal**: Automated sync every 30min + auto-linking to JIRA/Agent entities

### Day 6: Testing and Documentation

**Goal**: Comprehensive testing and PAGERDUTY-INTEGRATION-COMPLETE.md

---

## Timeline

**Total Effort**: ~22 hours (~3 days)
**Target Completion**: 2026-03-22

---

## Success Criteria

- [ ] Incidents fetched from PagerDuty via MCP
- [ ] Full incident metadata stored in database
- [ ] API endpoints return filtered incident lists
- [ ] Frontend displays incidents with proper status colors
- [ ] Background jobs sync incidents every 30 minutes
- [ ] PagerDuty references auto-detected in JIRA/Agent text
- [ ] Entity links created automatically
- [ ] Complete documentation with examples

---

## References

- **Auto-Context Spec**: [AUTO-CONTEXT-ENRICHMENT-SPEC.md](./AUTO-CONTEXT-ENRICHMENT-SPEC.md) (lines 275-331)
- **MCP Config**: `~/.cursor/mcp.json`
- **Team On-Call**: `~/claude/teams/oncall.md`
- **Pattern Reference**: [GITLAB-MR-INTEGRATION-COMPLETE.md](./GITLAB-MR-INTEGRATION-COMPLETE.md)
