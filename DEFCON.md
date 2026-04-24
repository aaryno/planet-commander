# DEFCON System Documentation

**Version**: 1.0
**Last Updated**: March 20, 2026
**Owner**: Compute Platform Team

---

## Overview

The **DEFCON (Defense Condition) System** is a multi-channel warning intelligence platform that provides real-time situational awareness of Planet's compute infrastructure health.

**Purpose**: Aggregate warning signals across Slack channels, PagerDuty incidents, and monitoring systems to provide a single, actionable health indicator for the platform.

**Analogy**: Think of it as the "check engine light" for Planet's infrastructure—but with 5 levels of granularity instead of just on/off.

---

## DEFCON Levels

### DEFCON 5 - Normal Operations 🟢

**Status**: All systems operating normally
**Score Range**: 0 - 2.9
**Typical State**: Baseline operations, minimal warning activity

**Characteristics**:
- Few or no active warnings across channels
- No multi-team incidents
- No critical alerts
- Business as usual

**Action Required**: None - continue normal operations

---

### DEFCON 4 - Minor Warning Activity 🔵

**Status**: Single team experiencing minor issues
**Score Range**: 3.0 - 5.9
**Typical State**: Isolated warnings, low severity

**Characteristics**:
- Single team (usually Compute) has active warnings
- Non-critical alerts (degraded performance, thresholds exceeded)
- No PagerDuty escalations
- Self-healing issues or transient problems

**Action Required**:
- **On-Call**: Monitor alerts, but no immediate action needed
- **Team**: Check if issues are auto-resolving
- **Escalation**: None unless warnings persist >30 minutes

**Example Scenario**:
```
compute-platform-warn: 3 alerts
  - jobs-scheduler-low-runs (warning)
  - wx-task-slow-processing (warning)
  - g4-api-latency-high (warning)

Teams: compute (1)
Score: 4.2
→ DEFCON 4: Minor warning activity
```

---

### DEFCON 3 - Significant Warning Activity 🟡

**Status**: Elevated warning activity or multi-team issues
**Score Range**: 6.0 - 9.9
**Typical State**: Multiple warnings, cross-team correlation, or single critical alert

**Characteristics**:
- 2-3 teams experiencing warnings simultaneously
- Critical alert in single system
- Some PagerDuty escalations
- User impact possible but not confirmed

**Action Required**:
- **On-Call**: Actively investigate warnings
- **Team**: Begin coordination if multi-team
- **Communication**: Update #compute-platform with status
- **Escalation**: Consider if warnings persist >15 minutes

**Example Scenario**:
```
compute-platform-warn: 5 alerts (2 critical)
delta-warn: 2 alerts
hobbes-warnings: 1 alert

Teams: compute, delta, hobbes (3)
Score: 8.1
→ DEFCON 3: Significant warning activity
```

**When to Escalate to DEFCON 2**:
- Multiple critical alerts
- Confirmed user impact
- Infrastructure-level issues (GKE, networking)

---

### DEFCON 2 - Major Multi-Team Issue 🟠

**Status**: Major incident affecting multiple teams or infrastructure
**Score Range**: 10.0 - 14.9
**Typical State**: Cross-platform impact, upstream infrastructure issues

**Characteristics**:
- 3+ teams alerting simultaneously
- Compute + Hobbes correlation (infrastructure impact)
- Multiple PagerDuty escalations
- Confirmed user impact or customer-facing degradation
- Lagged signal correlations detected (deployment → failures)

