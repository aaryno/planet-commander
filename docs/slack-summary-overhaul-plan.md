# Slack Summary Overhaul — Implementation Plan

**Date**: 2026-04-24
**Scope**: ChannelMessagesModal, SlackSummary, backend message API
**Goal**: Transform raw text message display into a rich, searchable, threaded Slack reader

---

## Current State Assessment

### What exists today

| Layer | File | What it does | Problems |
|-------|------|--------------|----------|
| **Data** | `~/tools/slack/sync-channel.py` | Syncs messages from Slack API, stores as markdown files per day. Threads marked with `  ↳ ` prefix. Reactions stored as `:emoji_name: N`. User mentions stored as `<@UXXXXXXX>`. | No structured data — everything is flat markdown text |
| **Backend** | `backend/app/services/slack_service.py` | Reads markdown files, concatenates them, counts messages by regex | Returns raw markdown string, no structured message objects |
| **Backend API** | `backend/app/api/slack.py` | `/channel/{name}/messages` returns `{content: string}` | Single giant text blob, no pagination, no user metadata |
| **Frontend Modal** | `ChannelMessagesModal.tsx` | Parses `**User** \`HH:MM:SS\`` headers from text, renders `<a>` for Slack-style links | No markdown rendering, no emoji, no thread grouping, no user highlighting, no search |
| **Frontend Card** | `SlackSummary.tsx` | Team/channel selector, AI summarization, channel stats | `MarkdownContent` uses regex→`dangerouslySetInnerHTML` (no react-markdown), no filters |

### Data format (from markdown files)

```markdown
# #compute-platform - March 17, 2025

**Channel ID**: CBEMHA2LV
**Message Count**: 19

---

**Henry Whipps** `16:20:23`
^ FYI I'm working to enable s3 compatible deliveries...

**Agata Kargol** `17:26:25`
<@U057YJUJ9KN> do you want another bizarre G4 on-call thing?

  ↳ **Dharma Bellamkonda** `17:54:31`
  ↳ Sure, what's up?

**Slackbot** `17:00:29`
Reminder: :mag_right: Please list any outstanding MRs that need review.

_Reactions: :eyes: 1_
```

Key patterns to parse:
- **Username** `` `HH:MM:SS` `` — message header
- `  ↳ ` prefix — thread reply
- `<@UXXXXXXX>` — user mention
- `<URL|text>` or `<URL>` — Slack-style links
- `:emoji_name:` — Slack emoji shortcodes
- `_Reactions: :name: N_` — reaction line
- `&amp;` etc. — HTML entities
- `*bold*`, `_italic_`, `` `code` `` — Slack formatting

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    ChannelMessagesModal                  │
│  ┌──────────────────────────────────────────────────┐   │
│  │  FilterBar                                        │   │
│  │  [🔍 Search_____________________] [Users▾] [Time]│   │
│  │  [pill1] [pill2] [pill3] ... [+N more]            │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │  MessageList (virtualized)                        │   │
│  │  ┌────────────────────────────────────────────┐   │   │
│  │  │  DateHeader: March 17, 2025                │   │   │
│  │  ├────────────────────────────────────────────┤   │   │
│  │  │  MessageBubble                             │   │   │
│  │  │  [Avatar] Username  16:20:23               │   │   │
│  │  │  Rich text with **bold**, `code`, :emoji:  │   │   │
│  │  │  └─ ThreadReplies (collapsible) ──────┐    │   │   │
│  │  │     ↳ Reply 1 by @user                │    │   │   │
│  │  │     ↳ Reply 2 by @user                │    │   │   │
│  │  │  └────────────────────────────────────┘    │   │   │
│  │  │  Reactions: 👍 2  👀 1                     │   │   │
│  │  └────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Structured Message Parsing (Backend)
**Effort**: ~3 hours | **Priority**: Foundation — everything else depends on this

The backend currently returns a single giant string. We need structured message objects with thread grouping.

#### 1a. New message parser in `slack_service.py`

Add a `parse_channel_messages()` function that converts the markdown text into structured dicts:

```python
@dataclass
class ParsedMessage:
    username: str
    timestamp: str          # "16:20:23"
    date: str               # "2025-03-17"
    text: str               # Raw text (still has Slack markup)
    is_thread_reply: bool
    thread_parent_ts: str | None
    reactions: list[dict]   # [{"name": "eyes", "count": 1}]
    attachments: list[str]
    files: list[str]
    raw_line_index: int     # For stable ordering
```

