# ScrollableCard Component - Shared UI Pattern

**Date**: 2026-03-17
**Status**: ✅ Complete

## Problem

Multiple cards across the dashboard had inconsistent layout patterns and issues:

1. **WX Agents View** - Search bar and header scrolled with content (not sticky)
2. **Inconsistent padding** - Cards had different padding styles
3. **Code duplication** - Same container pattern copied across components
4. **No shared component** - Each card implemented its own layout logic

## Solution

Created `ScrollableCard` - a shared UI component that provides:

- ✅ **Sticky header** with title and menu
- ✅ **Optional sticky filters/search** section
- ✅ **Scrollable content area** with consistent padding
- ✅ **Consistent styling** across all cards

## Component Location

**File**: `frontend/src/components/ui/scrollable-card.tsx`

## Usage

```tsx
import { ScrollableCard } from "@/components/ui/scrollable-card";

<ScrollableCard
  title="Card Title"
  icon={<Icon className="h-4 w-4" />}
  menuItems={[{ label: "Refresh", onClick: handleRefresh }]}
  stickyHeader={<div>Optional sticky filters/search</div>}
  maxHeight="600px" // Optional max height
>
  {/* Scrollable content here */}
</ScrollableCard>
```

## Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `title` | `string` | ✅ | Card title displayed in header |
| `icon` | `ReactNode` | ❌ | Icon displayed next to title |
| `menuItems` | `Array<{label, href?, onClick?}>` | ❌ | Dropdown menu items |
| `stickyHeader` | `ReactNode` | ❌ | Sticky content below title (filters, search, etc.) |
| `children` | `ReactNode` | ✅ | Scrollable content |
| `maxHeight` | `string` | ❌ | Max height for scrollable area |
| `className` | `string` | ❌ | Additional CSS classes |

## Structure

```
┌─────────────────────────────────────┐
│ 📌 Sticky Header (title + menu)     │ ← Always visible
├─────────────────────────────────────┤
│ 📌 Sticky Filters (optional)        │ ← Always visible
├─────────────────────────────────────┤
│                                     │
│ 📜 Scrollable Content               │ ← Scrolls independently
│                                     │
│                                     │
└─────────────────────────────────────┘
```

## Migrated Components

### 1. WX Deployments ✅

**Before:**
```tsx
<CardShell title="WX Deployments" ...>
  <div className="space-y-2">
    {/* Content */}
  </div>
</CardShell>
```

**After:**
```tsx
<ScrollableCard title="WX Deployments" icon={<Rocket />} ...>
  <div className="space-y-2">
    {/* Content */}
  </div>
</ScrollableCard>
```

**Benefits:**
- Consistent padding
- Proper scrolling when many deployments
- Matches other cards' styling

### 2. Agents List ✅

**Before:**
```tsx
<div className="bg-zinc-900 rounded-lg border border-zinc-800 flex flex-col overflow-hidden h-full">
  <div className="flex items-center justify-between p-4 border-b border-zinc-800">
    <h2>Agents</h2>
  </div>
  <div className="flex-1 overflow-auto">
    <ProjectAgents ... />
  </div>
</div>
```

**After:**
```tsx
<ScrollableCard
  title="Agents"
  icon={<Bot />}
  stickyHeader={
    <>
      <Search bar />
      <Filters />
    </>
  }
>
  <div className="space-y-2">
    {agents.map(...)}
  </div>
</ScrollableCard>
```

**Benefits:**
- ✅ **Sticky search bar** - Searchalways visible while scrolling agents
- ✅ **Sticky header** - Title stays at top
- ✅ **Proper padding** - Consistent with JIRA Summary
- ✅ **Better UX** - Can scroll long agent lists without losing search

### 3. JIRA Summary ✅

**Before:**
```tsx
<CardShell title="JIRA Summary" ...>
  <div className="space-y-2 mb-3 pb-3 border-b border-zinc-800">
    {/* Filters */}
  </div>
  <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2">
    {/* Content */}
  </div>
</CardShell>
```

