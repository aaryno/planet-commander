# DEFCON Quick Reference Card

**Last Updated**: March 20, 2026

---

## DEFCON Levels at a Glance

| Level | Status | Score | Action | Communication |
|-------|--------|-------|--------|---------------|
| **🔴 1** | **Platform-wide incident** | 15+ | Declare ProdIssue, war room | #production-incident-alerts, status page |
| **🟠 2** | **Major multi-team issue** | 10-14.9 | Multi-team coordination | #compute-platform, incident thread |
| **🟡 3** | **Significant warnings** | 6-9.9 | Active investigation | #compute-platform status update |
| **🔵 4** | **Minor warnings** | 3-5.9 | Monitor | None unless persistent |
| **🟢 5** | **Normal operations** | 0-2.9 | None | None |

---

## Quick Response Guide

### DEFCON 5 → 4
- ✅ Check warnings in `/warnings` page
- ✅ Wait 5 minutes (auto-resolve?)
- ✅ Investigate if persistent

### DEFCON 4 → 3
- ✅ Post in `#compute-platform`: "DEFCON 3: Investigating [alerts]"
- ✅ Check for recent deployments (lagged signals)
- ✅ Create JIRA if not auto-resolving

### DEFCON 3 → 2
- ✅ Multi-team coordination
- ✅ Create Slack incident thread
- ✅ Consider ProdIssue if user impact

### DEFCON 2 → 1
- ✅ **DECLARE PRODISSUE IMMEDIATELY**
- ✅ Post in `#production-incident-alerts`
- ✅ Activate incident response
- ✅ Update status page

---

## Channel Weights (Reference)

| Channel | Weight | Team | Notes |
|---------|--------|------|-------|
| `compute-platform-warn` | 1.0 | Compute | Direct alerts |
| `hobbes` / `hobbes-warnings` | **1.5** | Hobbes | **Upstream** - infrastructure |
| `compute-platform-info` | 0.5 | Compute | Lagged signals (deployments) |
| `delta-warn` | 0.3 | Delta | Cross-team |
| `discovery-and-delivery-warn` | 0.3 | DnD | Cross-team |

---

## Scoring Multipliers

### Severity Keywords
- **Critical (3.0×)**: `outage`, `down`, `failed`, `critical`, `unavailable`
- **Warning (1.5×)**: `degraded`, `slow`, `high`, `low`, `latency`

### Escalation
- **PagerDuty escalated**: 2.0×
- **High probability (>80%)**: 1.5×

### Multi-Team
- **4+ teams**: 2.0×
- **3 teams**: 1.5×
- **2 teams**: 1.2×

### Special Combinations
- **Compute + Hobbes**: 1.5× (infrastructure cascading!)
- **Compute + DataPipeline**: 1.3× (Jobs impact)

---

## Lagged Signals

**What**: Infrastructure changes → failures within 5-30 minutes

**Example**:
```
14:00 - compute-platform-info: "GKE node pool update"
14:18 - compute-platform-warn: "WX tasks OOMKilled"
        ↑ Lagged correlation (18 min)
```

**Common Patterns**:
- Node pool update → Pod OOM (10-20 min)
- Workload Identity change → Auth failures (5-15 min)
- Network policy → Connection timeouts (5-10 min)

**Why It Matters**: Quickly identify deployment-related root causes

---

## API Quick Reference

```bash
# Current DEFCON
curl http://localhost:9000/api/defcon/current

# 24-hour history
curl http://localhost:9000/api/defcon/history

# Active channels by team
curl http://localhost:9000/api/defcon/channels

# Lagged correlations
curl http://localhost:9000/api/defcon/correlations
```

---

## Dashboard Locations

- **Main widget**: `/` (home page, top left)
- **History**: `/` (home page, second row)
- **Warning details**: `/warnings` page
- **Full docs**: `/Users/aaryn/claude/dashboard/DEFCON.md`

---

## Common Issues

### DEFCON stuck at 3 with no visible warnings
→ Check `/api/defcon/current` for full warning list (widget may be cached)

### False DEFCON 2 alarms
→ Thresholds too sensitive, tune in `defcon_service.py`

### Missed real incidents (stayed at DEFCON 4/5)
→ Add missing channels or increase weights for critical channels

### No lagged correlations detected
→ Adjust `LAG_WINDOW_MIN`/`MAX` or improve entity matching

---

## When to Escalate

| Scenario | Level | Action |
|----------|-------|--------|
| Single warning, auto-resolving | 4 | Wait |
| Multiple warnings, single team | 3 | Investigate |
| Multiple teams alerting | 2 | Coordinate |
| Confirmed user impact | 2 | Consider ProdIssue |
| Critical services down | 1 | **Declare ProdIssue** |
| Multiple services down | 1 | **Declare ProdIssue** |

---

## Key Commands

### Check current DEFCON
```bash
curl http://localhost:9000/api/defcon/current | jq '.level'
```

### Create test warnings (testing only!)
```bash
curl -X POST http://localhost:9000/api/warnings/test \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "compute-platform-warn",
    "count": 5,
    "severity": "critical"
  }'
```

### View DEFCON history
```bash
curl http://localhost:9000/api/defcon/history?hours=24 | jq
```

---

## Support Channels

- **Slack**: `#compute-platform`
- **On-call**: Mention `@on-call` in Slack
- **Docs**: `/Users/aaryn/claude/dashboard/DEFCON.md`
- **Code**: `backend/app/services/defcon_service.py`

---

**Print this card and keep it handy! 📋**