**Parse logic**:
- Split file content by lines
- Detect `**Username** \`HH:MM:SS\`` as message headers
- Detect `  ↳ ` prefix for thread replies
- Group consecutive `↳` replies under their parent message
- Extract `_Reactions: :name: N ..._` lines
- Extract `📎 File:` lines
- Extract `_Attachment:` lines

**Thread grouping**: Walk messages in order. When a `↳` reply appears, attach it to the most recent non-reply message. Return messages as a tree:

```python
@dataclass
class MessageThread:
    parent: ParsedMessage
    replies: list[ParsedMessage]
```

#### 1b. New API endpoint

**File**: `backend/app/api/slack.py`

Add `GET /channel/{channel}/messages-structured`:

```python
@router.get("/channel/{channel}/messages-structured")
async def get_channel_messages_structured(
    channel: str,
    days: int = Query(7, ge=1, le=90),
):
    """Return parsed, structured messages with thread grouping."""
```

Response shape:
```json
{
  "channel": "compute-platform",
  "days": 7,
  "messages": [
    {
      "id": "msg-0",
      "username": "Henry Whipps",
      "timestamp": "16:20:23",
      "date": "2025-03-17",
      "text": "FYI I'm working to enable s3 compatible deliveries...",
      "is_thread_reply": false,
      "reactions": [{"name": "eyes", "count": 1}],
      "attachments": [],
      "files": [],
      "replies": [
        {
          "username": "Dharma Bellamkonda",
          "timestamp": "17:54:31",
          "date": "2025-03-17",
          "text": "Sure, what's up?",
          "reactions": [],
          "attachments": [],
          "files": []
        }
      ]
    }
  ],
  "users": ["Henry Whipps", "Agata Kargol", "Dharma Bellamkonda", ...],
  "total_count": 42
}
```

Keep the existing `/channel/{channel}/messages` endpoint for backward compatibility.

**Files modified**:
- `backend/app/services/slack_service.py` — add `parse_channel_messages()`, `get_channel_messages_structured()`
- `backend/app/api/slack.py` — add new endpoint

---

### Phase 2: Rich Text Rendering (Frontend)
**Effort**: ~4 hours | **Priority**: High — biggest visual improvement

#### 2a. Create `SlackMessageRenderer` utility

**New file**: `frontend/src/lib/slack-formatting.ts`

Pure functions, no React — just text→text transforms that can be tested independently:

```typescript
// Slack markup → markdown/HTML transforms
export function resolveSlackLinks(text: string): string
  // <URL|text> → [text](URL), <URL> → [URL](URL)

export function resolveUserMentions(text: string): string
  // <@UXXXXXXX> → @username (with highlight span)

export function resolveEmojiShortcodes(text: string): string
  // :thumbsup: → 👍, :eyes: → 👀, etc.
  // Use a static map of ~200 common Slack emoji shortcodes
  // Unknown shortcodes: render as-is (:custom_emoji:) with subtle styling

export function decodeHtmlEntities(text: string): string
  // &amp; → &, &lt; → <, etc.

export function slackToMarkdown(text: string): string
  // Pipeline: decodeHtmlEntities → resolveSlackLinks → resolveEmojiShortcodes
  // Does NOT resolve user mentions (those need React components)
```

**Emoji approach**: Bundle a static map of the ~200 most common Slack emoji shortcodes (from `gemoji` or hand-curated). No runtime fetches, no external API. Custom workspace emoji render as styled `:name:` badges.

#### 2b. Create `SlackMessage` React component

**New file**: `frontend/src/components/slack/SlackMessage.tsx`

```tsx
interface SlackMessageProps {
  message: StructuredMessage;
  highlightUsers?: string[];  // Usernames to highlight
  searchQuery?: string;       // Text to highlight
}

export function SlackMessage({ message, highlightUsers, searchQuery }: SlackMessageProps) {
  // 1. Transform text through slackToMarkdown()
  // 2. Render with ReactMarkdown (already installed) + remarkGfm
  // 3. Highlight @mentions with colored badges
  // 4. Highlight search matches with <mark>
  // 5. Show reactions as emoji pills below message
  // 6. Show file attachments as download links
}
```

#### 2c. Create `SlackReactions` component

**New file**: `frontend/src/components/slack/SlackReactions.tsx`

Small pill badges showing emoji + count, matching Slack's visual style:

```tsx
<div className="flex gap-1 mt-1">
  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full
    bg-zinc-800 border border-zinc-700 text-xs">
    👍 2
  </span>
</div>
```

