# Jira Summary View Design

## Overview
A comprehensive Jira view for the Commander Dashboard with "Me" and "Team" sections, showing Kanban-style ticket organization with relationship tracking.

## Layout

```
┌─────────────────────────────────────────────────────────────┐
│ JIRA Summary                                           [⋮]  │
├─────────────────────────────────────────────────────────────┤
│ [Me] [Team]           [To Do] [In Progress] [Review] [Done] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌──────────── ME SECTION ────────────┐                     │
│ │                                    │                     │
│ │ ┌─ Assigned (3) ─────────────────┐ │                     │
│ │ │ ● COMPUTE-1234                 │ │                     │
│ │ │   Fix task lease timeout       │ │                     │
│ │ │   👤 ao  🔗 !831  💬 3         │ │                     │
│ │ └────────────────────────────────┘ │                     │
│ │                                    │                     │
│ │ ┌─ Watching (2) ──────────────────┐ │                     │
│ │ │ ● COMPUTE-5678                 │ │                     │
│ │ │   G4 OOM detection             │ │                     │
│ │ │   👤 dharma  👀 watching       │ │                     │
│ │ └────────────────────────────────┘ │                     │
│ │                                    │                     │
│ │ ┌─ Reviewed MRs (1) ──────────────┐ │                     │
│ │ │ ● COMPUTE-9012                 │ │                     │
│ │ │   Add retry logic              │ │                     │
│ │ │   👤 justin  ✓ MR reviewed     │ │                     │
│ │ └────────────────────────────────┘ │                     │
│ └────────────────────────────────────┘                     │
│                                                             │
│ ┌──────────── TEAM SECTION ──────────┐                     │
│ │ [Kanban View]                      │                     │
│ │                                    │                     │
│ │ To Do (8)   In Progress (5)  Review (3)   Done (12)     │
│ │ ┌────────┐  ┌────────┐      ┌────────┐   ┌────────┐    │
│ │ │COMP-123│  │COMP-456│      │COMP-789│   │COMP-012│    │
│ │ │Title   │  │Title   │ ●ao  │Title   │   │Title   │    │
│ │ │👤 user │  │👤 user │      │👤 user │   │👤 user │    │
│ │ └────────┘  └────────┘      └────────┘   └────────┘    │
│ │ ┌────────┐  ┌────────┐      ┌────────┐                 │
│ │ │...     │  │...     │      │...     │                 │
│ │ └────────┘  └────────┘      └────────┘                 │
│ └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Features

### Me Section
Groups tickets by my relationship to them:

1. **Assigned to Me** - Direct assignments
2. **Watching** - Tickets I'm watching in Jira
3. **Paired/Reviewing** - Tickets where I'm listed as a reviewer or pair
4. **MR Reviewed** - Tickets linked to MRs I've reviewed (detected from dashboard MR review tracking)
5. **Slack Discussed** - Tickets I've responded about in Slack (based on Slack message correlation)

Each ticket shows:
- Status badge (color-coded)
- Key and title
- Assignee
- Relationship badges (🔗 MR linked, 💬 Slack activity, 👀 watching, ✓ reviewed)
- Age indicator

### Team Section
Kanban view of all team tickets:

1. **Column Layout**: To Do | In Progress | In Review | Done (recent)
2. **Visual Indicators**:
   - My tickets highlighted with border/background
   - Badge for "me" relationship (assigned/watching/etc)
3. **Stats Bar**: Count per column, quick filters
4. **Compact Cards**: Key, title, assignee, quick badges

### Filters & Controls

**Top Bar**:
- `[Me]` `[Team]` toggle buttons (can show both)
- Status filter badges: `[To Do]` `[In Progress]` `[In Review]` `[Done]`
- Project filter: `[WX]` `[G4]` `[Jobs]` `[Temporal]` `[All]`
- Sprint selector dropdown

**Sorting** (Team view):
- By status (default - Kanban)
- By updated (most recent first)
- By age (oldest first)
- By priority

### Data Model

```typescript
export interface JiraTicketEnhanced extends JiraTicketResult {
  // Relationship tracking
  my_relationships: {
    assigned: boolean;
    watching: boolean;
    paired: boolean;
    mr_reviewed: boolean;  // From MR review history
    slack_discussed: boolean;  // From Slack correlation
  };

  // Linked resources
  linked_mrs?: Array<{
    project: string;
    iid: number;
    title: string;
    url: string;
  }>;

  slack_mentions?: Array<{
    channel: string;
    timestamp: string;
    user: string;
  }>;

  // Metadata
  age_days: number;
  last_updated: string;
  sprint?: string;
  story_points?: number;
}

export interface JiraSummaryResponse {
  me: {
    assigned: JiraTicketEnhanced[];
    watching: JiraTicketEnhanced[];
    paired: JiraTicketEnhanced[];
    mr_reviewed: JiraTicketEnhanced[];
    slack_discussed: JiraTicketEnhanced[];
  };
  team: {
    by_status: {
      todo: JiraTicketEnhanced[];
      in_progress: JiraTicketEnhanced[];
      in_review: JiraTicketEnhanced[];
      done: JiraTicketEnhanced[];
    };
    stats: {
      todo_count: number;
      in_progress_count: number;
      in_review_count: number;
      done_count: number;
    };
  };
  current_sprint?: string;
  project: string;
}
```

### API Endpoints

```typescript
// Frontend API calls
api.jiraSummary: (project?: string, sprint?: string) =>
  fetchApi<JiraSummaryResponse>(`/jira/summary?project=${project}&sprint=${sprint}`);

