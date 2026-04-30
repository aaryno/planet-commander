# Planet Commander - Development Guide

**Repository**: `aaryno/planet-commander` (GitHub)
**Purpose**: All-in-one agent command center for cross-project workflows
**Stack**: Next.js (frontend) + FastAPI (backend) + PostgreSQL
**Changelog**: [CHANGELOG.md](CHANGELOG.md) — Development history with linked artifacts and pattern references

---

## Quick Start

### Running Locally (Recommended: Use Make)

```bash
cd ~/code/aaryn/planet-commander

# Start both backend + frontend (Ctrl+C stops both)
make start

# Or start individually:
make start-backend   # Backend: http://localhost:9000
make start-frontend  # Frontend: http://localhost:3000

# Stop all services
make stop

# See all available commands
make help
```

### Alternative: Manual Start

```bash
# Start all services (frontend, backend, database)
docker-compose up

# Or run individually:
cd frontend && npm run dev          # Frontend: http://localhost:3000
cd backend && uvicorn app.main:app  # Backend: http://localhost:9000
docker-compose up postgres          # Database: localhost:9432
```

### Development URLs

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Database**: postgresql://postgres:postgres@localhost:9432/planet_ops

---

## 🚀 Planet Commander Evolution (Phase 1 in Progress)

**Commander is evolving from a monitoring dashboard to a work context management platform.**

### What's Changing

**Current State**: Agent session display + JIRA filtering + deployment monitoring

**Future State (Planet Commander)**: Work context as primary abstraction, linking issues, chats, branches, worktrees, PRs, summaries, and audits into coherent operational contexts.

### Phase 1 Goals (Weeks 1-4)

**Deliverable**: Users can open any entity (JIRA ticket, chat, branch, worktree) and see a coherent linked context

**New Database Models**:
- `WorkContext` - Primary work abstraction
- `EntityLink` - Relationship graph
- `JiraIssue` - Cached JIRA issues
- `GitBranch` - Branch tracking
- `Worktree` - Worktree state tracking
- Extensions to `Agent` model for Chat

**New Backend Services**:
- `ContextResolverService` - Resolve entity → work context
- `EntityLinkService` - Create/manage links
- `BranchTrackingService` - Track branch state
- `WorktreeTrackingService` - Track worktree state

**New Frontend Components**:
- `ContextPanel` - Replaces ticket detail view
- `ContextHeader` - Title, status, health strip
- `HealthStrip` - Visual context health indicators
- `RelationshipList` - Display linked entities
- `LinkBadge` - Entity type badges

### Development Status

**Current Phase**: Phase 1 - Context Foundation
**Progress**: Planning complete, implementation starting
**Target**: 4 weeks (2 developers)

### For Developers

Follow the development rules below for all new code.

---

## 🏗️ Architecture

```
dashboard/
├── frontend/           # Next.js + React + TypeScript
│   ├── src/
│   │   ├── app/       # Next.js pages (routing)
│   │   ├── components/
│   │   │   ├── ui/            # 🔑 SHARED UI PRIMITIVES
│   │   │   ├── cards/         # Feature cards (JIRA, Slack, etc.)
│   │   │   ├── agents/        # Agent-specific components
│   │   │   └── ...
│   │   └── lib/       # API client, utilities
│   └── package.json
│
├── backend/           # FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── api/       # API routes
│   │   ├── models/    # Database models
│   │   ├── services/  # Business logic
│   │   └── main.py    # App entry point
│   └── requirements.txt
│
└── docker-compose.yml
```

---

## 🎨 Component Development Rules

### **RULE #1: Use Existing Components - Never Reinvent**

Before creating ANY new UI component:

1. ✅ **Check `frontend/src/components/ui/`** - Shared primitives live here
2. ✅ **Check shadcn/ui docs** - We use shadcn for base components
3. ✅ **Search for similar patterns** - `grep -r "ClassName" src/components/`

### **RULE #2: No Copy-Paste - Refactor to Configure**

If you find yourself copying code:

