# Slack Sync SSE Implementation

## Summary

Added Server-Sent Events (SSE) for real-time Slack sync progress updates. The sync button now shows live status instead of just a spinner.

## Problem

When clicking "Sync" in the Slack Summary card, the button would just show a spinner with no indication of:
- What channel is being synced
- How many messages are being fetched
- How recent the messages are
- Progress through multiple channels

## Solution

Implemented SSE streaming endpoint that provides real-time progress updates as channels are synced.

## Changes Made

### Backend

1. **`/backend/app/services/slack_service.py`**
   - Added `sync_channels_streaming()` async generator
   - Yields progress updates for each channel:
     - `status: "syncing"` - Currently syncing a channel
     - `status: "complete"` - All channels synced
     - `status: "error"` - Sync failed
   - Parses sync script output for message counts
   - Calculates relative age of last message ("13m", "2h", "3d")

2. **`/backend/app/api/slack.py`**
   - Added `/sync-stream` GET endpoint
   - Returns `StreamingResponse` with `text/event-stream` media type
   - Proper SSE headers (no-cache, keep-alive, no-buffering)
   - JSON-encoded data events

### Frontend

3. **`/frontend/src/components/cards/SlackSummary.tsx`**
   - Added `syncStatus` state for live progress messages
   - Rewrote `handleSync()` to use EventSource API
   - Shows status in footer replacing normal stats during sync
   - Auto-clears status 3 seconds after completion

## User Experience

### Before
```
[Sync button with spinner] → no feedback → done
```

### After
```
Click Sync
  ↓
"Connecting..."
  ↓
"Syncing compute-platform (1/3)"
  ↓
"Syncing compute-platform (1/3) · 12 messages"
  ↓
"Syncing compute-platform-info (2/3) · 25 messages"
  ↓
"Syncing compute-platform-warn (3/3) · 38 messages"
  ↓
"Complete · 38 messages · Last: 13m ago"
  ↓
(3 second delay)
  ↓
Back to normal stats display
```

## Technical Details

### SSE Event Format

```json
data: {
  "status": "syncing",
  "channel": "compute-platform",
  "channel_index": 1,
  "total_channels": 3,
  "messages_synced": 12
}

data: {
  "status": "complete",
  "total_channels": 3,
  "messages_synced": 38,
  "last_message_time": "2026-03-12",
  "last_message_age": "13m"
}
```

### Message Age Calculation

Relative time from most recent message file:
- `< 1h` → "13m"
- `< 24h` → "5h"
- `>= 24h` → "3d"

### Error Handling

- Connection fails → Shows "Sync connection failed"
- Sync script times out → Individual channel marked as timeout
- Parse error → Logged to console, continues with other channels

## Future Enhancements

### TODO: Add SSE to JIRA Sync

Similar implementation needed for JIRA ticket syncing:

```
/api/jira/sync-stream?project=COMPUTE

Events:
- "Fetching tickets... X/Y complete"
- "Found X new/updated tickets"
- "Last updated: 5m ago"
```

See TODO comment in `/backend/app/api/jira.py`

## Testing

1. **Start Dashboard**:
   ```bash
   cd ~/claude/dashboard
   docker-compose up
   ```

2. **Open Slack Summary Card**

3. **Click "Sync"**:
   - Should see "Connecting..."
   - Then "Syncing {channel} (X/Y)" updates
   - Then "Complete · X messages · Last: Xm ago"
   - Status clears after 3 seconds

4. **Check Browser DevTools**:
   - Network tab → EventSource connection to `/api/slack/sync-stream`
   - Should see streaming events coming through

## Files Modified

```
backend/app/services/slack_service.py
  - Added sync_channels_streaming() generator

backend/app/api/slack.py
  - Added /sync-stream GET endpoint
  - Import json, StreamingResponse

frontend/src/components/cards/SlackSummary.tsx
  - Added syncStatus state
  - Rewrote handleSync() to use EventSource
  - Updated footer to show sync status

backend/app/api/jira.py
  - Added TODO comment for JIRA SSE implementation
```

## Debugging

### If SSE doesn't work:

1. **Check backend logs**:
   ```bash
   docker logs planet-ops-backend
   ```

2. **Check EventSource in browser console**:
   ```javascript
   const es = new EventSource('/api/slack/sync-stream?team=compute')
   es.onmessage = (e) => console.log(JSON.parse(e.data))
   ```

3. **Verify SSE headers**:
   ```
   Content-Type: text/event-stream
   Cache-Control: no-cache
   Connection: keep-alive
   ```

4. **Check nginx/proxy buffering**:
   - Header `X-Accel-Buffering: no` disables nginx buffering
   - Critical for SSE to work through reverse proxies

## Benefits

1. **Better UX** - Users know what's happening during sync
2. **Progress visibility** - See which channel is being processed
3. **Message counts** - Know how much data was synced
4. **Recency info** - "Last: 13m ago" shows data freshness
5. **Error feedback** - Specific errors instead of generic failures
6. **No polling** - Efficient real-time updates via SSE