api.jiraMyTickets: (include_watching?: boolean) =>
  fetchApi<{ tickets: JiraTicketEnhanced[]; total: number }>("/jira/my-tickets?include_watching=true");

api.jiraTeamKanban: (project?: string, sprint?: string) =>
  fetchApi<JiraSummaryResponse["team"]>(`/jira/team-kanban?project=${project}&sprint=${sprint}`);
```

### Backend Implementation Notes

The backend would need to:

1. **Query Jira API**:
   - My assigned tickets
   - Tickets I'm watching
   - Team tickets in current sprint
   - JQL: `project = COMPUTE AND sprint = "Current Sprint"`

2. **Correlate MR Reviews**:
   - Read MR review tracking from dashboard DB
   - Extract ticket keys from MR titles/descriptions
   - Match against Jira tickets

3. **Correlate Slack Activity**:
   - Search Slack message cache for Jira ticket keys
   - Filter to messages from current user
   - Link tickets to Slack channels/threads

4. **Enhancement Data**:
   - Calculate age_days from created/updated dates
   - Extract sprint from Jira fields
   - Parse story points

## Visual Design

### Status Colors
```typescript
const STATUS_COLORS = {
  "To Do": "bg-zinc-600/20 text-zinc-400 border-zinc-600/30",
  "In Progress": "bg-blue-600/20 text-blue-400 border-blue-600/30",
  "In Review": "bg-purple-600/20 text-purple-400 border-purple-600/30",
  "Done": "bg-emerald-600/20 text-emerald-400 border-emerald-600/30",
  "Blocked": "bg-red-600/20 text-red-400 border-red-600/30",
};
```

### Relationship Badges
```typescript
const RELATIONSHIP_ICONS = {
  assigned: "👤",       // Primary assignee
  watching: "👀",       // Watching
  paired: "🤝",         // Pair/reviewer
  mr_reviewed: "✓",     // Reviewed MR
  slack_discussed: "💬", // Discussed in Slack
  mr_linked: "🔗",      // Has linked MR
};
```

### Priority Indicators
```typescript
const PRIORITY_COLORS = {
  "Highest": "text-red-400",
  "High": "text-orange-400",
  "Medium": "text-yellow-400",
  "Low": "text-zinc-500",
  "Lowest": "text-zinc-600",
};
```

## Component Structure

```
/Users/aaryn/claude/dashboard/frontend/src/components/cards/JiraSummary.tsx
  Main component with Me/Team toggle

/Users/aaryn/claude/dashboard/frontend/src/components/jira/JiraMeSection.tsx
  "Me" section with relationship grouping

/Users/aaryn/claude/dashboard/frontend/src/components/jira/JiraKanbanView.tsx
  Kanban board for team tickets

/Users/aaryn/claude/dashboard/frontend/src/components/jira/JiraTicketCard.tsx
  Reusable ticket card component

/Users/aaryn/claude/dashboard/frontend/src/components/jira/JiraTicketModal.tsx
  Detail modal for ticket deep-dive
```

## Interactions

### Ticket Card Click
Opens modal with:
- Full description
- Comments
- Linked MRs (clickable)
- Slack threads (clickable)
- Watchers list
- Transition buttons (To Do → In Progress → etc)

### Drag & Drop (Future)
Enable drag-and-drop between Kanban columns to update status

### Quick Actions
- **Assign to Me**: Click to assign unassigned ticket
- **Watch/Unwatch**: Toggle watching status
- **Open in Jira**: External link
- **View MRs**: Jump to related MRs in OpenMRs card
- **View Slack**: Jump to Slack threads

## Implementation Priority

### Phase 1: Basic View (MVP)
- [ ] JiraSummary component with Me/Team toggle
- [ ] API endpoint: `/api/jira/summary`
- [ ] Basic Me section (assigned, watching)
- [ ] Basic Team section (simple list by status)
- [ ] Click to open in Jira (external link)

### Phase 2: Enhanced Relationships
- [ ] MR correlation logic
- [ ] Slack correlation logic
- [ ] Enhanced badges showing relationships
- [ ] Ticket detail modal

### Phase 3: Kanban Polish
- [ ] Full Kanban column layout
- [ ] Drag-and-drop status updates
- [ ] Inline filters and sorting
- [ ] Sprint selector

### Phase 4: Integrations
- [ ] Quick transition buttons (move to In Progress, etc)
- [ ] Assign to Me button
- [ ] Watch/Unwatch toggle
- [ ] Deep links to MRs and Slack threads

## Responsive Behavior

- **Desktop (>1200px)**: Full side-by-side Me + Team
- **Tablet (768-1200px)**: Stacked Me above Team, compact Kanban
- **Mobile (<768px)**: Tab-based Me/Team toggle, list view instead of Kanban

## Performance Considerations

- Cache Jira data for 5 minutes (tickets don't change that fast)
- Poll interval: 5 minutes (120_000ms like other cards)
- Lazy load Slack/MR correlations (on expand/detail modal)
- Virtualize long lists (if >50 tickets)

## Example Queries

### Me Section
```jql
assignee = currentUser() AND resolution = Unresolved
OR watcher = currentUser() AND resolution = Unresolved
ORDER BY updated DESC
```

### Team Section (Compute)
```jql
project = COMPUTE
AND sprint in openSprints()
AND resolution = Unresolved
ORDER BY status ASC, updated DESC
```

## Notes

- Follow existing dashboard patterns (CardShell, usePoll, Badge)
- Reuse color schemes from OpenMRs and SlackSummary
- Maintain dark theme consistency
- Ensure accessibility (keyboard navigation, ARIA labels)
- Add tooltips for relationship badges