**Action Required**:
- **On-Call**: Immediate investigation required
- **Team**: Multi-team coordination via Slack/Zoom
- **Communication**:
  - Post in #compute-platform
  - Notify dependent teams (#datapipeline, #discovery-and-delivery)
  - Update status page if customer-facing
- **Escalation**: Consider declaring ProdIssue

**Example Scenario**:
```
compute-platform-warn: 8 alerts (5 critical)
  - wx-tasks-failing-high-rate (critical)
  - jobs-scheduler-down (critical)
  - g4-api-unavailable (critical)

hobbes-warnings: 3 alerts
  - gke-cluster-us-central1-degraded (critical)
  - workload-identity-errors (critical)

compute-platform-info (15 min ago):
  - gke-node-pool-update-us-central1

Teams: compute, hobbes (2)
Lagged correlation: node update → task failures
Score: 12.4
→ DEFCON 2: Major multi-team issue (infrastructure impact)
```

**When to Escalate to DEFCON 1**:
- Confirmed platform-wide outage
- Multiple critical services down
- Customer escalations

---

### DEFCON 1 - Platform-Wide Incident 🔴

**Status**: Critical incident affecting entire platform
**Score Range**: 15.0+
**Typical State**: Platform outage, multiple services down, widespread impact

**Characteristics**:
- 4+ teams experiencing critical alerts
- Multiple critical services unavailable
- Widespread PagerDuty escalations
- Customer escalations and support tickets
- Potential data loss or corruption risk

**Action Required**:
- **On-Call**: All hands on deck - activate incident response
- **Team**: War room (Slack thread + Zoom)
- **Communication**:
  - Declare ProdIssue immediately
  - Post in #production-incident-alerts
  - Update status page
  - Notify leadership
  - Customer communication via CS team
- **Escalation**: Incident Commander assigned

**Example Scenario**:
```
compute-platform-warn: 15 alerts (12 critical)
  - All platforms reporting critical failures

hobbes-warnings: 8 alerts
  - Multiple GKE clusters degraded/down

delta-warn: 5 alerts
discovery-and-delivery-warn: 4 alerts
datapipeline-alerts: 6 alerts

Teams: compute, hobbes, delta, dnd, datapipeline (5)
Score: 18.7
→ DEFCON 1: Platform-wide incident detected

ProdIssue: PRODISSUE-1234 (created automatically)
Status Page: Major outage posted
```

**Response Protocol**:
1. Activate incident response (see `/claude/projects/prodissue-notes/prodissue-claude.md`)
2. Assign Incident Commander
3. Create Slack incident thread
4. Start Zoom war room
5. Begin triage and mitigation
6. Hourly stakeholder updates

---

## How DEFCON is Calculated

### Data Sources

The DEFCON system aggregates data from:

1. **Slack Warning Channels** (13+ channels):
   - `#compute-platform-warn` - Direct Compute alerts
   - `#compute-platform-info` - Deployment notifications (lagged signals)
   - `#hobbes-warnings` - Infrastructure alerts
   - `#delta-warn`, `#discovery-and-delivery-warn` - Cross-team signals
   - Other team warning channels

2. **PagerDuty Incidents**:
   - Recent incidents (last 90 days)
   - Escalation status
   - Team ownership

3. **Grafana Alert Definitions**:
   - 107 alert rules
   - Severity mappings (critical, high, medium, low)
   - Team ownership

4. **Historical Patterns**:
   - Correlation database
   - Lagged signal detection
   - Multi-team incident history

### Scoring Algorithm

#### Step 1: Channel Weighting

Each channel has a base weight representing its importance:

| Channel | Weight | Rationale |
|---------|--------|-----------|
| `compute-platform-warn` | 1.0 | Direct Compute alerts |
| `hobbes` / `hobbes-warnings` | 1.5 | **Upstream infrastructure** - affects Compute downstream |
| `compute-platform-info` | 0.5 | Lagged indicators (deployments, not direct alerts) |
| `delta-warn` | 0.3 | Cross-team correlation signal |
| `discovery-and-delivery-warn` | 0.3 | Cross-team correlation signal |
| Other team channels | 0.2-0.4 | Context-dependent |

**Why Hobbes is weighted higher**: Hobbes owns GKE clusters, networking, and infrastructure. Issues there cascade to Compute platforms (WX, Jobs, G4).

#### Step 2: Severity Multiplier

Alert text is scanned for severity keywords:

- **Critical keywords** (3.0× multiplier):
  - `outage`, `down`, `failed`, `critical`, `unavailable`, `error`

- **Warning keywords** (1.5× multiplier):
  - `degraded`, `slow`, `high`, `low`, `latency`, `threshold`

- **Normal** (1.0× multiplier):
  - No severity keywords detected

#### Step 3: Escalation Multiplier

- **PagerDuty escalated**: 2.0× multiplier
- **High escalation probability** (>80%): 1.5× multiplier

#### Step 4: Multi-Team Correlation

If multiple teams are alerting simultaneously:

- **4+ teams**: 2.0× multiplier (platform-wide issue)
- **3 teams**: 1.5× multiplier (multi-team incident)
- **2 teams**: 1.2× multiplier (cross-team correlation)

#### Step 5: Special Combinations

Certain team combinations indicate higher risk:

- **Compute + Hobbes**: 1.5× multiplier (infrastructure cascading to platforms)
- **Compute + DataPipeline**: 1.3× multiplier (Jobs platform impact)

### Example Calculation

**Scenario**: GKE node update causes WX task failures

```
Warnings in last hour:

1. hobbes-warnings: "gke-cluster-us-central1-degraded"
   - Base weight: 1.5
   - Severity: "degraded" → 1.5× (warning keyword)
   - Escalated: Yes → 2.0×
   - Score: 1.5 × 1.5 × 2.0 = 4.5

2. compute-platform-warn: "wx-task-oom-critical"
   - Base weight: 1.0
   - Severity: "critical" → 3.0× (critical keyword)
   - Escalated: Yes → 2.0×
   - Score: 1.0 × 3.0 × 2.0 = 6.0

3. compute-platform-warn: "wx-api-latency-high"
   - Base weight: 1.0
   - Severity: "high" → 1.5× (warning keyword)
   - Escalated: No → 1.0×
   - Score: 1.0 × 1.5 × 1.0 = 1.5

Subtotal: 4.5 + 6.0 + 1.5 = 12.0

Multi-team multiplier:
  Teams: compute, hobbes (2 teams) → 1.2×

Special combination:
  Compute + Hobbes → 1.5× (infrastructure cascading)

Final Score: 12.0 × 1.2 × 1.5 = 21.6

→ DEFCON 1: Platform-wide incident detected
```

---

## Lagged Signal Detection

### What Are Lagged Signals?

**Lagged signals** are infrastructure changes that precede failures by 5-30 minutes.

**Example Pattern**:
```
14:00 - compute-platform-info: "GKE node pool rolling update"
14:18 - compute-platform-warn: "WX tasks OOMKilled (high rate)"
        ↑
   Lagged correlation detected! (18 minute lag)
```

### How Detection Works

The system monitors `#compute-platform-info` for deployment/infrastructure events, then watches for related warnings within 30 minutes.

**Correlation criteria**:
1. **Time window**: Warning occurs 5-30 minutes after info signal
2. **Entity matching**: Shared keywords (cluster name, region, namespace, service)
3. **Causality**: Info signal precedes warning (not vice versa)

**Common Lagged Patterns**:

| Info Signal | Lagged Warning | Typical Lag | Cause |
|-------------|----------------|-------------|-------|
| GKE node pool update | Pod OOMKilled | 10-20 min | Node churn → pod eviction → OOM |
| Workload Identity change | Auth failures | 5-15 min | Permission propagation delay |
| Network policy update | Connection timeouts | 5-10 min | Firewall rule propagation |
| K8s deployment | Task failures | 10-30 min | Bad image/config deployed |

**Why This Matters**:

Lagged signals provide **early warning** and **root cause hints**:
- "Why are WX tasks OOMing?" → "Oh, we just updated the node pool"
- Helps on-call engineers quickly identify deployment-related issues
- Prevents "unknown root cause" incidents

---

## Dashboard Integration

### Main Dashboard Widget

The DEFCON widget appears on the main Commander dashboard (`/`):

```
┌─────────────────────────────────┐
│ DEFCON 3            11:45 AM    │
├─────────────────────────────────┤
│ Significant warning activity    │
│                                 │
│ Teams: compute, hobbes          │
│ Warnings: 8                     │
│ Critical: 2                     │
│ Score: 7.2                      │
│                                 │
│ ⚠️ 1 lagged signal detected     │
└─────────────────────────────────┘
```

**Widget Features**:
- **Color-coded border**: Red (DEFCON 1) → Green (DEFCON 5)
- **Live updates**: Polls every 1 minute
- **Summary stats**: Teams, warning count, score
- **Lagged signals**: Alert icon if correlations detected

### DEFCON History

View recent DEFCON level changes (last 24 hours):

```
┌─────────────────────────────────────────────────┐
│ DEFCON History (24h)                     [↻]    │
├─────────────────────────────────────────────────┤
│                                                 │
│ DEFCON 2  14:23-14:45 (22m)                    │
│ Major multi-team issue                         │
│ compute, hobbes • 12 warnings                  │
│                                                 │
│ DEFCON 3  12:10-14:23 (2h 13m)                 │
│ Significant warning activity                   │
│ compute, delta • 6 warnings                    │
│                                                 │
│ DEFCON 5  00:00-12:10 (12h 10m)                │
│ Normal operations                              │
│ • 0 warnings                                   │
└─────────────────────────────────────────────────┘
```

**Use Cases**:
- **Incident timeline**: When did things go wrong?
- **Pattern recognition**: Do we hit DEFCON 3 every morning at 9am?
- **Postmortem context**: What was the DEFCON level during the incident?

---

## Response Workflows

### DEFCON 5 → 4 Transition

**What Happened**: Minor warnings appeared

**Response**:
1. Check warning details in `/warnings` page
2. Determine if auto-resolving (check last 5 minutes)
3. If persistent, investigate root cause
4. Document findings in alert's JIRA ticket

### DEFCON 4 → 3 Transition

**What Happened**: More warnings appeared OR second team started alerting

**Response**:
1. Post status update in `#compute-platform`:
   ```
   DEFCON 3: Multiple warnings active
   Investigating: [alert names]
   ETA for update: [time]
   ```
2. Check for lagged correlations (recent deployments?)
3. Coordinate with other teams if multi-team
4. Consider creating JIRA ticket if not auto-resolving

### DEFCON 3 → 2 Transition

**What Happened**: Critical alert OR compute + hobbes alerting

**Response**:
1. Post in `#compute-platform`:
   ```
   🟠 DEFCON 2: Major multi-team issue
   Impact: [description]
   Teams involved: compute, hobbes
   Incident thread: [link]
   ```
2. Create Slack incident thread
3. Start investigation with other teams
4. Consider declaring ProdIssue if user impact confirmed
5. Update status page if customer-facing

### DEFCON 2 → 1 Transition

**What Happened**: Platform-wide incident

**Response**:
1. **Immediate**: Declare ProdIssue
   - Use `/incident-response` skill or manual process
   - See `/claude/projects/prodissue-notes/prodissue-claude.md`

2. **Communication** (first 5 minutes):
   ```
   🔴 DEFCON 1: Platform-wide incident
   ProdIssue: PRODISSUE-1234
   Incident Commander: @on-call-engineer
   War room: [Zoom link]
   Thread: [Slack thread link]
   ```

3. **Coordination**:
   - Activate incident response protocol
   - Assign roles (IC, scribe, comms lead)
   - Start war room Zoom
   - Begin triage

4. **Status Updates**:
   - Update status page (via CS team)
   - Hourly stakeholder updates in thread
   - Customer communication (via CS)

---

## Configuration

### Channel Weights

Edit channel weights in `backend/app/services/defcon_service.py`:

```python
CHANNEL_WEIGHTS = {
    "compute-platform-warn": {
        "base_weight": 1.0,
        "team": "compute",
        "critical_keywords": ["production", "incident", "outage"],
        "warning_keywords": ["degraded", "slow"],
    },
    # Add more channels...
}
```

### DEFCON Thresholds

Adjust score thresholds in `score_to_defcon()`:

```python
def score_to_defcon(score: float) -> tuple[int, str]:
    if score >= 15:
        return (1, "Platform-wide incident detected")
    elif score >= 10:
        return (2, "Major multi-team issue")
    elif score >= 6:
        return (3, "Significant warning activity")
    elif score >= 3:
        return (4, "Minor warning activity")
    else:
        return (5, "Normal operations")
```

**Tuning Recommendations**:
- Monitor DEFCON levels for 1 week
- Analyze false alarms (DEFCON 2/3 without real issues)
- Analyze missed incidents (real issues at DEFCON 4/5)
- Adjust thresholds to minimize both

### Lagged Signal Window

Configure lag detection window in `check_lagged_correlations()`:

```python
LAG_WINDOW_MIN = 5   # Minimum lag (minutes)
LAG_WINDOW_MAX = 30  # Maximum lag (minutes)
```

**Recommended Values**:
- **Infrastructure changes**: 5-30 minutes (default)
- **Code deployments**: 2-15 minutes (faster feedback)
- **Database migrations**: 10-60 minutes (slower propagation)

---

## API Reference

### GET `/api/defcon/current`

Get current DEFCON level.

**Response**:
```json
{
  "level": 3,
  "reason": "Significant warning activity",
  "score": 7.2,
  "teams_alerting": ["compute", "hobbes"],
  "warning_count": 8,
  "critical_count": 2,
  "warnings": [
    {
      "channel": "compute-platform-warn",
      "team": "compute",
      "alert_name": "wx-task-oom",
      "score": 3.0,
      "escalated": false,
      "timestamp": "2026-03-20T14:23:00Z"
    }
  ],
  "correlations": [
    {
      "warning_id": "uuid",
      "info_signal_id": "uuid",
      "lag_minutes": 18,
      "shared_entities": ["wx-prod", "us-central1"]
    }
  ],
  "timestamp": "2026-03-20T14:45:00Z"
}
```

### GET `/api/defcon/history`

Get DEFCON level changes over time.

**Query Parameters**:
- `hours` (int, default: 24) - Number of hours to retrieve

**Response**:
```json
[
  {
    "level": 2,
    "reason": "Major multi-team issue",
    "score": 12.4,
    "started_at": "2026-03-20T14:23:00Z",
    "ended_at": "2026-03-20T14:45:00Z",
    "duration_minutes": 22,
    "teams_alerting": ["compute", "hobbes"],
    "warning_count": 12
  }
]
```

### GET `/api/defcon/channels`

Get active warning channels by team.

**Response**:
```json
{
  "compute": [
    {
      "channel": "compute-platform-warn",
      "warning_count": 5
    }
  ],
  "hobbes": [
    {
      "channel": "hobbes-warnings",
      "warning_count": 2
    }
  ]
}
```

### GET `/api/defcon/correlations`

Get detected lagged signal correlations.

**Query Parameters**:
- `hours` (int, default: 24) - Number of hours to retrieve

**Response**:
```json
[
  {
    "info_signal_id": "uuid",
    "warning_event_id": "uuid",
    "lag_minutes": 18.5,
    "confidence": 0.85,
    "shared_entities": ["wx-prod", "us-central1"],
    "detected_at": "2026-03-20T14:41:00Z"
  }
]
```

---

## Troubleshooting

### DEFCON Level Seems Wrong

**Issue**: DEFCON 3 but only 1 warning visible

**Causes**:
1. **Lag in display**: Widget polls every 1 minute, backend updates may be ahead
2. **Recently resolved warnings**: Warnings auto-cleared but DEFCON hasn't updated
3. **Hidden warnings**: Some warnings in channels you don't monitor

**Solution**:
- Check `/api/defcon/current` for full warning list
- Look at DEFCON history to see if level is dropping
- Verify all warning channels are synced

---

### False Alarms (DEFCON 2 for Minor Issues)

**Issue**: System frequently hits DEFCON 2 for non-critical issues

**Causes**:
1. **Thresholds too sensitive**: Score threshold for DEFCON 2 too low
2. **Channel weights too high**: Non-critical channels weighted like critical ones
3. **Keyword detection too broad**: Too many words trigger critical multiplier

**Solution**:
1. Analyze last 7 days of DEFCON 2 events
2. Identify common false alarm patterns
3. Adjust thresholds or channel weights
4. Refine critical keyword list

---

### Missed Incidents (Real Issues at DEFCON 4/5)

**Issue**: Real incident occurred but DEFCON stayed at 4 or 5

**Causes**:
1. **Warnings not captured**: Alerts in unmonitored channels
2. **Low channel weight**: Critical channel has low weight
3. **Missing keyword detection**: Alert text doesn't match keywords
4. **Single team incident**: No multi-team correlation to boost score

**Solution**:
1. Add missing channels to monitoring
2. Increase weight for critical channels
3. Add missing keywords to detection lists
4. Lower threshold for single-team critical alerts

---

### Lagged Correlations Not Detected

**Issue**: Deployment caused failures but no correlation shown

**Causes**:
1. **Lag window mismatch**: Actual lag outside 5-30 minute window
2. **Entity mismatch**: Different naming between info and warning
3. **Wrong channel**: Info signal in wrong Slack channel
4. **Timing**: Warning occurred before info signal logged

**Solution**:
1. Adjust `LAG_WINDOW_MIN` and `LAG_WINDOW_MAX`
2. Improve entity extraction (add more keywords/patterns)
3. Ensure `compute-platform-info` captures all deployments
4. Check timestamp accuracy in both sources

---

## Best Practices

### For On-Call Engineers

1. **Check DEFCON first**: Before diving into individual alerts, check overall DEFCON level
2. **Look for correlations**: If DEFCON is elevated, check for lagged signals (recent deployments?)
3. **Communicate early**: Post status updates in `#compute-platform` at DEFCON 3+
4. **Escalate appropriately**: Don't wait for DEFCON 1 to declare incidents
5. **Document patterns**: If you find a new correlation, update the system

### For Team Leads

1. **Review weekly**: Check DEFCON trends every week (are we always at 3-4?)
2. **Tune thresholds**: Adjust based on false alarms and missed incidents
3. **Add new channels**: As new teams/systems come online, add their channels
4. **Refine weights**: If a channel is always noisy, lower its weight

### For SREs

1. **Use DEFCON in runbooks**: Reference DEFCON levels in incident response procedures
2. **Include in postmortems**: Record DEFCON timeline in incident reports
3. **Automate responses**: Consider auto-creating ProdIssue tickets at DEFCON 1
4. **Monitor false alarms**: Track false positive rate and tune system

---

## Metrics & Monitoring

### System Health Metrics

Monitor DEFCON service itself:

- **Update frequency**: DEFCON should update every 1 minute
- **API latency**: `/current` endpoint should respond in <500ms
- **Data freshness**: Warning events should be <5 minutes old
- **Correlation detection**: 70%+ of lagged signals should be accurate

### DEFCON Distribution

Track how often each level occurs:

```
Target Distribution (healthy system):
DEFCON 5: 80-90%  (most of the time)
DEFCON 4: 5-15%   (occasional issues)
DEFCON 3: 1-5%    (rare but expected)
DEFCON 2: <1%     (infrequent incidents)
DEFCON 1: <0.1%   (rare critical incidents)
```

**Red Flags**:
- **DEFCON 4 >20%**: Too many warnings, system is noisy
- **DEFCON 3 >10%**: Thresholds too sensitive OR real platform issues
- **DEFCON 5 <70%**: Something is wrong with monitoring or system health

### False Alarm Rate

Track DEFCON 2/3 events that didn't require action:

```
False Alarm Rate = (False DEFCON 2/3) / (Total DEFCON 2/3)

Target: <10% false alarms
```

**Actions if high**:
- Review channel weights
- Refine keyword detection
- Adjust score thresholds

---

## Roadmap

### Planned Features

#### Phase 1 (Q2 2026)
- ✅ Core DEFCON calculation
- ✅ Dashboard widget
- ✅ DEFCON history tracking
- ✅ Lagged signal detection

#### Phase 2 (Q3 2026)
- [ ] Slack notifications on DEFCON level changes
- [ ] Automatic ProdIssue creation at DEFCON 1
- [ ] Team-specific DEFCON levels
- [ ] Mobile push notifications

#### Phase 3 (Q4 2026)
- [ ] Machine learning for threshold tuning
- [ ] Predictive DEFCON (forecast future levels)
- [ ] Integration with status page
- [ ] Custom DEFCON policies per team

### Future Ideas

- **DEFCON trends**: Long-term trend analysis (Are we getting more/less stable?)
- **Time-of-day patterns**: Adjust thresholds based on time (deployments vs off-hours)
- **Seasonal patterns**: Adjust for known busy periods
- **DEFCON runbook automation**: Auto-trigger runbooks at certain levels
- **Cross-platform DEFCON**: Separate DEFCON for WX, Jobs, G4, etc.

---

## FAQ

### Why "DEFCON"?

**Q**: Why use military terminology?

**A**: DEFCON is widely understood (thanks to pop culture), has clear severity levels (1-5), and implies "defense condition" which matches our use case (defensive monitoring). Plus, it's memorable and actionable ("we're at DEFCON 2" is clearer than "we have a score of 11.3").

### How often does DEFCON update?

**Q**: How frequently is DEFCON recalculated?

**A**: Every **1 minute** via background job. The dashboard widget polls every 1 minute, so you'll see updates within 1-2 minutes of a warning appearing.

### Can I customize thresholds for my team?

**Q**: Can I set different DEFCON thresholds for my team's channels?

**A**: Currently, thresholds are global. However, you can adjust **channel weights** to make your team's warnings more or less influential. Team-specific DEFCON levels are planned for Phase 2.

### What if my team's channel isn't monitored?

**Q**: How do I add my team's warning channel to DEFCON?

**A**: Edit `CHANNEL_WEIGHTS` in `backend/app/services/defcon_service.py`. Add your channel with an appropriate weight (0.2-0.5 for most teams). Submit a merge request or ask the Compute team.

### Does DEFCON replace PagerDuty?

**Q**: Should we stop using PagerDuty if we have DEFCON?

**A**: **No!** DEFCON is a **situational awareness** tool, not a replacement for alerting. PagerDuty still pages on-call for critical issues. DEFCON provides **context** about overall system health that PagerDuty doesn't.

### How do I test the system?

**Q**: Can I trigger a test DEFCON 2 to see how it works?

**A**: Yes! Use the test endpoint:
```bash
curl -X POST http://localhost:9000/api/warnings/test \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "compute-platform-warn",
    "alert_name": "test-critical-alert",
    "count": 10,
    "severity": "critical"
  }'
```

Wait 1 minute, then check `/api/defcon/current`. Remember to clean up test warnings after!

---

## Support

### Getting Help

- **Documentation**: This file + `DEFCON-service-implementation-plan.md`
- **Runbooks**: `/claude/projects/prodissue-notes/prodissue-claude.md`
- **Slack**: `#compute-platform` (mention @on-call or @aaryn)
- **Code**: `~/claude/dashboard/backend/app/services/defcon_service.py`

### Reporting Issues

If DEFCON is misbehaving:

1. **Capture context**:
   - Current DEFCON level + score
   - Recent warning events
   - Expected vs actual behavior

2. **Report in Slack**:
   ```
   DEFCON Issue Report:
   - Current: DEFCON 3 (score 7.2)
   - Expected: DEFCON 5 (only 1 minor warning)
   - Warnings: [list]
   - Screenshots: [attach]
   ```

3. **Create JIRA ticket**:
   - Project: COMPUTE
   - Component: Commander / DEFCON
   - Attach logs and screenshots

---

## Changelog

### v1.0 (March 20, 2026)
- Initial DEFCON system design
- Core scoring algorithm
- 5-level DEFCON scale
- Lagged signal detection
- Dashboard widget
- API endpoints

---

**Questions?** Ask in `#compute-platform` or see the implementation plan at:
`/Users/aaryn/claude/artifacts/20260320-DEFCON-service-implementation-plan.md`
