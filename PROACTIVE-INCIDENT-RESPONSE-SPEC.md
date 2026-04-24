# Proactive Incident Response — Slack Warning Monitor

**Created**: 2026-03-18
**Purpose**: Monitor warning channels, pre-assemble incident context before escalation
**Integration**: Commander Auto-Context Enrichment + Slack SSE

---

## Vision

**Current state**: Reactive incident response
- Alert fires → PagerDuty pages → Human investigates → Context assembled → Mitigation starts
- **Lag time**: 5-15 minutes to gather context and start mitigation

**Future state**: Proactive incident response
- Warning appears in `#compute-platform-warn` → Commander detects → Context pre-assembled → Mitigation plan ready
- **If escalates** to `#compute-platform` → Plan already available → Immediate action
- **If resolves** → Context archived for learning

---

## Channel Architecture

### Compute Team Alert Flow

```
Warning Level (#compute-platform-warn)
├── Failed deployments
├── Non-critical PagerDuty warnings
├── Threshold approaching (not breached)
├── Transient failures
└── System health degradation

                    ↓ (if escalates)

Alert Level (#compute-platform)
├── Critical PagerDuty alerts
├── SEV1-3 incidents
├── Service outages
└── Customer impact
```

### Other Team Patterns

| Team | Warning Channel | Alert Channel | Pattern |
|------|----------------|---------------|---------|
| **Compute** | `#compute-platform-warn` | `#compute-platform` | Warnings → Alerts |
| **Data Pipeline** | `#datapipeline` (mixed) | PagerDuty only | No separate warn |
| **Hobbes** | `#hobbes` (mixed) | PagerDuty only | No separate warn |

**Compute has unique two-tier pattern** — can be model for other teams!

---

## Proactive Response Workflow

### Phase 1: Warning Detection

**Trigger**: Message posted to `#compute-platform-warn`

**Commander actions**:
1. Parse warning message (alert name, system, severity)
2. Classify warning type:
   - Deployment failure
   - Threshold approaching
   - Transient failure
   - Resource degradation
3. Determine if this warning could escalate
4. If escalation-prone → Start pre-assembly

### Phase 2: Context Pre-Assembly

**For escalation-prone warnings**, Commander automatically:

```
Warning Detected: "jobs-scheduler-low-runs WARNING"
├── 🔍 Search artifacts for "jobs-scheduler" investigations
├── 📊 Load alert definition (threshold, query, runbook)
├── 📖 Load Jobs project context (jobs-claude.md)
├── 🎯 Identify recommended skill (jobs-alert-triage)
├── 📋 Find similar prior incidents (semantic search)
├── 🛠️ Pre-load mitigation steps (from runbooks)
├── 👥 Identify on-call contact (from PagerDuty)
└── 💾 Create "Standby Context" (ready to activate)
```

**Status**: `standby` (warning active, not yet incident)

### Phase 3: Escalation Detection

**Trigger**: Same alert fires in `#compute-platform` (critical level)

**Commander actions**:
1. Detect correlation (same alert name)
2. Activate standby context → Full incident context
3. Notify on-call with pre-assembled plan
4. Create incident work context (auto-linked)
5. Status: `standby` → `active_incident`

### Phase 4: Resolution or Auto-Clear