❌ **Bad - Copy/Paste**:
```tsx
// agents/ProjectAgents.tsx
<div className="bg-zinc-900 rounded-lg border border-zinc-800">
  <div className="p-4 border-b">Title</div>
  <div className="overflow-y-auto">{content}</div>
</div>

// cards/WXDeployments.tsx
<div className="bg-zinc-900 rounded-lg border border-zinc-800">
  <div className="p-4 border-b">Title</div>
  <div className="overflow-y-auto">{content}</div>
</div>
```

✅ **Good - Shared Component**:
```tsx
// components/ui/scrollable-card.tsx
export function ScrollableCard({ title, children, ... }) { ... }

// Usage everywhere:
<ScrollableCard title="Agents">{content}</ScrollableCard>
<ScrollableCard title="Deployments">{content}</ScrollableCard>
```

**Recent Example**: See `ScrollableCard` in `frontend/src/components/ui/scrollable-card.tsx`

### **RULE #3: Make Components Configurable, Not Specialized**

Design for reuse through props, not duplication:

❌ **Bad - Hardcoded**:
```tsx
function AgentCard({ agent }) {
  return <div className="p-4 bg-zinc-900">...</div>;
}

function DeploymentCard({ deployment }) {
  return <div className="p-4 bg-zinc-900">...</div>; // Same layout!
}
```

✅ **Good - Configurable**:
```tsx
function Card({ title, icon, children, variant = "default" }) {
  const styles = {
    default: "bg-zinc-900",
    highlighted: "bg-blue-900/20",
  };
  return <div className={`p-4 ${styles[variant]}`}>...</div>;
}
```

### **RULE #4: Use Component Libraries**

We use **shadcn/ui** for primitives. DO NOT recreate these:

#### Available Components (from shadcn)

| Component | Import | Use Case |
|-----------|--------|----------|
| **Badge** | `@/components/ui/badge` | Labels, status indicators |
| **Button** | `@/components/ui/button` | All buttons (with variants) |
| **Card** | `@/components/ui/card` | Container base (CardHeader, CardContent) |
| **DropdownMenu** | `@/components/ui/dropdown-menu` | Context menus, actions |
| **Input** | `@/components/ui/input` | Text inputs, search bars |
| **Separator** | `@/components/ui/separator` | Dividers (from react-resizable-panels) |
| **Toast** | `@/components/ui/toast` | Notifications |

**Adding new shadcn components**:
```bash
npx shadcn@latest add <component-name>
```

#### Commander-Specific Shared Components

| Component | Location | Use Case |
|-----------|----------|----------|
| **ScrollableCard** | `@/components/ui/scrollable-card` | Cards with sticky headers + scrollable content |
| **CardShell** | `@/components/cards/CardShell` | Simple cards (legacy, migrate to ScrollableCard) |

---

## 🔗 Work Context Integration Pattern

**New to integrations?** This pattern lets you add new entity types to work contexts in ~30 minutes.

### Overview

Commander uses an **EntityLink-based architecture** to connect work contexts with external entities (PagerDuty incidents, Grafana alerts, GitLab MRs, artifacts, etc.).

**Key Principle**: Build infrastructure once (models, background jobs, UI cards), then wire into work contexts with minimal code.

**Proven Success**: 4 integrations completed in 2h 10min (average ~30 min each).

### Prerequisites

Before integrating an entity type, ensure you have:
1. ✅ **Database model** - SQLAlchemy model for the entity
2. ✅ **Background job** - Syncs data from external source
3. ✅ **EntityLink creation** - Job that creates links to JIRA/chats
4. ✅ **UI card component** - React component to display entity

**If these exist**, integration takes ~30 minutes. **If not**, build infrastructure first (~1-2 days), then integrate.

### The 5-Step Pattern

Follow these steps in order. Each integration adds ~50-125 lines of code.

#### Step 1: Update Context Resolver (~5 min)

**File**: `backend/app/services/context_resolver.py`

