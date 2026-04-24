# Slack Message Formatting Improvements

## Problem

Slack messages were displayed as raw markdown with ugly link syntax:
```
**Gitlab** `20:57:16`
Dharma Bellamkonda (dharmab) merged merge request <https://hello.planet.com/code/product/compute-meta/-/merge_requests/55|!55 *add wx gcp projects to compute-meta management*> in <https://hello.planet.com/code/product/compute-meta|product / compute-meta>
```

Also:
- Clicking channel name would trigger summarization (wrong)
- Modal was too tall (90vh)
- Links weren't clickable

## Solution

### 1. Parse Slack Link Format

Slack uses `<URL|text>` or `<URL>` format for links. Now parsed into clickable `<a>` tags.

**Link formats handled**:
```
<https://example.com|Link Text>  → Link Text (clickable)
<https://example.com>             → https://example.com (clickable)
```

### 2. Format Messages Nicely

Messages now displayed with:
- **Date headers**: "2026-03-12" (gray, semibold)
- **Username + timestamp**: "Dharma Bellamkonda" + "20:57:16" (on same line)
- **Message content**: Properly spaced with clickable links
- **Link styling**: Blue, underlined, hover effect

**Example output**:
```
Dharma Bellamkonda  20:57:16
merged merge request !55 add wx gcp projects to compute-meta management in product / compute-meta
                    ^^^^ clickable                                          ^^^^^^^^^^^^^^^^^^^^^ clickable
```

### 3. Changed Modal Size

- **Before**: `max-h-[90vh]` (too tall, modal dominated screen)
- **After**: `max-h-[600px]` (card-sized, ~same height as JIRA card)

### 4. Made Channel Name Clickable

- **Before**: Eye icon only
- **After**: Channel name itself is clickable
- **Action**: Opens message viewer (not summarize)

## Implementation Details

### SlackMessageContent Component

New React component that:
1. Splits content by lines
2. Identifies date headers (`## Date`)
3. Identifies message headers (`**User** \`timestamp\``)
4. Groups message content
5. Formats each line with link parsing

### formatSlackLine Function

Parses Slack link syntax using regex:
```typescript
/<(https?:\/\/[^|>]+)(?:\|([^>]+))?>/g
```

Extracts:
- URL (always)
- Link text (optional, after `|`)

Renders as:
```tsx
<a href={url} target="_blank" className="text-blue-400 hover:text-blue-300 underline">
  {linkText || url}
</a>
```

### Message Structure

```
## 2026-03-12              ← Date header (gray, semibold)

**Username** `HH:MM:SS`    ← Message header (username bold, timestamp small)
Message content with       ← Content (gray, normal)
<URL|clickable links>      ← Links (blue, underlined)

**Next User** `HH:MM:SS`   ← Next message
More content...
```

## Changes Made

### ChannelMessagesModal.tsx

1. **Modal height**: `max-h-[90vh]` → `max-h-[600px]`
2. **Content parsing**: New `SlackMessageContent` component
3. **Link formatting**: New `formatSlackLine` function
4. **React import**: Added for `React.ReactNode` types

### SlackSummary.tsx

1. **Channel name**: Changed from `<span>` to `<button>`
2. **Click action**: Opens message viewer
3. **Hover effect**: Blue highlight on hover

## User Experience

### Before
```
Raw markdown display:
<https://hello.planet.com/code/product/compute-meta/-/merge_requests/55|!55 *add wx gcp projects*>
                                                                         ^ not clickable, ugly syntax
```

### After
```
Nice formatted display:
!55 add wx gcp projects
^^^ clickable blue link, clean appearance
```

### Modal Interaction

**Before**:
- Click eye icon → Modal opens (huge, 90% screen)
- Can't click channel name

**After**:
- Click channel name OR eye icon → Modal opens (card-sized)
- Scrollable content
- Clickable links
- Clean formatting

## Testing

### Link Parsing
```
Input:  <https://example.com|Click Me>
Output: <a href="https://example.com">Click Me</a>

Input:  <https://example.com>
Output: <a href="https://example.com">https://example.com</a>

Input:  Text before <https://example.com|link> and after
Output: Text before <a>link</a> and after
```

### Message Formatting
```
Input:
## 2026-03-12
**John Doe** `14:30:00`
Message with <https://example.com|a link>

Output:
2026-03-12           (gray header)
John Doe  14:30:00   (bold + timestamp)
Message with a link  (clickable blue)
```

## Files Modified

```
frontend/src/components/cards/ChannelMessagesModal.tsx
  - Changed max-h-[90vh] to max-h-[600px]
  - Added SlackMessageContent component
  - Added formatSlackLine function
  - Added React import for ReactNode

frontend/src/components/cards/SlackSummary.tsx
  - Changed channel name from span to button
  - Added onClick handler to open viewer
  - Added hover styling
```

## Edge Cases Handled

1. **Multiple links in one line**: All parsed correctly
2. **Links with special characters**: URL-encoded properly
3. **Links without text**: Shows full URL
4. **Empty messages**: Skipped gracefully
5. **Malformed links**: Falls back to plain text
6. **Long messages**: Scrollable within modal

## Future Enhancements

- [ ] Parse Slack @mentions (`<@U12345|username>`)
- [ ] Parse Slack channels (`<#C12345|channel-name>`)
- [ ] Parse Slack emojis (`:thumbsup:` → 👍)
- [ ] Parse code blocks (` ```code``` `)
- [ ] Parse bold/italic markdown
- [ ] Thread view for replies
