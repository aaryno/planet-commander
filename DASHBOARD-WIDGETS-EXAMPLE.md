# Dashboard Widgets Example

This document shows how to use all the Planet Commander widgets in a dashboard layout.

## All Available Widgets

From **Phase 2:**
- `SuggestedLinksCard` - Review and confirm auto-discovered entity links
- `BackgroundJobsCard` - Monitor background job execution

From **Phase 3:**
- `HealthAuditCard` - View context health distribution
- `StaleContextsCard` - Find and manage stale contexts
- `OrphanedEntitiesCard` - Find orphaned entities

## Example Dashboard Layout

```tsx
// app/commander/page.tsx
"use client";

import {
  SuggestedLinksCard,
  BackgroundJobsCard,
  HealthAuditCard,
  StaleContextsCard,
  OrphanedEntitiesCard,
} from "@/components/widgets";

export default function CommanderDashboard() {
  return (
    <div className="min-h-screen bg-zinc-950 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-zinc-100 mb-2">
            Planet Commander
          </h1>
          <p className="text-zinc-400">
            Automated context management and workflow automation
          </p>
        </div>

        {/* Top Row: Health Overview */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1">
            <HealthAuditCard />
          </div>
          <div className="lg:col-span-1">
            <StaleContextsCard />
          </div>
          <div className="lg:col-span-1">
            <OrphanedEntitiesCard />
          </div>
        </div>

        {/* Middle Row: Background Jobs & Suggested Links */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <BackgroundJobsCard />
          <SuggestedLinksCard />
        </div>
      </div>
    </div>
  );
}
```

## Two-Column Layout

For a more compact layout:

```tsx
export default function CommanderDashboard() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 p-6">
      {/* Left Column */}
      <div className="space-y-6">
        <HealthAuditCard />
        <StaleContextsCard />
        <BackgroundJobsCard />
      </div>

      {/* Right Column */}
      <div className="space-y-6">
        <SuggestedLinksCard />
        <OrphanedEntitiesCard />
      </div>
    </div>
  );
}
```

## Single Column Layout (Mobile-Friendly)

```tsx
export default function CommanderDashboard() {
  return (
    <div className="max-w-4xl mx-auto space-y-6 p-6">
      <HealthAuditCard />
      <SuggestedLinksCard />
      <StaleContextsCard />
      <BackgroundJobsCard />
      <OrphanedEntitiesCard />
    </div>
  );
}
```

## Widget Features

### Auto-Refresh
All widgets auto-refresh at different intervals:
- `HealthAuditCard`: 5 minutes
- `StaleContextsCard`: 5 minutes
- `OrphanedEntitiesCard`: 5 minutes
- `BackgroundJobsCard`: 1 minute
- `SuggestedLinksCard`: 5 minutes

### Manual Actions
Each widget has actions in the menu (⋮):
- **Health**: Refresh, Run Audit
- **Stale**: Refresh, Mark Orphaned (60d)
- **Orphaned**: Refresh
- **Jobs**: Refresh, Trigger [job_name]
- **Suggested**: Refresh, Confirm All

### Empty States
All widgets handle empty states gracefully:
- Show helpful messages
- Explain what will appear when data is available
- Provide context on how data is generated

## Integration with Context Pages

Widgets can also be used on context detail pages:

```tsx
// app/context/[id]/page.tsx
import { HealthAuditCard, SuggestedLinksCard } from "@/components/widgets";

export default function ContextPage({ params }: { params: { id: string } }) {
  return (
    <div className="space-y-6">
      {/* Context details... */}

      <div className="grid grid-cols-2 gap-6">
        <HealthAuditCard />
        <SuggestedLinksCard />
      </div>
    </div>
  );
}
```

## Customization

All widgets accept standard props from `ScrollableCard`:

```tsx
<HealthAuditCard
  className="custom-class"
  style={{ maxHeight: "500px" }}
/>
```

For more control, you can access the underlying data directly:

```tsx
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";

function CustomHealthWidget() {
  const { data, loading, error, refresh } = usePoll(
    () => api.healthAuditAll(),
    300_000 // 5 minutes
  );

  // Custom rendering...
}
```

## Performance Considerations

1. **Polling Intervals**: Widgets poll at different rates based on data volatility
2. **Lazy Loading**: Consider code splitting for large dashboards
3. **Conditional Rendering**: Only render widgets user has access to

```tsx
{canViewHealth && <HealthAuditCard />}
{canManageJobs && <BackgroundJobsCard />}
```

## Router Configuration

Add to your Next.js routing:

```tsx
// app/commander/page.tsx - Main dashboard
// app/health/page.tsx - Health-focused view
// app/automation/page.tsx - Automation-focused view
```

Each can show a different subset of widgets based on the page purpose.