**Changes**:
```python
# 1. Add import
from app.models import YourEntityModel

# 2. Add field to ResolvedContext
@dataclass
class ResolvedContext:
    your_entities: list[YourEntityModel] = field(default_factory=list)
    # ... other fields

# 3. Add fetching logic to _resolve_context_graph()
async def _resolve_context_graph(self, context_id: uuid.UUID) -> ResolvedContext:
    # ... existing entity fetching ...

    # Find EntityLinks (choose correct direction!)
    links_result = await self.db.execute(
        select(EntityLink).where(
            EntityLink.from_id.in_(entity_ids)  # or to_id for reverse
            & (EntityLink.to_type == "your_entity_type")  # or from_type
        )
    )
    links = links_result.scalars().all()

    # Extract IDs and fetch entities
    entity_ids = [uuid.UUID(link.to_id) for link in links]  # or from_id

    if entity_ids:
        entities_result = await self.db.execute(
            select(YourEntityModel).where(YourEntityModel.id.in_(entity_ids))
        )
        resolved.your_entities = list(entities_result.scalars().all())

    return resolved
```

**Link Direction Guide**:
- **Entity referenced by work** (PagerDuty, Artifacts, MRs): Use `to_type`, extract `link.to_id`
- **Entity referencing work** (Grafana alerts): Use `from_type`, extract `link.from_id`

#### Step 2: Update Context API (~10 min)

**File**: `backend/app/api/contexts.py`

**Changes**:
```python
# 1. Add response model
class YourEntityResponse(BaseModel):
    """Your entity in context response."""
    id: str
    # ... entity-specific fields

# 2. Add to ContextResponse
class ContextResponse(BaseModel):
    your_entities: list[YourEntityResponse] = Field(default_factory=list)
    # ... other fields

# 3. Serialize in _build_context_response()
def _build_context_response(resolved: Any) -> ContextResponse:
    return ContextResponse(
        your_entities=[
            YourEntityResponse(
                id=str(entity.id),
                # ... map all fields
            )
            for entity in resolved.your_entities
        ],
        # ... other fields
    )
```

#### Step 3: Update Frontend Types (~2 min)

**File**: `frontend/src/lib/api.ts`

**Changes**:
```typescript
// Add entity interface (if not already defined)
export interface YourEntityInContext {
  id: string;
  // ... entity-specific fields
}

// Add to ContextResponse
export interface ContextResponse {
  your_entities: YourEntityInContext[];
  // ... other fields
}
```

#### Step 4: Update ContextPanel (~10 min)

**File**: `frontend/src/components/context/ContextPanel.tsx`

**Changes**:
```tsx
// 1. Import card component and icon
import { YourEntityCard } from "@/components/your-entity/YourEntityCard";
import { YourIcon } from "lucide-react";

// 2. Add tab to navigation
<TabsTrigger value="your-entities">
  <YourIcon className="w-3 h-3 mr-1" />
  Your Entities ({context.your_entities.length})
</TabsTrigger>

// 3. Add Overview section
{context.your_entities.length > 0 && (
  <div className="space-y-2">
    <h3 className="text-xs font-semibold text-zinc-400">Your Entities</h3>
    {context.your_entities.map(entity => (
      <YourEntityCard key={entity.id} entity={entity} />
    ))}
  </div>
)}

// 4. Add dedicated tab
<TabsContent value="your-entities" className="mt-4 space-y-2">
  {context.your_entities.length === 0 ? (
    <p className="text-sm text-zinc-500 text-center py-8">
      No entities linked to this context
    </p>
  ) : (
    context.your_entities.map(entity => (
      <YourEntityCard key={entity.id} entity={entity} />
    ))
  )}
</TabsContent>
```

#### Step 5: Create Completion Artifact (~5-10 min)

**File**: `~/claude/artifacts/YYYYMMDD-HHMM-your-entity-integration-complete.md`

Document:
- What was built (overview, key achievements)
- How it works (data flow, EntityLink integration)
- Files modified (with line counts)
- Testing steps (SQL queries, API calls, UI verification)
- Link direction pattern used

**Template**: See existing integration artifacts in `~/claude/artifacts/`

### Link Direction Patterns

Understanding link direction is **critical** for correct EntityLink queries:

| Pattern | Example Entities | Link Direction | Query |  ID Field |
|---------|------------------|----------------|-------|-----------|
| **Referenced by work** | PagerDuty, Artifacts, MRs | JIRA → entity | `to_type = "entity"` | `link.to_id` |
| **Referencing work** | Grafana alerts | entity → JIRA | `from_type = "entity"` | `link.from_id` |