**Files modified/created**:
- `frontend/src/lib/slack-formatting.ts` — **new**
- `frontend/src/components/slack/SlackMessage.tsx` — **new**
- `frontend/src/components/slack/SlackReactions.tsx` — **new**

---

### Phase 3: Thread Detection & Expandable Views
**Effort**: ~2 hours | **Priority**: High — threads are currently invisible

#### 3a. Thread grouping in `MessageList`

Use the `replies[]` array from the structured API. Display parent message normally, then show a collapsed thread indicator:

```
  [Username] 16:20:23
  Message text here...
  ┗━ 3 replies (click to expand) ━━━━━━━━━━━━━━━━━━━┛
```

#### 3b. `ThreadReplies` collapsible component

**New file**: `frontend/src/components/slack/ThreadReplies.tsx`

Uses the existing `Collapsible` component from `@/components/ui/collapsible`:

```tsx
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "@/components/ui/collapsible";

export function ThreadReplies({ replies, highlightUsers, searchQuery }: Props) {
  // CollapsibleTrigger: "N replies" badge
  // CollapsibleContent: indented list of <SlackMessage> components
  // Auto-expand if any reply matches search query
}
```

Visual: Replies indented with a left border (`border-l-2 border-zinc-700 pl-3 ml-4`), slightly dimmer background.

**Files created**:
- `frontend/src/components/slack/ThreadReplies.tsx` — **new**

---

### Phase 4: Modal Overhaul & z-index Fix
**Effort**: ~2 hours | **Priority**: High — functional blockers

#### 4a. Migrate to shadcn Dialog

Replace the custom `<div className="fixed inset-0 z-[9999]">` with the existing `Dialog` component from `@/components/ui/dialog`. This fixes z-index issues by using Radix Portal (renders at document root, outside any stacking context).

```tsx
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export function ChannelMessagesModal({ channel, days, open, onOpenChange }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[85vh] flex flex-col bg-zinc-900 border-zinc-700">
        <DialogHeader>
          <DialogTitle>#{channel}</DialogTitle>
        </DialogHeader>
        {/* FilterBar + MessageList */}
      </DialogContent>
    </Dialog>
  );
}
```

**Why this fixes z-index**: Radix Dialog uses `Portal` to mount at the top of the DOM tree. Our current modals render inside deeply nested flex containers on the dashboard, inheriting parent stacking contexts. The `z-[9999]` hack doesn't work because `z-index` only competes within the same stacking context.

#### 4b. Also migrate `ChannelDetailsModal` to Dialog

Same treatment — consistent modal behavior across the app.

#### 4c. Widen modal for message content

Current: `max-w-4xl` (896px), `max-h-[600px]`
New: `max-w-5xl` (1024px), `max-h-[85vh]` — more room for threads and filters

**Files modified**:
- `frontend/src/components/cards/ChannelMessagesModal.tsx` — rewrite
- `frontend/src/components/cards/ChannelDetailsModal.tsx` — rewrite
- `frontend/src/components/cards/SlackSummary.tsx` — update modal invocation (pass `open`/`onOpenChange` instead of conditional render)

---

### Phase 5: Filter Bar & User Pills
**Effort**: ~3 hours | **Priority**: Medium — major UX improvement

#### 5a. `FilterBar` component

**New file**: `frontend/src/components/slack/FilterBar.tsx`

Layout: Full-width bar at the top of the modal, below the header.

```
┌─────────────────────────────────────────────────────────┐
│ 🔍 [Search messages...________________________] [Clear]│
│                                                         │
│ Users: [Agata ×] [Ryan ×] [Henry] [Dharma] [Bot]       │
│        [Gitlab] [Jira Server] [Slackbot]  [+4 more]    │
│                                                         │
│ 42 messages · 12 threads · 7 users                      │
└─────────────────────────────────────────────────────────┘
```

**User pills**:
- Computed from the `users` array in the API response
- Sorted by message count (descending) — most active users first
- Show top 8, then a `+N more` expander
- Toggle on/off: active pills filter messages to that user
- Multiple selection supported (OR logic)
- Active pill style: `bg-blue-500/20 text-blue-300 border-blue-500/40`
- Inactive pill style: `border-zinc-700 text-zinc-500`

**Search box**:
- Wide input using `@/components/ui/input`
- Debounced (300ms) real-time filtering
- Filters message text content (case-insensitive substring match)
- N-gram autocomplete: as user types 3+ chars, show dropdown with matching phrases from message text
- Highlight matched text in messages (via `searchQuery` prop on `SlackMessage`)

#### 5b. Filter state management

All filter state lives in the modal component (not URL state — modal is ephemeral):

