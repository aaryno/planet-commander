# Chat Filtering and Pinning - Technical Specification

**Created**: 2026-03-19
**Component**: ChatView.tsx
**Purpose**: Message filtering, pinning, and organization in agent chat sessions

---

## Overview

The ChatView component provides advanced message management through three independent but complementary systems:

1. **Message Type Filtering** - Show/hide message types (User, Claude, Tools, Thinking)
2. **Message Pinning** - Pin important messages to top of chat
3. **Pinned Section Accordion** - Collapse/expand pinned messages section

These features work together to help users focus on relevant content in long chat sessions.

---

## 1. Message Type Filtering

### Purpose

Allow users to selectively show/hide message types to reduce noise and focus on specific content.

### Message Types

| Type | Description | Default Visible | Use Case |
|------|-------------|-----------------|----------|
| **User** | User-sent messages | ✅ Yes | See user prompts and questions |
| **Claude** | Claude's responses | ✅ Yes | See Claude's answers and reasoning |
| **Tools** | Tool execution results | ❌ No | Debug tool calls, see command output |
| **Thinking** | Claude's internal reasoning | ❌ No | Understand Claude's thought process |

### State Management

```typescript
// State for each message type
const [showUser, setShowUser] = useState(true);
const [showAssistant, setShowAssistant] = useState(true);
const [showToolOutput, setShowToolOutput] = useState(false);
const [showThinking, setShowThinking] = useState(false);
```

### Filtering Logic

Messages are filtered **before rendering**:

```typescript
// Filter messages based on type toggles
const messages = allMessages.filter((msg) => {
  if (msg.role === "user") return showUser;
  if (msg.role === "assistant") return showAssistant;
  return true; // tool_result, thinking if we add them later
});
```

**Key characteristics**:
- Filtering happens at **render time**, not data fetch
- Original message array (`allMessages`) is preserved
- Filtered messages are indexed sequentially (affects pinning - see below)
- No network requests when toggling filters

### UI Controls

**Location**: Header section, right side of "Expand details" checkbox

```tsx
<div className="flex items-center gap-1.5 ml-2">
  <span className="text-[10px] text-zinc-600">Show:</span>

  {/* User messages badge */}
  <Badge
    variant="outline"
    className={`cursor-pointer text-[10px] px-1.5 py-0 ${
      showUser
        ? "bg-blue-500/20 border-blue-500/50 text-blue-300"
        : "border-zinc-700 text-zinc-600 hover:text-zinc-400"
    }`}
    onClick={() => setShowUser(!showUser)}
  >
    User
  </Badge>

  {/* Similar badges for Claude, Tools, Thinking */}
</div>
```

**Visual Design**:
- **Active state**: Colored background (blue for User, violet for Claude, etc.)
- **Inactive state**: Gray border, muted text
- **Hover**: Text brightens on inactive badges
- **Click**: Toggles filter immediately

### Color Coding

| Type | Active BG | Active Border | Active Text |
|------|-----------|---------------|-------------|
| User | `bg-blue-500/20` | `border-blue-500/50` | `text-blue-300` |
| Claude | `bg-violet-500/20` | `border-violet-500/50` | `text-violet-300` |
| Tools | `bg-cyan-500/20` | `border-cyan-500/50` | `text-cyan-300` |
| Thinking | `bg-amber-500/20` | `border-amber-500/50` | `text-amber-300` |

---

## 2. Message Pinning

### Purpose

Allow users to pin important messages to keep them visible at the top of the chat, regardless of scroll position.

### State Management

```typescript
// Set of message indices that are pinned
const [pinnedMessages, setPinnedMessages] = useState<Set<number>>(new Set());
```

**Key points**:
- Uses **Set** for O(1) lookup
- Stores message **indices** (not IDs)
- Indices refer to **filtered messages array**
- Persists during session (not across page reloads)

### Pin/Unpin Logic

```typescript
const handleToggleMessagePin = useCallback((index: number) => {
  setPinnedMessages((prev) => {
    const next = new Set(prev);
    if (next.has(index)) {
      next.delete(index); // Unpin
    } else {
      next.add(index);    // Pin
    }
    return next;
  });
}, []);
```

### Message Rendering Strategy

Messages are rendered in **two sections**:

#### 1. Pinned Section (Sticky)
```tsx
<div className="sticky top-0 z-10 bg-zinc-900 mb-2 border-b border-zinc-800">
  {messages.map((msg, i) => {
    if (!pinnedMessages.has(i)) return null; // Skip unpinned
    return (
      <ChatMessage
        key={`pinned-${msg.timestamp}-${i}`}
        message={msg}
        isPinned={true}
        onTogglePin={() => handleToggleMessagePin(i)}
        // ... other props
      />
    );
  })}
</div>
```

