# JIRA Summary Filter Update

## Clickable Filter Titles

Made all filter section titles clickable to select all/none, matching the OpenMRs pattern.

### Changes

1. **View** - Click to toggle back to "Both"
2. **Project** - Click to toggle between "All" and current selection
3. **Status** - Click to toggle all on/off

### Behavior

**View Title Click**:
- Always sets to "Both" (shows Me + Team sections)

**Project Title Click**:
- If "All" selected → switches to first specific project (Compute)
- If specific project selected → switches back to "All"

**Status Title Click** (like OpenMRs):
- If any statuses selected → deselect all
- If none selected → select all

### UI Changes

All three filter titles are now styled as clickable buttons:
```tsx
<button
  onClick={toggleAllStatuses}
  className="text-[10px] text-zinc-500 font-medium uppercase w-20 text-left hover:text-zinc-300 transition-colors"
>
  Status
</button>
```

Hover effect changes color from zinc-500 to zinc-300 to indicate clickability.

## Files Modified

- `frontend/src/components/cards/JiraSummary.tsx`
  - Added `toggleAllProjects()` function
  - Added `toggleAllStatuses()` function
  - Changed View/Project/Status title `<span>` to `<button>`
  - Added onClick handlers and hover styles

## Testing

Try clicking on:
- "View" label → Should switch to "Both"
- "Project" label → Should toggle between "All" and specific project
- "Status" label → Should toggle all statuses on/off

All filters now have consistent interaction patterns matching OpenMRs.
