# Commander Development Workflow

**Purpose**: Step-by-step workflow for building features in Commander while adhering to component reuse guidelines.

**Date**: 2026-03-17

---

## Pre-Development Checklist

Before writing ANY code, complete this checklist:

### 1. **Read the Guidelines** (First Time Only)
- [ ] Read [CLAUDE.md](./CLAUDE.md) - Complete development guide
- [ ] Review [SCROLLABLE-CARD-COMPONENT.md](./SCROLLABLE-CARD-COMPONENT.md) - Example of shared component pattern
- [ ] Understand the 4 Core Rules:
  - ✅ Use existing components - never reinvent
  - ✅ No copy-paste - refactor to configure
  - ✅ Make components configurable, not specialized
  - ✅ Use component libraries (shadcn/ui)

### 2. **Component Discovery** (Every Feature)
- [ ] Check `frontend/src/components/ui/` for existing shared components
- [ ] Check [shadcn/ui docs](https://ui.shadcn.com/docs/components) for available primitives
- [ ] Search codebase for similar patterns: `grep -r "ClassName" src/components/`
- [ ] Review recent implementation docs for examples

### 3. **Design Decision**
- [ ] Can I use an existing component as-is? → **Use it**
- [ ] Can I extend an existing component with props? → **Add props**
- [ ] Do I need a new shared component? → **Create it in `components/ui/`**
- [ ] Is this truly feature-specific? → **Create in feature folder**

---

## Development Workflow

### Phase 1: Research & Planning

1. **Identify Requirements**
   - What UI elements do you need? (cards, badges, buttons, inputs, etc.)
   - What layout pattern? (sticky header, scrollable content, filters, etc.)
   - What data sources? (API endpoints, polling intervals, etc.)

2. **Map to Existing Components**
   ```bash
   # Check for existing components
   ls frontend/src/components/ui/

   # Search for similar usage
   grep -r "ScrollableCard" frontend/src/components/
   grep -r "usePoll" frontend/src/components/
   ```

3. **Document Your Approach**
   - Which existing components will you use?
   - Which props do you need to add?
   - What's truly new vs. configurable existing?

### Phase 2: Implementation

#### A. Using Existing Components

**Example: Building a new card with sticky filters**

```tsx
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// ✅ Good - Compose existing components
const stickyHeader = (
  <div className="space-y-3">
    <Input placeholder="Search..." value={search} onChange={setSearch} />
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
    {items.map(item => (
      <div key={item.id}>
        <Badge>{item.status}</Badge>
        {item.name}
      </div>
    ))}
  </div>
</ScrollableCard>
```

#### B. Extending Existing Components

**When to extend**: You need a small variation of an existing component.

```tsx
// ❌ Bad - Copy component and modify
// ✅ Good - Add props to existing component

// In scrollable-card.tsx:
interface ScrollableCardProps {
  // ... existing props
  variant?: "default" | "compact" | "wide";  // Add new prop
}

// Usage:
<ScrollableCard variant="compact" ... />
```

#### C. Creating New Shared Components

**When to create**: Pattern appears in 2+ places.

**Steps**:
1. Create in `frontend/src/components/ui/`
2. Make it configurable via props (not hardcoded)
3. Use TypeScript interfaces for props
4. Follow established color palette
5. Document in a `*-IMPLEMENTATION.md` file

**Template**:
```tsx
// frontend/src/components/ui/my-component.tsx

import { ReactNode } from "react";

interface MyComponentProps {
  title: string;
  variant?: "default" | "highlighted";
  children: ReactNode;
  className?: string;
}

export function MyComponent({
  title,
  variant = "default",
  children,
  className = "",
}: MyComponentProps) {
  const variantStyles = {
    default: "bg-zinc-900",
    highlighted: "bg-blue-900/20",
  };

  return (
    <div className={`${variantStyles[variant]} ${className}`}>
      <h3>{title}</h3>
      {children}
    </div>
  );
}
```

### Phase 3: Review & Documentation

1. **Self-Review Checklist**
   - [ ] No copy-pasted code (DRY)
   - [ ] All UI primitives from shadcn/ui (Button, Badge, Input, etc.)
   - [ ] Proper TypeScript interfaces
   - [ ] Following color palette (zinc-900, zinc-800, etc.)
   - [ ] Components are configurable, not specialized

2. **Create Implementation Doc** (for significant features)
   ```bash
   # Create artifact documenting your work
   touch dashboard/MY-FEATURE-IMPLEMENTATION.md
   ```

   **Include**:
   - Problem solved
   - Components used/created
   - Props added
   - Usage examples
   - Migration notes (if refactoring existing code)

3. **Update CLAUDE.md** (if creating new patterns)
   - Add new shared component to "Commander-Specific Shared Components" table
   - Add usage example to "Common Patterns" section
   - Document any new guidelines discovered

---

## Common Patterns Reference

### Pattern: Sticky Filters + Scrollable Content

**Use**: `ScrollableCard` with `stickyHeader` prop

**Example**: See [JiraSummary.tsx](frontend/src/components/cards/JiraSummary.tsx)

```tsx
const stickyHeader = (
  <div className="space-y-2">
    {/* Filters, search, etc. */}
  </div>
);

<ScrollableCard stickyHeader={stickyHeader}>
  {/* Scrollable items */}
</ScrollableCard>
```

### Pattern: Auto-Refreshing Data

**Use**: `usePoll` hook

**Example**: See [WXDeployments.tsx](frontend/src/components/cards/WXDeployments.tsx)

```tsx
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";

const fetcher = useCallback(() => api.myEndpoint(), []);
const { data, loading, error, refetch } = usePoll(
  fetcher,
  300_000 // 5 minutes
);
```

### Pattern: Status Badges

**Use**: `Badge` from shadcn/ui

**Colors**: Follow established palette

```tsx
import { Badge } from "@/components/ui/badge";

// Success/Healthy
<Badge className="bg-emerald-500/20 text-emerald-400">Active</Badge>

// Warning
<Badge className="bg-amber-500/20 text-amber-400">Degraded</Badge>

// Error
<Badge className="bg-red-500/20 text-red-400">Down</Badge>

// Info
<Badge className="bg-blue-500/20 text-blue-400">Pending</Badge>

// Neutral
<Badge className="bg-zinc-600/20 text-zinc-400">Unknown</Badge>
```

---

## Anti-Patterns to Avoid

### ❌ Copying Component Structure

```tsx
// ❌ Bad - Copied from another card
<div className="bg-zinc-900 rounded-lg border border-zinc-800">
  <div className="p-4 border-b border-zinc-800">
    <h2>Title</h2>
  </div>
  <div className="p-4">{content}</div>
</div>

// ✅ Good - Use shared component
<ScrollableCard title="Title">{content}</ScrollableCard>
```

### ❌ Hardcoding Values

```tsx
// ❌ Bad - Hardcoded
function AgentCard({ agent }) {
  return <div className="p-4">...</div>;
}

function TaskCard({ task }) {
  return <div className="p-4">...</div>; // Same padding!
}

// ✅ Good - Configurable
function ItemCard({ title, children, padding = "p-4" }) {
  return <div className={padding}>{children}</div>;
}
```

### ❌ Reinventing UI Primitives

```tsx
// ❌ Bad - Custom button
<div
  className="px-3 py-1 bg-blue-500 rounded cursor-pointer"
  onClick={...}
>
  Click me
</div>

// ✅ Good - Use Button component
import { Button } from "@/components/ui/button";
<Button onClick={...}>Click me</Button>
```

### ❌ Creating New Colors

```tsx
// ❌ Bad - Random colors
<div className="bg-purple-900 text-yellow-200">...</div>

// ✅ Good - Established palette
<div className="bg-zinc-900 text-zinc-200">...</div>
```

---

## Quick Reference Commands

### Component Discovery
```bash
# List all shared components
ls frontend/src/components/ui/

# Find component usage
grep -r "ScrollableCard" frontend/src/components/

# Find similar patterns
grep -r "sticky" frontend/src/components/
grep -r "usePoll" frontend/src/components/
```

### Adding shadcn Components
```bash
cd frontend
npx shadcn@latest add <component-name>

# Available components: https://ui.shadcn.com/docs/components
```

### Development Server
```bash
# Start frontend only
cd frontend && npm run dev

# Start all services
docker-compose up

# Backend API docs
# http://localhost:8000/docs
```

---

## Migration Workflow

**When refactoring existing code to use shared components:**

### Step 1: Identify Copy-Paste
```bash
# Find duplicated patterns
grep -r "bg-zinc-900 rounded-lg border" frontend/src/components/
```

### Step 2: Extract to Shared Component
1. Create new component in `components/ui/`
2. Make it configurable with props
3. Add TypeScript interface
4. Test in one location

### Step 3: Migrate Usages
1. Update one component at a time
2. Test each migration
3. Remove old code

### Step 4: Document
1. Create `*-IMPLEMENTATION.md` artifact
2. Update CLAUDE.md if new pattern
3. Commit with descriptive message

**Example**: See [SCROLLABLE-CARD-COMPONENT.md](./SCROLLABLE-CARD-COMPONENT.md)

---

## Success Metrics

You're following the guidelines when:

- ✅ No component code is duplicated
- ✅ All UI primitives use shadcn/ui
- ✅ Shared components have TypeScript interfaces
- ✅ Components are configurable via props
- ✅ Color palette is consistent
- ✅ New patterns are documented
- ✅ Implementation docs exist for major features

---

## Getting Help

1. **Read existing implementation docs**:
   - [SCROLLABLE-CARD-COMPONENT.md](./SCROLLABLE-CARD-COMPONENT.md)
   - [WX-DEPLOYMENTS-IMPLEMENTATION.md](./WX-DEPLOYMENTS-IMPLEMENTATION.md)
   - [JIRA-SUMMARY-IMPLEMENTATION.md](./JIRA-SUMMARY-IMPLEMENTATION.md)

2. **Search for similar patterns**:
   ```bash
   grep -r "pattern-name" frontend/src/components/
   ```

3. **Check CLAUDE.md**:
   - Component development rules
   - Common patterns
   - Anti-patterns

4. **Review recent commits**:
   ```bash
   git log --oneline -10
   git show <commit-hash>
   ```

---

**Remember**: The goal is maintainability through reuse. When in doubt, refactor to make it configurable rather than creating a new specialized component.
