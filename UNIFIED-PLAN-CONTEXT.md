# Commander Development Context - Unified Plan

**Date**: 2026-03-20
**For**: Commander development agent
**Status**: Phase 2 complete (4/4 integrations), Phase 3 ready to start

---

## What Changed

**Previous plan**: Commander was a standalone dashboard project

**New plan**: Commander is part of a unified **Planet Operations Platform** with three components:

1. **v2** (Progressive Disclosure) - Documentation delivery system (~/claude/v2/)
2. **Commander** (Work Context Platform) - Context assembly system (~/claude/dashboard/)
3. **ECC Integration** - Automation patterns (hooks, agents, learning)

**Impact on Commander development**: Minimal - Phase 3 proceeds as planned, but with awareness of integration points

---

## Commander's Role in the Unified Platform

**Commander is the "context assembly engine"**:
- Fetches data from all systems (JIRA, PagerDuty, Grafana, Slack, GitLab, etc.)
- Creates EntityLink graph connecting everything
- Background jobs enrich work contexts
- API provides unified context to AI agents

**v2 provides the "documentation delivery"**:
- Progressive disclosure of project/tool docs
- Reduces token usage from 32K → 7-12K
- Loads based on triggers (project mentions, tool usage)

**ECC provides the "automation"**:
- Lifecycle hooks trigger Commander enrichment
- Language-specific agents review code
- Pattern extraction learns from artifacts
- Verification loops validate multi-step workflows

**Together**: User mentions "Debug WX task COMPUTE-1234"
- ECC hook detects triggers → loads v2 docs (WX-INDEX, KUBECTL-QUICK-REF)
- ECC hook calls Commander → enriches COMPUTE-1234 (PD, alerts, artifacts, MRs)
- Combined context delivered: 10-12K tokens total

---

## What This Means for Commander Development

### Good News

1. **Phase 3 (Proactive Warning Monitoring) proceeds as planned** ✅
   - No changes to the spec (PROACTIVE-INCIDENT-RESPONSE-SPEC.md)
   - No changes to the implementation approach
   - Can start immediately

2. **Phase 3 gains ECC automation benefits** 🚀
   - ECC hooks can auto-trigger warning monitoring
   - Pattern extraction can learn escalation patterns
   - Verification loops can validate mitigation steps

3. **Parallel development** 👥
   - Commander agent: Focus on Phase 3
   - ECC agent: Focus on hooks + v2 integration
   - Minimal coordination needed (only API endpoints)

### New Integration Points

**Commander needs to expose 2 new API endpoints** (Week 1-2):

1. `/api/enrich/{entity_type}/{entity_id}` (POST)
   - Triggers immediate enrichment of an entity
   - Called by ECC hooks when user mentions JIRA ticket
   - Returns enriched context

2. `/api/context/{context_id}/v2_metadata` (GET)
   - Returns metadata about loaded v2 docs
   - Used by UI to display token budget
   - Optional - can be added later (Week 3)

**That's it.** Everything else in Commander works as-is.

---

## Commander Phase 3: Proactive Warning Monitoring

**Location**: See `PROACTIVE-INCIDENT-RESPONSE-SPEC.md`

**Goal**: Monitor #compute-platform-warn, predict escalations, pre-assemble mitigation contexts

**Status**: Ready to implement (no dependencies on ECC)

**Effort**: 2 days (16 hours) as originally planned

**Can start**: Immediately (in parallel with ECC Week 1-2)

### Phase 3 Implementation (Unchanged)

**Day 1: Real-Time Monitoring** (8 hours)
- [ ] WarningEvent model
- [ ] SSE monitoring for #compute-platform-warn
- [ ] Warning message parsing
- [ ] Classification (alert name, system, severity)

**Day 2: Escalation Prediction** (8 hours)
- [ ] Pattern matching (DB, scheduler, resource patterns)
- [ ] Historical escalation rate analysis
- [ ] Escalation probability calculation
- [ ] Standby context creation

**Later: Mitigation Plan Generation** (Week 4-5)
- [ ] Artifact search integration (uses semantic search)
- [ ] Runbook parsing from alert definitions
- [ ] Plan template generation
- [ ] Mitigation plan UI

**Later: Learning System** (Week 6+)
- [ ] Escalation metrics collection
- [ ] Feedback collection (post-incident)
- [ ] Model accuracy tracking
- [ ] ECC integration: Pattern extraction from incidents

---

## How Phase 3 Integrates with ECC

**Week 1-2** (ECC Foundation):
- Commander adds `/api/enrich` endpoint → ECC hooks can call it
- Phase 3 continues independently

**Week 4-5** (ECC Learning):
- Pattern extraction learns from warning→escalation patterns
- Commander's escalation predictor uses extracted patterns
- Confidence scores improve over time

**Week 6-7** (ECC Agents):
- Mitigation plans can include agent suggestions
- E.g., Go agent suggests "check for goroutine leak"