**If warning clears without escalation**:
- Archive standby context
- Add to learning corpus (warnings that didn't escalate)
- Update escalation probability model

**If escalates then resolves**:
- Incident context remains
- Link to postmortem (if needed)
- Update mitigation effectiveness

---

## Warning Classification System

### Escalation-Prone Warnings

**High probability of escalation** (pre-assemble context):
- **Database warnings**: Connection pool, CPU, slow queries
- **Scheduler failures**: Low runs, stuck jobs, queue depth
- **Resource exhaustion**: Memory approaching limit, disk filling
- **Deployment failures**: Multiple failures, rollback needed
- **Service health**: Multiple components degrading

**Pattern detection**:
```python
ESCALATION_PATTERNS = {
    "high": [
        r"database.*cpu.*high",
        r"scheduler.*low.*runs",
        r"memory.*approaching.*limit",
        r"deployment.*failed.*rollback",
        r"service.*degraded"
    ],
    "medium": [
        r"connection.*pool.*warning",
        r"queue.*depth.*increasing",
        r"disk.*\d{2}%.*full"
    ],
    "low": [
        r"transient.*failure",
        r"retry.*successful"
    ]
}
```

### Low-Escalation Warnings

**Low probability** (log but don't pre-assemble):
- Transient network blips
- Single retry successful
- Brief threshold breach (< 1 min)
- Non-critical subsystem

---

## Mitigation Plan Generation

### Automatic Plan Assembly

For each warning, generate mitigation plan from:

1. **Runbook** (from alert definition)
2. **Prior investigations** (artifact search)
3. **Known fixes** (from past incidents)
4. **Diagnostic commands** (from project claude.md)

**Example: jobs-scheduler-low-runs WARNING**

```markdown
# Pre-Assembled Mitigation Plan

## Alert: jobs-scheduler-low-runs
**Status**: ⚠️ WARNING (not yet critical)
**First seen**: 2026-03-18 14:23 PST
**Escalation probability**: 🔴 HIGH (75%)

## Quick Checks (Run immediately if escalates)

1. **Check scheduler health**:
   ```bash
   pjclient workers stats
   ```
   Expected: Should return successfully
   If fails: Scheduler likely down

2. **Check queue depth**:
   ```bash
   pjclient jobs search --state queued --limit 10
   ```
   Expected: < 1000 queued jobs
   If high: Queue backup indicates problem

3. **Check database**:
   - Dashboard: [Jobs DB Metrics](https://planet.grafana.net/...)
   - Look for: CPU spikes, connection pool exhaustion

## Prior Incidents (Similar Pattern)

📋 **20260212-0936-jobs-scheduler-investigation.md**
- Root cause: Database connection pool exhaustion
- Fix: Increased pool size, deployed in 15 min
- Prevented escalation: Yes

📋 **20260108-jobs-alert-triage.md**
- Root cause: Redis connectivity issues
- Fix: Restarted Redis, recovered in 5 min
- Note: This pattern recurs monthly

## Recommended Actions (If escalates to CRITICAL)

1. **Immediate** (< 2 min):
   - Run diagnostic commands above
   - Check if this matches prior pattern

2. **If database issue** (5 min):
   - Increase connection pool (prior fix)
   - Deploy via helm upgrade

3. **If Redis issue** (3 min):
   - Restart Redis pods
   - Monitor recovery

4. **If neither** (10 min):
   - Escalate to secondary on-call
   - Start full investigation

## On-Call Contact
👤 **Aaryn Olsson** (current rotation)
- Slack: @aaryn
- PagerDuty: Will auto-page if escalates

## Resources
- Runbook: https://hello.planet.com/wiki/.../Jobs-Scheduler-Runbook
- Dashboard: https://planet.grafana.net/d/.../jobs-3e-jobs
- Alert definition: [jobs-scheduler-low-runs.yaml](...)
```

**This plan is ready BEFORE the critical alert fires!**

---

## Real-Time Monitoring Architecture

### Slack SSE Integration

**Already implemented**: WX Deployments use SSE from backend

**Extend for warning monitoring**:

```python
# backend/app/services/slack_warning_monitor.py

class SlackWarningMonitor:
    """Monitor #compute-platform-warn for escalation-prone warnings."""

    MONITORED_CHANNELS = [
        "C123ABC",  # #compute-platform-warn
        # Add other team warn channels
    ]

    async def monitor_warnings(self):
        """Real-time monitoring via Slack API."""
        async for message in self.slack_client.listen_channel(
            channels=self.MONITORED_CHANNELS
        ):
            warning = self.parse_warning(message)
            if self.is_escalation_prone(warning):
                await self.pre_assemble_context(warning)

    def is_escalation_prone(self, warning: Warning) -> bool:
        """Classify warning escalation probability."""
        # Pattern matching
        # Historical data (what % of these warnings escalate?)
        # Time of day (deploy window = higher risk)
        # Recent similar warnings
        return probability > 0.5

    async def pre_assemble_context(self, warning: Warning):
        """Build standby incident context."""
        context = await self.context_resolver.create_standby_context(
            alert_name=warning.alert_name,
            system=warning.system,
            first_seen=warning.timestamp
        )

        # Fetch all the things
        await self.artifact_service.search_similar(warning.alert_name)
        await self.alert_service.load_definition(warning.alert_name)
        await self.project_service.load_context(warning.system)
        await self.runbook_service.load_mitigation_steps(warning.alert_name)

        # Generate plan
        plan = await self.plan_generator.generate(context)

        # Notify (low-priority, FYI)
        await self.notify_on_call(
            message=f"⚠️ Warning detected, context pre-assembled: {warning.alert_name}",
            context_url=context.url,
            severity="info"
        )
```

### Database Schema Extension

```sql
-- Extend work_contexts with standby state
ALTER TABLE work_contexts
ADD COLUMN origin_warning_ts TIMESTAMPTZ,
ADD COLUMN escalation_probability FLOAT,
ADD COLUMN escalated_at TIMESTAMPTZ,
ADD COLUMN auto_cleared_at TIMESTAMPTZ;

-- New table for warning tracking
CREATE TABLE warning_events (
    id UUID PRIMARY KEY,
    alert_name VARCHAR(200),
    channel_id VARCHAR(50),
    message_ts VARCHAR(50),
    severity VARCHAR(10),  -- warning, critical
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    escalated BOOLEAN DEFAULT FALSE,
    escalated_at TIMESTAMPTZ,
    auto_cleared BOOLEAN DEFAULT FALSE,
    cleared_at TIMESTAMPTZ,
    escalation_probability FLOAT,
    standby_context_id UUID REFERENCES work_contexts(id),
    incident_context_id UUID REFERENCES work_contexts(id),
    raw_message JSONB
);

CREATE INDEX idx_warning_events_alert ON warning_events(alert_name);
CREATE INDEX idx_warning_events_escalated ON warning_events(escalated);
CREATE INDEX idx_warning_events_first_seen ON warning_events(first_seen);
```

---

## Escalation Detection Algorithm

### Pattern Matching

```python
class EscalationDetector:
    """Detect when warning escalates to critical alert."""

    async def detect_escalation(
        self,
        critical_alert: Alert,
        lookback_window: timedelta = timedelta(hours=2)
    ) -> Optional[WarningEvent]:
        """Check if this alert was preceded by a warning."""

        # Same alert name in warn channel?
        warning = await self.warning_repo.find_recent(
            alert_name=critical_alert.name,
            since=critical_alert.fired_at - lookback_window
        )

        if warning and not warning.escalated:
            # Mark as escalated
            warning.escalated = True
            warning.escalated_at = critical_alert.fired_at

            # Activate standby context
            if warning.standby_context_id:
                await self.activate_standby_context(
                    warning.standby_context_id,
                    critical_alert
                )

            return warning

        return None

    async def activate_standby_context(
        self,
        standby_context_id: UUID,
        critical_alert: Alert
    ):
        """Convert standby context to active incident."""

        context = await self.context_repo.get(standby_context_id)

        # Update status
        context.status = "active_incident"
        context.escalated_at = critical_alert.fired_at

        # Create incident work context (if needed)
        incident = await self.create_incident_context(
            warning_context=context,
            alert=critical_alert
        )

        # Link contexts
        await self.link_service.create_link(
            from_type="work_context",
            from_id=standby_context_id,
            to_type="work_context",
            to_id=incident.id,
            link_type="escalated_to"
        )

        # Notify on-call with pre-assembled plan
        await self.notify_escalation(context, incident)
```

---

## Learning System

### Track Escalation Patterns

**What to learn**:
- Which warnings escalate vs. auto-clear
- Time-to-escalation (if warning → alert)
- Effectiveness of pre-assembled plans
- False positive rate (standby contexts never used)

**Data collection**:
```sql
CREATE TABLE warning_escalation_metrics (
    alert_name VARCHAR(200),
    total_warnings INTEGER,
    escalated_count INTEGER,
    auto_cleared_count INTEGER,
    escalation_rate FLOAT,
    avg_time_to_escalation INTERVAL,
    avg_time_to_clear INTERVAL,
    last_calculated_at TIMESTAMPTZ,
    PRIMARY KEY (alert_name)
);
```

**Model training**:
- Historical escalation rate per alert
- Time-of-day patterns (deployments = higher risk)
- Recent trend (increasing frequency = higher risk)
- Correlated warnings (multiple systems = higher risk)

### Mitigation Effectiveness

**Track**:
- Was pre-assembled plan used?
- Was it helpful? (on-call feedback)
- Time saved vs. reactive response
- Accuracy of recommended actions

```sql
CREATE TABLE mitigation_plan_feedback (
    id UUID PRIMARY KEY,
    warning_event_id UUID REFERENCES warning_events(id),
    plan_used BOOLEAN,
    helpful_rating INTEGER,  -- 1-5 scale
    time_saved_minutes INTEGER,
    recommended_action_accurate BOOLEAN,
    feedback_text TEXT,
    responder VARCHAR(200),
    created_at TIMESTAMPTZ
);
```

---

## UI/UX Design

### Warning Monitor Dashboard

**New page**: `/warnings` or integrate into main dashboard

**Layout**:
```
┌─────────────────────────────────────────────────────┐
│  ⚠️  Warning Monitor                       [Settings]│
├─────────────────────────────────────────────────────┤
│                                                       │
│  🟡 Active Warnings (3)                              │
│  ┌───────────────────────────────────────────────┐  │
│  │ 🔴 jobs-scheduler-low-runs                    │  │
│  │    Escalation prob: 75% • First seen: 14:23   │  │
│  │    [View Plan] [Dismiss] [Create Incident]    │  │
│  ├───────────────────────────────────────────────┤  │
│  │ 🟡 wx-task-lease-expiration                   │  │
│  │    Escalation prob: 45% • First seen: 14:30   │  │
│  │    [View Plan] [Dismiss]                      │  │
│  └───────────────────────────────────────────────┘  │
│                                                       │
│  🟢 Auto-Cleared Today (8)                           │
│  • g4-executor-oom (cleared after 5min)              │
│  • jobs-workers-idle (cleared after 12min)           │
│  • ...                                               │
│                                                       │
│  📊 Escalation History (Last 7 Days)                │
│  [Chart: Warnings vs. Escalations]                   │
│                                                       │
│  🎯 Learning Metrics                                 │
│  • Escalation prediction accuracy: 82%               │
│  • Avg time saved: 8 minutes                         │
│  • False positive rate: 18%                          │
└─────────────────────────────────────────────────────┘
```

### Standby Context View

When clicking "View Plan" on a warning:

```
┌─────────────────────────────────────────────────────┐
│  ⚠️  Standby Context: jobs-scheduler-low-runs       │
│                                           [Activate]│
├─────────────────────────────────────────────────────┤
│                                                       │
│  📊 Warning Details                                  │
│  • First seen: 14:23 PST (12 min ago)               │
│  • Channel: #compute-platform-warn                   │
│  • Escalation probability: 🔴 75%                   │
│  • Pattern match: Database connection pool (80%)     │
│                                                       │
│  🛠️  Pre-Assembled Mitigation Plan                  │
│  ┌───────────────────────────────────────────────┐  │
│  │ ## Quick Checks                               │  │
│  │                                               │  │
│  │ 1. Check scheduler health:                   │  │
│  │    ```bash                                    │  │
│  │    pjclient workers stats                    │  │
│  │    ```                                        │  │
│  │    [Copy] [Run in Terminal]                  │  │
│  │                                               │  │
│  │ 2. Check queue depth: ...                    │  │
│  └───────────────────────────────────────────────┘  │
│                                                       │
│  📋 Prior Incidents (2 similar)                      │
│  • 20260212-0936-jobs-scheduler-investigation.md     │
│    → Database connection pool exhaustion (fixed)     │
│  • 20260108-jobs-alert-triage.md                     │
│    → Redis connectivity (recurring pattern)          │
│                                                       │
│  🔗 Auto-Linked Context                              │
│  • Alert definition: jobs-scheduler-low-runs.yaml    │
│  • Project context: jobs-claude.md                   │
│  • Dashboard: Jobs 3E                                │
│  • Runbook: Jobs Scheduler Runbook                   │
│                                                       │
│  [Escalate to Incident] [Dismiss Warning]           │
└─────────────────────────────────────────────────────┘
```

### Incident Escalation Flow

**When critical alert fires in #compute-platform**:

```
┌─────────────────────────────────────────────────────┐
│  🚨 ALERT ESCALATED                                 │
│                                                      │
│  jobs-scheduler-low-runs → CRITICAL                 │
│                                                      │
│  ✅ Mitigation plan ready (pre-assembled 12min ago) │
│                                                      │
│  [View Incident Context] [Start Mitigation]         │
└─────────────────────────────────────────────────────┘
```

---

## Notification Strategy

### Low-Priority (Warning Detected)

**Channel**: Slack DM or low-priority channel
**Message**:
```
⚠️ Warning detected: jobs-scheduler-low-runs
Escalation probability: 75% (high)
Context pre-assembled: https://commander.local/warnings/abc-123

No action needed unless this escalates to critical.
```

### High-Priority (Escalation Detected)

**Channel**: PagerDuty (already firing) + Slack
**Message**:
```
🚨 ALERT ESCALATED: jobs-scheduler-low-runs

✅ Mitigation plan ready (pre-assembled 12 minutes ago)

Quick actions:
1. pjclient workers stats
2. Check DB connection pool

View full plan: https://commander.local/incidents/xyz-789

Prior incident (same pattern): 20260212-0936-jobs-scheduler-investigation.md
→ Fix: Increased connection pool size (15 min resolution)
```

---

## Configuration

### Per-Team Settings

```yaml
# backend/config/warning_monitor.yaml

warning_monitor:
  enabled: true

  channels:
    - name: "compute-platform-warn"
      channel_id: "C123ABC"
      team: "compute"
      escalation_channel: "C456DEF"  # #compute-platform

  escalation_thresholds:
    probability: 0.5  # Pre-assemble if > 50%
    lookback_window_hours: 2

  learning:
    enabled: true
    feedback_collection: true
    model_update_frequency: "daily"

  notifications:
    warning_detected:
      enabled: true
      channel: "slack_dm"
      priority: "low"

    escalation_detected:
      enabled: true
      channel: "slack_alert"
      priority: "high"
      include_plan: true
```

---

## Success Metrics

### Proactive Response Effectiveness

- **Time to first action**: Warning → Plan available
  - Target: < 2 minutes (pre-assembled before escalation)
  - vs. Reactive: 5-15 minutes (after alert fires)

- **Escalation prediction accuracy**:
  - Target: > 80% (warnings flagged as high-risk do escalate)
  - False positive rate: < 20% (standby contexts never used)

- **Mitigation time reduction**:
  - Target: 50% reduction in time-to-mitigation
  - Measure: Pre-assembled vs. reactive response

- **On-call feedback**:
  - Target: > 80% find pre-assembled plans helpful
  - Collect: Post-incident surveys

### Learning System

- **Model improvement**: Escalation prediction accuracy over time
  - Baseline: 60% (naive model)
  - Target: 80%+ (trained model)

- **Pattern recognition**: Identify recurring warning patterns
  - Target: Detect 90%+ of recurring issues
  - Action: Automated fixes for known patterns

---

## Implementation Phases

### Phase 1: Basic Warning Monitoring (2 weeks)

- [ ] Slack SSE integration for `#compute-platform-warn`
- [ ] Warning message parsing
- [ ] Database schema (warning_events table)
- [ ] Basic UI (warning list)

### Phase 2: Escalation Detection (2 weeks)

- [ ] Alert correlation algorithm
- [ ] Standby context creation
- [ ] Escalation detection
- [ ] Standby → Active transition

### Phase 3: Mitigation Plan Generation (3 weeks)

- [ ] Artifact search integration
- [ ] Alert definition fetching
- [ ] Runbook parsing
- [ ] Plan template generation
- [ ] Plan UI

### Phase 4: Learning System (3 weeks)

- [ ] Escalation metrics collection
- [ ] Prediction model training
- [ ] Feedback collection
- [ ] Model updates

### Phase 5: Multi-Team Expansion (2 weeks)

- [ ] Support other team warning patterns
- [ ] Configurable escalation rules
- [ ] Team-specific plan templates

---

## Open Questions

1. **False positive tolerance**: What % of unused standby contexts is acceptable?
2. **Plan generation quality**: How to measure if generated plans are actually helpful?
3. **Notification fatigue**: How to balance FYI notifications vs. noise?
4. **Multi-team adoption**: Will other teams want this? Should we build for Compute only first?
5. **Automated mitigation**: Should Commander ever auto-execute mitigation steps? (Risky!)

---

## References

- **Auto-Context Enrichment**: [AUTO-CONTEXT-ENRICHMENT-SPEC.md](./AUTO-CONTEXT-ENRICHMENT-SPEC.md)
- **Slack Context Parser**: [SLACK-CONTEXT-PARSER-SPEC.md](./SLACK-CONTEXT-PARSER-SPEC.md)
- **Planet Commander**: [PLANET-COMMANDER-SPEC.md](./PLANET-COMMANDER-SPEC.md)
- **Investigation Methodology**: `~/claude/investigation-methodology.md`
- **Incident Response Skill**: `~/.claude/skills/incident-response/`
