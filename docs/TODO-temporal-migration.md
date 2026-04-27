# TODO: Migrate Temporal to ProjectDashboard

## Goal
Replace the custom `TemporalCommandCenter` page with the generic `ProjectDashboard` component, so Temporal gets the same workspace sidebar, dynamic config, and consistent UX as WX/G4/Jobs.

## Current State
- **`frontend/src/app/temporal/page.tsx`** — Custom 153-line component, NOT using ProjectDashboard
- **9 Temporal-specific components** in `frontend/src/components/temporal/`:
  - `NeedsAttentionBanner.tsx` — Temporal-specific alert banner
  - `KeyHealth.tsx` — API key health metrics
  - `UnansweredSlack.tsx` — Unanswered Slack messages
  - `SlackSentiment.tsx` — Sentiment analysis card
  - `TemporalJira.tsx` — Temporal JIRA view
  - `TemporalMRs.tsx` — Temporal MR list
  - `TemporalUsers.tsx` — Temporal user/tenant list
  - `UsageMetrics.tsx` — Usage metrics dashboard
  - `PerformanceMetrics.tsx` — Performance metrics
- **Temporal backend APIs** in `backend/app/api/temporal.py` — dedicated endpoints for keys, metrics, tenants
- **Temporal project** already exists in DB (`key: "temporal"`)

## Migration Steps

### Step 1: Convert temporal/page.tsx to use ProjectDashboard
```tsx
// Replace:
import { TemporalCommandCenter } from "...";
export default function TemporalPage() { return <TemporalCommandCenter />; }

// With:
import { ProjectDashboard } from "@/components/projects/ProjectDashboard";
export default function TemporalPage() { return <ProjectDashboard projectKey="temporal" />; }
```

### Step 2: Register Temporal-specific cards as extra cards
The ProjectDashboard `buildCards()` function renders cards based on project config.
Temporal needs custom cards beyond the standard JIRA/MRs/Agents/Deploy set.

Options:
- **A) Add a `customCards` prop to ProjectDashboard** — Temporal page passes its unique cards
- **B) Make cards pluggable via project config** — Project entity has a `custom_cards` JSONB field that lists which extra card components to render
- **C) Keep temporal components but render inside ProjectDashboard grid** — Register them in the card map

Recommended: **Option A** — minimal change, Temporal page wraps ProjectDashboard with extra cards.

### Step 3: Decide which Temporal components to keep vs generalize
| Component | Keep as Temporal-specific? | Could generalize? |
|-----------|--------------------------|-------------------|
| `NeedsAttentionBanner` | Keep — unique attention logic | No |
| `KeyHealth` | Keep — Temporal API key monitoring | No |
| `UnansweredSlack` | Generalize — useful for any project | Yes → generic "Unanswered Threads" card |
| `SlackSentiment` | Keep — niche feature | No |
| `TemporalJira` | Remove — use standard JiraSummary | Yes, already replaced |
| `TemporalMRs` | Remove — use standard OpenMRs | Yes, already replaced |
| `TemporalUsers` | Keep — Temporal tenant management | No |
| `UsageMetrics` | Keep — Temporal-specific metrics | Could generalize to "Project Metrics" |
| `PerformanceMetrics` | Keep — Temporal-specific | No |

### Step 4: Update project config
Ensure the `temporal` project in DB has:
- `deployment_config` set (if applicable)
- `grafana_dashboards` populated
- `jira_default_filters.label_filters` set to `["temporal"]`

### Step 5: Clean up
- Remove `frontend/src/app/temporal/page.tsx` custom implementation
- Keep `frontend/src/components/temporal/` for Temporal-specific cards
- Update sidebar nav (already dynamic from API)

## Estimated Effort
- Step 1-2: 1-2 hours
- Step 3: 2-3 hours (deciding + refactoring)
- Step 4-5: 30 min
- **Total: 4-6 hours**

## Dependencies
- ProjectDashboard must support custom/extra cards (Step 2)
- Temporal backend APIs remain unchanged