**Week 8** (ECC Verification):
- Verification loops validate mitigation steps
- E.g., checkpoint: "Alert cleared after mitigation"

**All optional** - Phase 3 works without ECC, gets better with ECC

---

## Development Workflow

### For Commander Agent (You)

**Focus**: Implement Phase 3 (proactive warning monitoring)

**Timeline**: Start now, complete in 2 days (16 hours)

**Coordinate with ECC agent**: Only for `/api/enrich` endpoint (Week 1)

**Reference docs**:
- Spec: `PROACTIVE-INCIDENT-RESPONSE-SPEC.md`
- Development guide: `CLAUDE.md`
- Progress tracking: `PROGRESS.md`
- Integration pattern: See Phase 2 summary artifact

**Ignore for now**:
- v2 documentation system (not relevant to Phase 3)
- ECC hooks (will integrate later)
- Pattern extraction (will integrate later)

---

### For ECC Agent (Parallel Work)

**Focus**: Implement ECC Foundation (Week 1-2)

**Timeline**: 20 hours over 2 weeks

**Coordinate with Commander agent**: Only for API endpoints

**Key deliverable**: Hook system that can:
- Detect triggers (project, tool, JIRA ticket)
- Load v2 docs (progressive disclosure)
- Call Commander `/api/enrich` endpoint

---

## API Endpoints Needed

### 1. POST /api/enrich/{entity_type}/{entity_id}

**Purpose**: Trigger immediate enrichment of an entity

**Request**:
```json
POST /api/enrich/jira_issue/COMPUTE-1234
{
  "force_refresh": false  // optional
}
```

**Response**:
```json
{
  "entity_type": "jira_issue",
  "entity_id": "COMPUTE-1234",
  "enrichment_status": "complete",
  "entity_links_created": 4,
  "entities_fetched": {
    "pagerduty_incidents": 1,
    "grafana_alerts": 2,
    "artifacts": 3,
    "gitlab_mrs": 1
  },
  "enrichment_time_ms": 324
}
```

**Implementation** (~2 hours):
```python
# backend/app/api/enrichment.py (new file)
from fastapi import APIRouter, HTTPException
from app.services.jira_service import JiraService
from app.services.entity_link import EntityLinkService

router = APIRouter(prefix="/api/enrich", tags=["enrichment"])

@router.post("/{entity_type}/{entity_id}")
async def enrich_entity(
    entity_type: str,
    entity_id: str,
    force_refresh: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Trigger immediate enrichment of an entity."""
    if entity_type == "jira_issue":
        # Use existing JIRA service
        jira_service = JiraService(db)

        # Fetch JIRA issue (from cache unless force_refresh)
        issue = await jira_service.get_issue(entity_id, force_refresh)

        if not issue:
            raise HTTPException(404, f"Issue {entity_id} not found")

        # Trigger enrichment (reuse existing background job logic)
        link_service = EntityLinkService(db)
        start = time.time()

        # Run all enrichment services
        stats = await link_service.enrich_jira_issue(issue.id)

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "enrichment_status": "complete",
            "entity_links_created": stats["links_created"],
            "entities_fetched": stats["entities"],
            "enrichment_time_ms": int((time.time() - start) * 1000)
        }

    else:
        raise HTTPException(400, f"Unsupported entity type: {entity_type}")
```

**Register in main.py**:
```python
from app.api import enrichment
app.include_router(enrichment.router)
```

---

### 2. GET /api/context/{context_id}/v2_metadata (Optional, Week 3)

**Purpose**: Get metadata about loaded v2 docs for a context

**Response**:
```json
{
  "context_id": "uuid",
  "v2_docs_loaded": {
    "layers": [
      {"name": "INDEX.md", "path": "~/claude/v2/INDEX.md", "tokens": 2346},
      {"name": "WX-INDEX.md", "path": "~/claude/v2/projects/WX-INDEX.md", "tokens": 2899},
      {"name": "KUBECTL-QUICK-REF.md", "path": "~/claude/v2/tools/KUBECTL-QUICK-REF.md", "tokens": 1371}
    ],
    "total_tokens": 6616,
    "load_time_ms": 87
  }
}
```

**Not needed for Phase 3** - Can be added later for UI integration

---

## Updated PROGRESS.md Sections

### Current Status (Updated)

```markdown
## Current Status

### ✅ Phase 2 Complete (2026-03-20)

All 4 integrations complete in 2h 10min:
- PagerDuty incidents
- Grafana alert definitions
- Investigation artifacts
- GitLab merge requests

### 🚧 Phase 3 In Progress (2026-03-20)

**Proactive Warning Monitoring** - 2 days (16 hours)
- Monitor #compute-platform-warn for escalation patterns
- Predict which warnings will escalate to alerts
- Pre-assemble mitigation contexts

**Parallel Work**: ECC integration (different agent)
- Week 1-2: Hook system + v2 auto-loading
- Adds `/api/enrich` endpoint for Commander
- No impact on Phase 3 timeline

### 📋 Next Up (After Phase 3)

**Week 4-5**: ECC Learning Integration
- Pattern extraction from artifacts
- Escalation pattern detection
- Confidence scoring for predictions

**Week 6-7**: ECC Agent Integration
- Language-specific code reviewers
- Mitigation plan suggestions

**Week 8**: ECC Verification Integration
- Checkpoint evaluation for mitigation steps
- Observer loop prevention
```