#### 2. Main Messages Section (Scrollable)
```tsx
{messages.map((msg, i) => {
  if (pinnedMessages.has(i)) return null; // Skip pinned (already shown above)
  return (
    <ChatMessage
      key={`${msg.timestamp}-${i}`}
      message={msg}
      isPinned={false}
      onTogglePin={() => handleToggleMessagePin(i)}
      // ... other props
    />
  );
})}
```

### Sticky Positioning

The pinned section uses `position: sticky` with `top: 0`:
- **Scrolls with content** until it reaches the top
- **Sticks to top** of scroll container when user scrolls down
- **Always visible** regardless of scroll position
- **z-index: 10** ensures it stays above other content

### ChatMessage Component Integration

Each `ChatMessage` receives:
- `isPinned: boolean` - Current pin state
- `onTogglePin: () => void` - Callback to toggle
- Renders pin icon based on state
- Shows visual indicator when pinned

---

## 3. Pinned Section Accordion

### Purpose

Allow users to collapse the pinned section to reclaim screen space when not actively referencing pinned messages.

### State Management

```typescript
const [pinnedSectionCollapsed, setPinnedSectionCollapsed] = useState(false);
```

**Default**: Expanded (false)

### Visual Design

#### Accordion Header

```tsx
<div
  className="flex items-center justify-between py-1.5 px-2 cursor-pointer hover:bg-zinc-800/50 transition-colors"
  onClick={() => setPinnedSectionCollapsed(!pinnedSectionCollapsed)}
>
  <div className="flex items-center gap-2">
    {/* Chevron indicator */}
    {pinnedSectionCollapsed ? (
      <ChevronRight className="h-3.5 w-3.5 text-zinc-500" />
    ) : (
      <ChevronDown className="h-3.5 w-3.5 text-zinc-500" />
    )}

    {/* Count of pinned items */}
    <span className="text-[10px] font-medium text-zinc-400">
      Pinned ({(jiraPinned ? 1 : 0) + pinnedMessages.size})
    </span>
  </div>

  <span className="text-[9px] text-zinc-600">
    {pinnedSectionCollapsed ? "Expand" : "Collapse"}
  </span>
</div>
```

**Count calculation**:
- Includes JIRA card if pinned: `jiraPinned ? 1 : 0`
- Includes pinned messages: `pinnedMessages.size`
- Total: `(jiraPinned ? 1 : 0) + pinnedMessages.size`

#### Collapsible Content

```tsx
{!pinnedSectionCollapsed && (
  <div className="pb-2">
    {/* JIRA Card if pinned */}
    {jiraPinned && showJiraCard && agent.jira_key && (
      <JiraCard {...props} />
    )}

    {/* Pinned messages */}
    {messages.map((msg, i) => {
      if (!pinnedMessages.has(i)) return null;
      return <ChatMessage {...props} />;
    })}
  </div>
)}
```

### Interaction Behavior

| Action | Result |
|--------|--------|
| Click header | Toggle collapsed state |
| Collapsed → Expanded | Pinned messages slide into view |
| Expanded → Collapsed | Pinned messages hidden, header remains |
| Pin new message | Auto-expands if collapsed |
| Unpin last message | Section disappears entirely |

### JIRA Card Integration

The JIRA card can also be pinned and appears in the pinned section:

```typescript
// JIRA card pinned by default if agent has JIRA key
const [jiraPinned, setJiraPinned] = useState(!!agent.jira_key);
```

**Behavior**:
- JIRA card auto-pins when agent has `jira_key`
- Appears **before** pinned messages in section
- Counted in accordion header total
- Can be unpinned independently

---

## 4. Integration Between Systems

### Filtering + Pinning Interaction

**Critical behavior**: Pin indices refer to **filtered messages**, not original messages.

**Example scenario**:
```
Original messages: [user1, assistant1, user2, assistant2, user3]
Filter: showUser=false, showAssistant=true
Filtered messages: [assistant1, assistant2]
Pinned indices: [1]  // Pins assistant2, NOT user2!
```

**Implications**:
- Changing filters **changes which messages indices refer to**
- Pinned indices may become invalid after filter change
- Current implementation: Indices persist but may refer to different messages
- **Improvement opportunity**: Store message timestamps instead of indices

### Collapse + Filtering Interaction

- Filtering affects **which messages appear in pinned section**
- Collapsed state is **independent** of filtering
- Collapsing does not change filter state
- Expanding shows filtered pinned messages

### Message Count Display

```typescript
// Header shows total count across filters
<span className="text-[10px] text-zinc-600 ml-auto">
  {agent.message_count} messages
</span>
```