**Examples**:
```python
# Pattern A: JIRA → entity (PagerDuty, Artifacts, MRs)
links = await db.execute(
    select(EntityLink).where(
        EntityLink.from_id.in_(jira_ids)  # FROM JIRA
        & (EntityLink.to_type == "pagerduty_incident")  # TO incident
    )
)
incident_ids = [uuid.UUID(link.to_id) for link in links]

# Pattern B: entity → JIRA (Grafana alerts)
links = await db.execute(
    select(EntityLink).where(
        EntityLink.to_id.in_(jira_ids)  # TO JIRA
        & (EntityLink.from_type == "grafana_alert")  # FROM alert
    )
)
alert_ids = [uuid.UUID(link.from_id) for link in links]
```

### Integration Checklist

Use this checklist when integrating a new entity type:

- [ ] **Prerequisites verified**
  - [ ] Database model exists
  - [ ] Background sync job exists
  - [ ] EntityLink creation job exists
  - [ ] UI card component exists

- [ ] **Step 1: Context Resolver**
  - [ ] Imported entity model
  - [ ] Added field to ResolvedContext
  - [ ] Added fetching logic (correct link direction!)
  - [ ] Tested query returns entities

- [ ] **Step 2: Context API**
  - [ ] Created response model
  - [ ] Added to ContextResponse
  - [ ] Updated _build_context_response()
  - [ ] Tested API returns entities

- [ ] **Step 3: Frontend Types**
  - [ ] Created/updated entity interface
  - [ ] Added to ContextResponse
  - [ ] TypeScript compiles without errors

- [ ] **Step 4: ContextPanel**
  - [ ] Imported card component
  - [ ] Added tab with icon + count
  - [ ] Added Overview section
  - [ ] Added dedicated tab
  - [ ] Tested UI displays entities

- [ ] **Step 5: Documentation**
  - [ ] Created completion artifact
  - [ ] Documented link direction
  - [ ] Included testing steps
  - [ ] Updated PROGRESS.md

### Common Mistakes

❌ **Wrong link direction**
```python
# Wrong: Querying from_type for entities that link TO work
select(EntityLink).where(EntityLink.from_type == "pagerduty_incident")
# Should be: to_type (because JIRA → incident)
```

❌ **Extracting from wrong ID field**
```python
# Wrong: Extracting from_id when link direction is JIRA → entity
incident_ids = [link.from_id for link in links]
# Should be: to_id
```

❌ **Forgetting to add tab**
- Entity shows in Overview but no dedicated tab
- Users expect dedicated tabs for all entity types

❌ **Not testing EntityLink existence**
- Assumes links exist but background job hasn't run yet
- Always verify EntityLinks exist in database first

### Success Metrics

After integration, you should see:
- ✅ Entities visible in context Overview tab
- ✅ Dedicated tab with entity count badge
- ✅ Entity cards display correctly
- ✅ Clicking links opens external system
- ✅ No TypeScript errors
- ✅ No console errors
- ✅ Integration took < 1 hour

### Example Integrations

Study the existing integrations in the codebase for reference:
- **PagerDuty Incidents** — Pattern A (JIRA → incident): `context_resolver.py`
- **Grafana Alerts** — Pattern B (alert → JIRA): `context_resolver.py`
- **Artifacts** — Pattern A (JIRA → artifact): `context_resolver.py`
- **GitLab MRs** — Pattern A (JIRA → MR): `context_resolver.py`

---

## 🎯 Common Patterns

### Scrollable Cards with Sticky Filters

Use `ScrollableCard` for any card with:
- Sticky header (title + menu)
- Sticky filters/search bar
- Scrollable content

```tsx
import { ScrollableCard } from "@/components/ui/scrollable-card";

const stickyHeader = (
  <div className="space-y-3">
    <Input placeholder="Search..." />
    <div className="flex justify-between">
      <span>{count} items</span>
      <Button onClick={refresh}>Refresh</Button>
    </div>
  </div>
);

<ScrollableCard
  title="My Feature"
  icon={<Icon />}
  menuItems={[{ label: "Refresh", onClick: refetch }]}
  stickyHeader={stickyHeader}
>
  <div className="space-y-2">
    {items.map(item => <ItemCard key={item.id} {...item} />)}
  </div>
</ScrollableCard>
```