```typescript
interface FilterState {
  searchQuery: string;
  selectedUsers: Set<string>;  // Empty = show all
  expandedUsers: boolean;      // Show all users vs top 8
}
```

Filtering logic (applied client-side since we already have all messages loaded):

```typescript
function filterMessages(messages: StructuredMessage[], filters: FilterState): StructuredMessage[] {
  return messages.filter(msg => {
    // User filter
    if (filters.selectedUsers.size > 0) {
      const msgUsers = [msg.username, ...msg.replies.map(r => r.username)];
      if (!msgUsers.some(u => filters.selectedUsers.has(u))) return false;
    }
    // Search filter
    if (filters.searchQuery) {
      const q = filters.searchQuery.toLowerCase();
      const allText = [msg.text, ...msg.replies.map(r => r.text)].join(' ').toLowerCase();
      if (!allText.includes(q)) return false;
    }
    return true;
  });
}
```

#### 5c. N-gram autocomplete

Build an n-gram index when messages load:

```typescript
function buildNgramIndex(messages: StructuredMessage[], n: number = 3): Map<string, Set<string>> {
  // For each message, extract all n-grams from text
  // Map: trigram → Set of full words/phrases containing it
  // Used for autocomplete dropdown suggestions
}
```

Show dropdown under search input with up to 8 suggestions. Click a suggestion to set it as the search query.

**Files created**:
- `frontend/src/components/slack/FilterBar.tsx` — **new**

---

### Phase 6: Update `SlackSummary.tsx` MarkdownContent
**Effort**: ~1 hour | **Priority**: Medium — improves AI summary display

Replace the regex-based `MarkdownContent` component with `ReactMarkdown` (already installed and used in `ChatMessage.tsx`):

```tsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// In the summary display area:
<ReactMarkdown
  remarkPlugins={[remarkGfm]}
  components={{
    // Reuse the same component overrides from ChatMessage.tsx
  }}
>
  {summary}
</ReactMarkdown>
```

Also add emoji shortcode rendering to the summary display via `resolveEmojiShortcodes()` from `slack-formatting.ts`.

**Files modified**:
- `frontend/src/components/cards/SlackSummary.tsx` — replace `MarkdownContent`, remove `dangerouslySetInnerHTML`

---

### Phase 7: Frontend Types & API Client
**Effort**: ~30 min | **Priority**: Required for Phases 2-5

#### 7a. Add types to `api.ts`

```typescript
export interface StructuredSlackMessage {
  id: string;
  username: string;
  timestamp: string;
  date: string;
  text: string;
  is_thread_reply: boolean;
  reactions: Array<{ name: string; count: number }>;
  attachments: string[];
  files: string[];
  replies: StructuredSlackMessage[];
}

export interface StructuredChannelResponse {
  channel: string;
  days: number;
  messages: StructuredSlackMessage[];
  users: string[];
  total_count: number;
}
```

#### 7b. Add API method

```typescript
slackChannelMessagesStructured: (channel: string, days: number) =>
  fetchApi<StructuredChannelResponse>(
    `/slack/channel/${encodeURIComponent(channel)}/messages-structured?days=${days}`
  ),
```

**Files modified**:
- `frontend/src/lib/api.ts` — add types + API method

---

## File Summary

### New files (6)

| File | Purpose | Lines (est.) |
|------|---------|-------------|
| `frontend/src/lib/slack-formatting.ts` | Slack markup transforms, emoji map | ~200 |
| `frontend/src/components/slack/SlackMessage.tsx` | Rich message renderer | ~120 |
| `frontend/src/components/slack/SlackReactions.tsx` | Emoji reaction pills | ~40 |
| `frontend/src/components/slack/ThreadReplies.tsx` | Collapsible thread view | ~60 |
| `frontend/src/components/slack/FilterBar.tsx` | Search + user pill filters | ~180 |
| `frontend/src/components/slack/index.ts` | Barrel export | ~5 |

### Modified files (5)

| File | Changes | Lines changed (est.) |
|------|---------|---------------------|
| `backend/app/services/slack_service.py` | Add `parse_channel_messages()`, `MessageThread` dataclass | ~120 |
| `backend/app/api/slack.py` | Add `/messages-structured` endpoint | ~40 |
| `frontend/src/lib/api.ts` | Add types + API method | ~30 |
| `frontend/src/components/cards/ChannelMessagesModal.tsx` | Full rewrite: Dialog, structured data, filter bar, threaded messages | ~200 |
| `frontend/src/components/cards/SlackSummary.tsx` | Replace `MarkdownContent` with ReactMarkdown, update modal invocation | ~30 |
| `frontend/src/components/cards/ChannelDetailsModal.tsx` | Migrate to Dialog | ~20 |