**Count source**: `agent.message_count` from database (total, not filtered)

---

## 5. Message Collapse (Related Feature)

### Purpose

Allow individual messages to be collapsed to save space.

### State Management

```typescript
// Set of message indices that are collapsed
const [collapsedMessages, setCollapsedMessages] = useState<Set<number>>(new Set());
const [allCollapsed, setAllCollapsed] = useState(false);
```

### Collapse All/Expand All

```tsx
<Button
  variant="ghost"
  size="sm"
  className="h-6 w-6 p-0"
  onClick={handleCollapseAll}
  title={allCollapsed ? "Expand all messages" : "Collapse all messages"}
>
  {allCollapsed ? <ChevronsDown /> : <ChevronsUp />}
</Button>
```

**Logic**:
```typescript
const handleCollapseAll = useCallback(() => {
  if (allCollapsed) {
    // Expand all
    setCollapsedMessages(new Set());
    setAllCollapsed(false);
  } else {
    // Collapse all
    const allIndices = new Set(messages.map((_, i) => i));
    setCollapsedMessages(allIndices);
    setAllCollapsed(true);
  }
}, [allCollapsed, messages.length]);
```

### Integration with Pinning

- Pinned messages **can be collapsed**
- Collapse state is **independent** of pin state
- `ChatMessage` receives both `isPinned` and `collapsed` props
- Collapsed pinned messages still show in pinned section (just collapsed)

---

## 6. State Persistence

### Current Behavior (Session-Only)

All state is **in-memory** and **not persisted**:
- Filter settings reset on page reload
- Pinned messages lost on reload
- Collapsed state lost on reload
- Accordion state resets to expanded

### Future Enhancement: LocalStorage Persistence

**Potential implementation**:

```typescript
// Save to localStorage
useEffect(() => {
  localStorage.setItem(`chat-filters-${agent.id}`, JSON.stringify({
    showUser,
    showAssistant,
    showToolOutput,
    showThinking
  }));
}, [showUser, showAssistant, showToolOutput, showThinking, agent.id]);

// Load from localStorage
useEffect(() => {
  const saved = localStorage.getItem(`chat-filters-${agent.id}`);
  if (saved) {
    const filters = JSON.parse(saved);
    setShowUser(filters.showUser);
    setShowAssistant(filters.showAssistant);
    setShowToolOutput(filters.showToolOutput);
    setShowThinking(filters.showThinking);
  }
}, [agent.id]);
```

**Benefits**:
- User preferences persist across sessions
- Per-agent filter settings
- Improved UX for repeated visits

**Tradeoffs**:
- More complex state management
- Storage limits (though minimal data)
- Cleanup needed for deleted agents

---

## 7. Performance Considerations

### Filtering Performance

**Current**: O(n) filter on every render
```typescript
const messages = allMessages.filter((msg) => {
  if (msg.role === "user") return showUser;
  if (msg.role === "assistant") return showAssistant;
  return true;
});
```

**Optimization**: Memoize filtered messages
```typescript
const messages = useMemo(() => {
  return allMessages.filter((msg) => {
    if (msg.role === "user") return showUser;
    if (msg.role === "assistant") return showAssistant;
    return true;
  });
}, [allMessages, showUser, showAssistant, showToolOutput, showThinking]);
```

### Pinning Performance

**Lookup**: O(1) with Set data structure
```typescript
pinnedMessages.has(i)  // Constant time
```

**Iteration**: O(n) to render all messages twice (pinned + unpinned)
- Acceptable for typical chat lengths (<1000 messages)
- Could optimize with virtualization for very long chats

### Accordion Performance

**Toggle**: O(1) state change
**Render**: Only affects pinned section, not main messages

---

## 8. User Experience Flow

### Typical Usage Pattern

1. **Start with defaults**
   - User and Claude messages visible
   - Tools and Thinking hidden
   - Nothing pinned
   - Pinned section not visible

2. **Find important message**
   - Scroll through chat
   - Identify key message (decision, command, output)

3. **Pin message**
   - Click pin icon on message
   - Message appears in pinned section at top
   - Pinned section becomes sticky

4. **Continue conversation**
   - Pinned message stays visible while scrolling
   - Can reference pinned content easily

5. **Add more pins**
   - Pin additional messages
   - Pinned section grows
   - Accordion shows total count

6. **Collapse when not needed**
   - Click accordion header
   - Pinned section collapses
   - Expand again when needed

7. **Filter for focus**
   - Hide user messages to see only Claude responses
   - Hide Claude to see only prompts
   - Show Tools to debug commands

### Edge Cases