**Example**: See [ProjectAgents.tsx](frontend/src/components/agents/ProjectAgents.tsx)

### API Data Fetching with Polling

Use the `usePoll` hook for auto-refreshing data:

```tsx
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";

const fetcher = useCallback(() => api.myEndpoint(), []);
const { data, loading, error, refetch } = usePoll(
  fetcher,
  300_000 // 5 minutes
);
```

### Color Palette

Stick to the established color scheme:

```tsx
// Base colors
bg-zinc-900       // Card backgrounds
bg-zinc-800       // Hover states, borders
border-zinc-800   // Card borders
text-zinc-200     // Primary text
text-zinc-400     // Secondary text
text-zinc-500     // Muted text

// Status colors
bg-emerald-500/20  text-emerald-400  // Success, healthy
bg-blue-500/20     text-blue-400     // Info, in-progress
bg-amber-500/20    text-amber-400    // Warning
bg-red-500/20      text-red-400      // Error, danger

// Tier badges (WX example)
bg-slate-600/20    text-slate-400    // Staging
bg-red-600/20      text-red-400      // Production
```

---

## 🗂️ File Organization

### Frontend Structure

```
src/
├── app/                    # Pages (Next.js routing)
│   ├── page.tsx           # Dashboard (/)
│   ├── wx/page.tsx        # WX dashboard (/wx)
│   └── temporal/page.tsx  # Temporal dashboard (/temporal)
│
├── components/
│   ├── ui/                # 🔑 SHARED PRIMITIVES (add new reusables here)
│   │   ├── badge.tsx
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── scrollable-card.tsx  # Commander-specific shared
│   │   └── ...
│   │
│   ├── cards/             # Feature cards (JIRA, Slack, Deployments, etc.)
│   │   ├── JiraSummary.tsx
│   │   ├── WXDeployments.tsx
│   │   └── ...
│   │
│   ├── agents/            # Agent-related components
│   │   ├── ProjectAgents.tsx
│   │   ├── AgentRow.tsx
│   │   └── ChatView.tsx
│   │
│   └── <feature>/         # Other feature-specific components
│
└── lib/
    ├── api.ts             # API client + TypeScript types
    ├── polling.ts         # usePoll hook
    └── utils.ts           # Utilities
```

### Backend Structure

```
app/
├── api/                   # API routes
│   ├── agents.py
│   ├── jira.py
│   ├── wx.py
│   └── ...
│
├── services/              # Business logic (keep routes thin!)
│   ├── agent_service.py
│   ├── jira_service.py
│   ├── wx_deployment_service.py
│   └── ...
│
├── models/                # SQLAlchemy models
│   ├── agent.py
│   ├── page_layout.py
│   └── ...
│
└── main.py                # FastAPI app initialization
```

---

## 🚀 Adding New Features

### Checklist for New Cards/Components

- [ ] **Search for existing components** - Check `components/ui/` and shadcn docs
- [ ] **Reuse existing patterns** - See JIRA Summary, Agents, Deployments for examples
- [ ] **Use `ScrollableCard`** if you need sticky headers + scrollable content
- [ ] **Use shadcn components** for buttons, badges, inputs, dropdowns
- [ ] **Add TypeScript types** to `lib/api.ts`
- [ ] **Use `usePoll` hook** for auto-refreshing data
- [ ] **Follow color palette** - Don't invent new colors
- [ ] **Keep backend routes thin** - Business logic goes in `services/`
- [ ] **Document new patterns** - Create a `FEATURE-NAME-IMPLEMENTATION.md` artifact

### Example: Adding a New Card

