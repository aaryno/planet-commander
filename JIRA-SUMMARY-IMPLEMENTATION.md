# JIRA Summary Implementation

## Status: Phase 1 MVP Complete ✓

Implemented a compelling JIRA Summary view for the Commander Dashboard with "Me" and "Team" sections.

## What's Been Built

### Frontend Components

1. **`/frontend/src/components/jira/JiraTicketCard.tsx`**
   - Reusable ticket card component
   - Shows status badges, priority, assignee
   - Relationship indicators (👀 watching, 🔗 MR linked, 💬 Slack discussed, ✓ reviewed)
   - My tickets highlighted with emerald border/background
   - Compact mode for list views

2. **`/frontend/src/components/cards/JiraSummary.tsx`**
   - Main dashboard card component
   - View mode toggle: Me / Team / Both
   - Project filter: All, Compute, WX, G4, Jobs, Temporal
   - Status filter: To Do, In Progress, In Review, Done
   - 5-minute polling (300s)
   - Follows existing CardShell pattern

3. **Updated `/frontend/src/app/page.tsx`**
   - Integrated JiraSummary into main dashboard
   - col-span-4 layout (takes up 1/3 of row)

### Backend API

4. **Updated `/backend/app/api/jira.py`**
   - New endpoint: `GET /api/jira/summary`
   - Query params: `project`, `sprint` (optional)
   - Returns structured response with Me/Team sections
   - **Currently returns mock data** for MVP testing

5. **Updated `/frontend/src/lib/api.ts`**
   - Added `JiraTicketEnhanced` interface
   - Added `JiraSummaryResponse` interface
   - Added `api.jiraSummary()` method

## Features Implemented

### "Me" Section
Groups tickets by relationship:
- **Assigned** - Direct assignments (excluding Done)
- **Watching** - Tickets being watched (not assigned)
- **MR Reviewed** - Tickets where I've reviewed MRs
- **Slack Discussed** - Tickets I've discussed in Slack

Each section shows:
- Badge with count
- Up to 5 tickets (with "+N more" if needed)
- Compact cards with relationship indicators

### "Team" Section
Kanban-style status grouping:
- **To Do** - Not started
- **In Progress** - Active work
- **In Review** - Code review
- **Done** - Recently completed

Each status shows:
- Colored status badge
- Count indicator
- Up to 5 tickets per status
- My tickets highlighted

### Filters & Controls
- **View Toggle**: Me, Team, or Both sections
- **Project Filter**: All, Compute, WX, G4, Jobs, Temporal
- **Status Filter**: Toggle which statuses show in Team view
- **Refresh**: Manual refresh via menu

### Visual Design
- Dark theme consistency
- Color-coded status badges
- Relationship emoji indicators
- Emerald highlighting for my tickets
- Compact, scannable layout

## Mock Data

Currently using 5 sample tickets:
1. **COMPUTE-1234** - Assigned to me, in progress, has MR, Slack discussed
2. **COMPUTE-5678** - Watching, in review, MR reviewed by me
3. **COMPUTE-9012** - Team member, to do
4. **COMPUTE-3456** - Assigned to me, done, has MR
5. **COMPUTE-7890** - Team member, in progress

## How to Test

1. **Start the dashboard**:
   ```bash
   cd ~/claude/dashboard
   docker-compose up
   ```

2. **Open browser**:
   ```
   http://localhost:9300
   ```

3. **View the JIRA Summary card**:
   - Located in the main dashboard (col-span-4)
   - Toggle between Me/Team/Both views
   - Filter by project
   - Filter by status (in Team view)

## Next Steps (Phase 2+)

### Backend Enhancements
- [ ] Replace mock data with real JIRA API queries
- [ ] Implement watching detection (JIRA watcher API)
- [ ] Correlate MRs to tickets (extract COMPUTE-#### from MR titles/descriptions)
- [ ] Correlate Slack discussions (search message cache for ticket keys)
- [ ] Add sprint detection/filtering
- [ ] Cache results (5-minute TTL)

### Frontend Enhancements
- [ ] Ticket detail modal (on card click)
  - Full description
  - Comments
  - Linked MRs (clickable)
  - Slack threads (clickable)
  - Watchers list
  - Status transition buttons
- [ ] Drag-and-drop Kanban (update status)
- [ ] Quick actions:
  - Assign to Me
  - Watch/Unwatch
  - Open in JIRA (external link)
  - View linked MRs
  - View Slack threads
- [ ] Sprint selector dropdown
- [ ] Sorting options (age, priority, updated)

### Integration Enhancements
- [ ] Cross-link with OpenMRs card
- [ ] Cross-link with Slack Summary
- [ ] Real-time updates on status changes
- [ ] Notifications for @mentions in Slack

## Architecture Notes

### Data Flow
```
Frontend (React)
  ↓ usePoll (5min)
  ↓ api.jiraSummary(project, sprint)
  ↓
Backend (FastAPI)
  ↓ GET /api/jira/summary?project=X&sprint=Y
  ↓
[Phase 2] JIRA Service
  ↓ JQL queries (assigned, watching, team)
  ↓
[Phase 2] Correlation Services
  ↓ MR database (reviewed MRs)
  ↓ Slack cache (discussed tickets)
  ↓
Response: JiraSummaryResponse
```

### Relationship Detection Logic (Phase 2)

**Assigned**: `assignee = currentUser()`

**Watching**: JIRA Watcher API
```
GET /rest/api/2/issue/{issueKey}/watchers
```

**MR Reviewed**: Dashboard MR review database
- Query reviews where `reviewer = current_user`
- Extract ticket keys from MR titles: `/(COMPUTE-\d+)/`
- Match against JIRA tickets

**Slack Discussed**: Slack message cache
- Search messages from current user
- Find JIRA key patterns: `/(COMPUTE-\d+)/`
- Group by ticket key
- Link to channels/threads

## Files Modified

```
frontend/src/lib/api.ts                           (types + endpoint)
frontend/src/components/jira/JiraTicketCard.tsx   (new)
frontend/src/components/cards/JiraSummary.tsx     (new)
frontend/src/app/page.tsx                         (integration)
backend/app/api/jira.py                           (new /summary endpoint)
```

## Design Document

Full design specification: `~/claude/dashboard/jira-summary-design.md`

## Questions?

- **Why mock data?**: Phase 1 MVP focuses on UI/UX. Real integration comes in Phase 2.
- **Why 5-minute polling?**: Matches other dashboard cards. JIRA data doesn't change rapidly.
- **Why emoji indicators?**: Quick visual scan of relationships without reading text.
- **Why "Me" section first?**: Primary use case is "what do I need to work on?"