**After:**
```tsx
<ScrollableCard
  title="JIRA Summary"
  icon={<CheckSquare />}
  stickyHeader={<div>{/* Filters */}</div>}
  maxHeight="600px"
>
  <div className="space-y-4">
    {/* Content */}
  </div>
</ScrollableCard>
```

**Benefits:**
- Sticky filters remain visible while scrolling tickets
- No manual overflow/padding management
- Cleaner component structure

## Design Pattern

### Sticky Header Section

Use `stickyHeader` for:
- Search/filter inputs
- Action buttons (refresh, sync, etc.)
- Quick stats/counts
- Tab/view toggles

**Example:**
```tsx
const stickyHeader = (
  <div className="space-y-3">
    {/* Search */}
    <Input placeholder="Search..." />

    {/* Stats and actions */}
    <div className="flex justify-between">
      <span>{count} items</span>
      <Button onClick={refresh}>Refresh</Button>
    </div>
  </div>
);

<ScrollableCard stickyHeader={stickyHeader}>
  {/* Content */}
</ScrollableCard>
```

### Scrollable Content

The `children` prop contains the scrollable content:
- Lists of items
- Detailed information
- Nested sections

**Auto-padding:** The component automatically adds consistent padding (`px-4 py-3`)

## Styling Details

### Colors & Borders
- Background: `bg-zinc-900/50` with backdrop blur
- Border: `border-zinc-800`
- Header border: `border-b border-zinc-800`

### Padding
- **Header**: `py-3 px-4`
- **Sticky section**: `px-4 pt-3 pb-3`
- **Content**: `px-4 py-3`

### Overflow
- Card: `overflow-hidden` (prevents content overflow)
- Content area: `overflow-y-auto` (vertical scroll only)

## Benefits

1. **Consistency** - All cards use same layout/padding
2. **DRY** - No copy-pasta of container code
3. **UX** - Sticky headers improve usability
4. **Maintainability** - One place to update card styling
5. **Accessibility** - Proper scroll containers

## Future Components

Any new card with scrollable content should use `ScrollableCard`:

```tsx
// ✅ Good - Use ScrollableCard
<ScrollableCard title="New Feature" ...>
  <div className="space-y-2">
    {items.map(...)}
  </div>
</ScrollableCard>

// ❌ Bad - Don't recreate the pattern
<div className="bg-zinc-900 rounded-lg border...">
  <div className="p-4 border-b...">
    <h2>New Feature</h2>
  </div>
  <div className="overflow-y-auto...">
    {/* Content */}
  </div>
</div>
```

## Files Changed

- ✅ `frontend/src/components/ui/scrollable-card.tsx` - New component
- ✅ `frontend/src/components/cards/WXDeployments.tsx` - Migrated
- ✅ `frontend/src/components/agents/ProjectAgents.tsx` - Migrated
- ✅ `frontend/src/components/cards/JiraSummary.tsx` - Migrated
- ✅ `frontend/src/components/wx/WXDashboard.tsx` - Updated agents container

## Testing

After frontend rebuild, verify:

1. **WX Page** (`/wx`):
   - ✅ Agents search bar stays at top when scrolling agent list
   - ✅ Agents header doesn't scroll
   - ✅ Padding matches JIRA Summary card

2. **Dashboard** (`/`):
   - ✅ JIRA filters stay visible when scrolling tickets
   - ✅ WX Deployments card has proper padding

3. **All cards**:
   - ✅ Consistent visual style
   - ✅ Smooth scrolling
   - ✅ No layout shifts

## Migration Checklist

When converting a card to `ScrollableCard`:

- [ ] Import `ScrollableCard` instead of `CardShell`
- [ ] Move filters/search to `stickyHeader` prop
- [ ] Remove manual `overflow-y-auto` from content
- [ ] Remove manual padding from content sections
- [ ] Set `maxHeight` if needed (otherwise uses full height)
- [ ] Update closing tag to `</ScrollableCard>`
- [ ] Test sticky behavior and scrolling

---

**Result**: Consistent, maintainable card layout across the entire dashboard!