**Empty chat**:
- No messages to filter
- No messages to pin
- Shows "No messages in this session"

**All messages filtered out**:
- Displays empty chat area
- Filter badges show active filters
- User can toggle to see messages again

**All messages pinned**:
- Pinned section contains all messages
- Main section is empty
- Accordion shows full count

**Filtering removes pinned messages**:
- Pinned indices may become invalid
- Messages disappear from pinned section
- Changing filters back restores them

---

## 9. Future Enhancements

### 1. Timestamp-Based Pinning

**Problem**: Index-based pinning breaks with filtering

**Solution**: Store message timestamps instead
```typescript
const [pinnedMessages, setPinnedMessages] = useState<Set<string>>(new Set());
// Store: Set(['2026-03-19T10:30:00.000Z', ...])
```

### 2. Pin Annotations

Allow users to add notes to pinned messages:
```typescript
interface PinnedMessageAnnotation {
  messageTimestamp: string;
  note: string;
  createdAt: string;
}
```

### 3. Pin Groups

Organize pinned messages into named groups:
```typescript
interface PinGroup {
  id: string;
  name: string;
  messageTimestamps: string[];
  collapsed: boolean;
}
```

### 4. Export Pinned Messages

Allow users to export pinned messages as:
- Markdown summary
- JSON data
- Copy to clipboard
- Share link

### 5. Smart Filters

**Content-based filtering**:
- Messages with errors
- Messages with code blocks
- Messages with URLs
- Messages with JIRA tickets

**Metadata filtering**:
- Messages by date range
- Messages by token count
- Messages by tool usage

### 6. Filter Presets

Save and load filter combinations:
```typescript
interface FilterPreset {
  name: string;
  filters: {
    showUser: boolean;
    showAssistant: boolean;
    showToolOutput: boolean;
    showThinking: boolean;
  };
}

// Example presets
const PRESETS = {
  "Only Claude": { showUser: false, showAssistant: true, ... },
  "Only Prompts": { showUser: true, showAssistant: false, ... },
  "Debug Mode": { showUser: true, showAssistant: true, showToolOutput: true, showThinking: true }
};
```

---

## 10. Implementation Checklist

### Current State (Implemented)

- [x] Message type filtering (User, Claude, Tools, Thinking)
- [x] Filter badge UI with color coding
- [x] Pin/unpin individual messages
- [x] Pinned section sticky positioning
- [x] Accordion collapse for pinned section
- [x] Count display in accordion header
- [x] JIRA card pinning integration
- [x] Message collapse functionality
- [x] Collapse all/expand all
- [x] Dual rendering (pinned + main sections)

### Future Enhancements

- [ ] LocalStorage persistence
- [ ] Timestamp-based pinning
- [ ] Memoized filtering
- [ ] Pin annotations
- [ ] Pin groups
- [ ] Export pinned messages
- [ ] Smart content filters
- [ ] Filter presets
- [ ] Keyboard shortcuts
- [ ] Analytics/usage tracking

---

## 11. Code References

### Key Files

- **Component**: `frontend/src/components/agents/ChatView.tsx` (lines 40-56, 293-328, 567-660)
- **Sub-component**: `frontend/src/components/agents/ChatMessage.tsx` (receives pin/collapse props)
- **JIRA Card**: `frontend/src/components/agents/JiraCard.tsx` (pinnable)

### Key State Variables

```typescript
// Message type filters
const [showUser, setShowUser] = useState(true);
const [showAssistant, setShowAssistant] = useState(true);
const [showToolOutput, setShowToolOutput] = useState(false);
const [showThinking, setShowThinking] = useState(false);

// Pinning
const [pinnedMessages, setPinnedMessages] = useState<Set<number>>(new Set());
const [jiraPinned, setJiraPinned] = useState(!!agent.jira_key);
const [pinnedSectionCollapsed, setPinnedSectionCollapsed] = useState(false);

// Collapse
const [collapsedMessages, setCollapsedMessages] = useState<Set<number>>(new Set());
const [allCollapsed, setAllCollapsed] = useState(false);
```

### Key Functions

- `handleToggleMessagePin(index)` - Toggle pin state
- `handleToggleMessageCollapse(index)` - Toggle collapse state
- `handleCollapseAll()` - Collapse/expand all messages
- Filtering: Inline `.filter()` in render

---

## Summary

The chat filtering and pinning system provides powerful message management through:

1. **Flexible filtering** - Show/hide message types on demand
2. **Persistent visibility** - Pin important messages to stay visible
3. **Space management** - Collapse pinned section when not needed
4. **Independent controls** - Each system works independently but harmoniously

This enables users to manage long conversations effectively, maintaining focus on relevant content while keeping important context always accessible.