**Total estimated new/changed code**: ~1,045 lines

---

## Implementation Order

```
Phase 7 (Types)  ──┐
                    ├──→ Phase 1 (Backend) ──→ Phase 2 (Rendering) ──→ Phase 3 (Threads)
Phase 4 (Modal)  ──┘                                                        │
                                                                            ▼
                                                              Phase 5 (Filters/Search)
                                                                            │
                                                                            ▼
                                                              Phase 6 (Summary fix)
```

**Recommended sequence**:

| Step | Phase | What | Effort | Cumulative |
|------|-------|------|--------|------------|
| 1 | 7 + 1 | Types, backend parser, new endpoint | 3.5h | 3.5h |
| 2 | 4 | Dialog migration, z-index fix | 2h | 5.5h |
| 3 | 2 | Slack formatting utils, SlackMessage component | 4h | 9.5h |
| 4 | 3 | Thread detection, collapsible replies | 2h | 11.5h |
| 5 | 5 | Filter bar, user pills, search | 3h | 14.5h |
| 6 | 6 | Summary markdown fix | 1h | 15.5h |

**Total estimated effort**: ~15.5 hours (2 solid days)

---

## Testing Plan

### Backend
- Unit test `parse_channel_messages()` against real markdown files
- Verify thread grouping: parent + N replies → single `MessageThread`
- Verify reaction parsing: `_Reactions: :eyes: 1 :thumbsup: 2_` → `[{name: "eyes", count: 1}, ...]`
- Verify user mention preservation: `<@U057YJUJ9KN>` passes through to frontend

### Frontend
- Emoji rendering: `:thumbsup:` → 👍, `:eyes:` → 👀, unknown `:custom:` → styled badge
- User mention highlighting: `<@U057YJUJ9KN>` → colored `@username` pill
- Thread collapse/expand: click toggles, auto-expands when search matches reply
- Search: debounced input, highlight matches in message text
- User pills: correct sort order, toggle filtering, +N more expansion
- z-index: open modal from dashboard, verify it appears above all elements
- Markdown in messages: `*bold*`, `_italic_`, `` `code` ``, links all render correctly
- HTML entities: `&amp;` → `&`, `&lt;` → `<`

### Integration
- Load channel with 100+ messages: verify no performance degradation
- Load channel with threads: verify correct grouping
- Filter by user + search simultaneously: verify AND logic
- Test with all team channels (compute, wx, g4, jobs, temporal)

---

## Dependencies

### Already installed (no new packages needed)
- `react-markdown` ^10.1.0 — markdown rendering
- `remark-gfm` ^4.0.1 — GitHub-flavored markdown tables, strikethrough
- `@/components/ui/collapsible` — Radix collapsible (for threads)
- `@/components/ui/dialog` — Radix dialog (for modal fix)
- `@/components/ui/input` — search box
- `@/components/ui/badge` — user pills

### No new npm packages required

The emoji shortcode map will be a static TypeScript object (~200 entries) bundled in `slack-formatting.ts`. No external emoji library needed.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Large channels (1000+ messages) cause slow rendering | Client-side filtering is fast for <5000 messages. If needed later, add virtual scrolling with `react-window`. |
| Thread grouping fails on malformed markdown | Fallback: treat all `↳` messages as top-level if parent can't be found |
| Emoji map incomplete | Start with top 200 from Slack's standard set. Unknown shortcodes render as styled `:name:` badges — visually acceptable |
| Dialog migration breaks existing modal behavior | Radix Dialog handles focus trapping, ESC to close, click-outside-to-close — all improvements over current DIY modal |
| Search on large datasets slow | N-gram index built once on load. Substring matching is O(n) on filtered set — fine for <5000 messages |

---

## Not in Scope (Future)

- **Pagination / infinite scroll**: Current approach loads all messages for the time window. Fine for 7-day and 30-day views. Revisit if we add 90-day views.
- **Real-time message updates**: Would require WebSocket or SSE. Current polling-based sync is sufficient.
- **User avatar images**: Would require Slack API calls per user. Could add later with cached user profiles.
- **Message editing / deletion tracking**: Would require storing message edit history from Slack API.
- **Cross-channel search**: Currently scoped to single channel modal. Could add a global search later.
- **Time-of-day filter**: User pills + search cover most filter needs. Time filter can be added to FilterBar if requested.