---

## Key Files Reference

### Commander Development

**Specs**:
- `PROACTIVE-INCIDENT-RESPONSE-SPEC.md` - Phase 3 spec (UNCHANGED)
- `AUTO-CONTEXT-ENRICHMENT-SPEC.md` - Enrichment patterns (reference)
- `PLANET-COMMANDER-SPEC.md` - Product vision (reference)

**Development**:
- `CLAUDE.md` - Development guide (UNCHANGED)
- `PROGRESS.md` - Progress tracking (UPDATE after each day)

**Integration Pattern**:
- `artifacts/20260320-1930-phase2-integrations-summary.md` - Proven 5-step pattern

**New Unified Docs** (for context only):
- `~/claude/ARCHITECTURE-RECONCILIATION.md` - How v2 + Commander + ECC fit together
- `~/claude/UNIFIED-IMPLEMENTATION-PLAN.md` - 8-week plan for all three systems
- `~/claude/dashboard/ECC-INTEGRATION-GAP-ANALYSIS.md` - ECC integration details

---

## Commander Phase 3 Quick Start

**You are ready to start Phase 3 immediately:**

1. **Read the spec**: `PROACTIVE-INCIDENT-RESPONSE-SPEC.md`
2. **Follow the pattern**: Reference Phase 2 integration summaries
3. **Track progress**: Update `PROGRESS.md` after each day
4. **Coordinate once**: Add `/api/enrich` endpoint (Week 1)

**No blockers** - All dependencies from Phase 2 are complete.

**Timeline**:
- Day 1: Real-time monitoring (SSE, parsing, classification)
- Day 2: Escalation prediction (patterns, probability, standby contexts)

**Success criteria**:
- Warnings detected from Slack in real-time
- Escalation probability calculated (high/medium/low)
- Standby contexts created with runbooks + similar incidents

---

## FAQ for Commander Agent

### Q: Do I need to wait for ECC integration?

**A**: No. Phase 3 has zero dependencies on ECC. Start immediately.

### Q: How do I coordinate with ECC agent?

**A**: Minimal coordination:
- Week 1: Add `/api/enrich` endpoint (2 hours)
- Week 3: (Optional) Add v2 metadata endpoint (1 hour)
- That's it.

### Q: Does Phase 3 spec change?

**A**: No. `PROACTIVE-INCIDENT-RESPONSE-SPEC.md` is unchanged. Implement as written.

### Q: Will ECC break Commander?

**A**: No. ECC only adds automation on top. Commander works independently.

### Q: When do I integrate ECC features?

**A**: Later phases:
- Week 4-5: Pattern extraction (optional enhancement)
- Week 6-7: Agent suggestions (optional enhancement)
- Week 8: Verification loops (optional enhancement)

All **optional** - Phase 3 delivers value without ECC.

### Q: What if I have questions about the unified plan?

**A**: Read:
1. This document (UNIFIED-PLAN-CONTEXT.md)
2. `~/claude/ARCHITECTURE-RECONCILIATION.md` (architecture)
3. `~/claude/UNIFIED-IMPLEMENTATION-PLAN.md` (detailed plan)

Still confused? Ask the user to clarify.

---

## Summary for Commander Agent

**What you need to know**:
1. Commander is part of a 3-component unified platform
2. Phase 3 proceeds exactly as planned (no changes)
3. One new endpoint needed: `/api/enrich` (2 hours, Week 1)
4. ECC integration happens in parallel (different agent)
5. ECC adds automation benefits later (optional enhancements)

**What you should do**:
1. Read `PROACTIVE-INCIDENT-RESPONSE-SPEC.md`
2. Start Day 1 of Phase 3 (real-time monitoring)
3. Add `/api/enrich` endpoint when ECC agent needs it
4. Continue Phase 3 implementation
5. Update `PROGRESS.md` after each day

**What you should NOT do**:
1. Wait for ECC integration (not needed)
2. Change Phase 3 spec (it's correct as-is)
3. Implement v2 loading (different agent handles that)
4. Worry about pattern extraction (comes later)

**You are unblocked. Start Phase 3 now.** 🚀

---

**Questions?** Reference:
- Development guide: `CLAUDE.md`
- Phase 3 spec: `PROACTIVE-INCIDENT-RESPONSE-SPEC.md`
- Integration pattern: Phase 2 artifacts
- Unified plan: This document

**Ready to start?** Say: "Start Commander Phase 3 - Day 1"

---

**Last Updated**: 2026-03-20
**Document**: Commander agent context for unified plan
**Status**: Phase 3 ready to start