```tsx
// 1. Check if similar card exists - reuse pattern
// 2. Use ScrollableCard for consistent layout
// 3. Use shadcn components for UI primitives

import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";

export function MyNewCard() {
  const { data, loading, error, refetch } = usePoll(
    () => api.myEndpoint(),
    300_000 // 5 min
  );

  return (
    <ScrollableCard
      title="My Feature"
      icon={<Icon />}
      menuItems={[{ label: "Refresh", onClick: refetch }]}
    >
      {loading && <p className="text-xs text-zinc-500">Loading...</p>}
      {error && <p className="text-xs text-red-400">Error!</p>}
      {data && (
        <div className="space-y-2">
          {data.items.map(item => (
            <div key={item.id} className="p-2 rounded border border-zinc-800">
              <Badge>{item.status}</Badge>
              {item.name}
            </div>
          ))}
        </div>
      )}
    </ScrollableCard>
  );
}
```

---

## 📚 Reference Documentation

### Implementation Guides

Implementation docs are kept in your personal project notes directory
(not committed to the repo). See existing feature code for patterns.

### Tech Stack

- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: FastAPI, SQLAlchemy, PostgreSQL
- **State**: React hooks (usePoll for polling)
- **Styling**: Tailwind + custom Zinc color palette
- **Icons**: Lucide React

---

## 🎓 Learning Resources

### shadcn/ui Documentation
- **Website**: https://ui.shadcn.com/
- **Components**: https://ui.shadcn.com/docs/components
- **Installation**: Already configured in this project

### Tailwind CSS
- **Docs**: https://tailwindcss.com/docs
- **Colors**: We use `zinc` scale for most components

### Next.js
- **App Router**: https://nextjs.org/docs/app
- **Data Fetching**: We use client-side polling (not Next.js SSR patterns)

---

## ⚠️ Common Mistakes to Avoid

### ❌ Don't Reinvent Existing Components

```tsx
// ❌ Bad - Creating custom button
<div
  className="px-3 py-1 bg-blue-500 rounded cursor-pointer"
  onClick={...}
>
  Click me
</div>

// ✅ Good - Use Button component
import { Button } from "@/components/ui/button";
<Button variant="default" onClick={...}>Click me</Button>
```

### ❌ Don't Copy-Paste Card Structures

```tsx
// ❌ Bad - Copy/paste card layout
<div className="bg-zinc-900 rounded-lg border border-zinc-800">
  <div className="p-4 border-b border-zinc-800">
    <h2>Title</h2>
  </div>
  <div className="p-4">{content}</div>
</div>

// ✅ Good - Use ScrollableCard or CardShell
<ScrollableCard title="Title">{content}</ScrollableCard>
```

### ❌ Don't Hardcode Values That Should Be Props

```tsx
// ❌ Bad
function AgentCard({ agent }) {
  return <div className="p-4">...</div>;
}

function TaskCard({ task }) {
  return <div className="p-4">...</div>; // Same padding!
}

// ✅ Good - Make a configurable component
function ItemCard({ title, children, variant = "default" }) {
  return <div className={`p-4 ${variant}`}>{children}</div>;
}
```

### ❌ Don't Invent New Colors

```tsx
// ❌ Bad - Random colors
<div className="bg-purple-900 text-yellow-200">...</div>

// ✅ Good - Use established palette
<div className="bg-zinc-900 text-zinc-200">...</div>
```

---

## 🔍 Before You Code - Checklist

1. **Does this component already exist?**
   - Check `components/ui/`
   - Check shadcn/ui docs
   - Grep the codebase

2. **Is there a similar pattern I can follow?**
   - Look at existing cards (JIRA, Agents, Deployments)
   - Check recent implementation docs

3. **Can I make an existing component more configurable instead of creating a new one?**
   - Add props to existing component
   - Create variants (not new components)

4. **Am I following the established patterns?**
   - Using `ScrollableCard` for scrollable content?
   - Using shadcn components for primitives?
   - Using `usePoll` for data fetching?
   - Following the color palette?

---

## 🤝 Contributing

When adding new features:

1. **Follow these rules** - Reuse, don't reinvent
2. **Write a `*-IMPLEMENTATION.md`** - Document what you built
3. **Update this CLAUDE.md** if you create new shared patterns
4. **Add TypeScript types** to `lib/api.ts`

---

**Questions?** Check existing implementation docs or ask the team.

**Found a pattern worth sharing?** Add it to this guide and create a shared component!
