# Slack Channel Actions - Implementation Summary

**Date**: 2026-03-12
**Changes**: Added View and Details actions for Slack channels + improved error handling

## Features Added

### 1. View Messages Modal
- **Trigger**: Eye icon button on channel hover
- **Displays**: Scrollback of messages for the selected time period
- **Endpoint**: `GET /api/slack/channel/{channel}/messages?days={days}`
- **Component**: `ChannelMessagesModal.tsx`

### 2. Details Modal
- **Trigger**: Info icon button on channel hover
- **Displays**:
  - Earliest message date
  - Latest message date
  - Total message count (all time)
  - Last day message count
  - 7-day average messages/day
  - Total files stored
- **Endpoint**: `GET /api/slack/channel/{channel}/details`
- **Component**: `ChannelDetailsModal.tsx`

## Backend Changes

### New API Endpoints

**`/api/slack/channel/{channel}/messages`**
- Returns message content for a single channel
- Parameters: `days` (1-90)
- Response: `{ channel, content, days }`

**`/api/slack/channel/{channel}/details`**
- Returns detailed statistics for a channel
- Response includes:
  - `earliest_date` / `latest_date`
  - `total_messages` (all time)
  - `last_day_count`
  - `last_week_avg`
  - `total_files`

### Error Handling Improvements

**Fixed 500 Error on Summarize**:
1. Added try/catch around `get_team_messages()` with detailed error logging
2. Added error logging in `capture_broadcast()` callback
3. Added `exc_info=True` to all logger.error() calls for full stack traces
4. Added try/catch around session termination
5. Better error messages in HTTPExceptions

**Error Locations**:
- `/api/slack/summarize` - improved error handling throughout
- Error logs include full exception details via `exc_info=True`

## Frontend Changes

### Modified Files

**`SlackSummary.tsx`**:
- Added state for `viewingChannel` and `detailsChannel`
- Added Eye and Info icon buttons (visible on hover)
- Channel rows now have hover effects
- Renders modals when channels are selected

**`api.ts`**:
- Added `slackChannelMessages()` API function
- Added `slackChannelDetails()` API function
- Added `SlackChannelDetails` interface

**`OpenMRs.tsx`** (Bug fix):
- Fixed `refetch` → `refresh` (usePoll returns `refresh`, not `refetch`)

### New Components

**`ChannelMessagesModal.tsx`**:
- Full-screen modal with scrollable message view
- Displays raw markdown content in monospace
- Loading states and error handling

**`ChannelDetailsModal.tsx`**:
- Compact modal showing channel statistics
- Organized into sections: Date Range, Message Counts, Activity
- Icon indicators for each section

## UI/UX

### Channel Row Interaction
```
[#channel-name]  [🔍 View] [ℹ️ Details]  [last_activity]  [count]
                  ↑ appears on hover
```

### Hover States
- Channel rows have subtle background change on hover
- Action buttons fade in on hover (opacity 0 → 100)
- Button colors: View (blue), Details (emerald)

### Modal Design
- Dark theme consistent with dashboard
- Click outside to close (backdrop)
- X button in header
- Responsive sizing (max-w-4xl for messages, max-w-md for details)

## Testing

### Backend Endpoints
```bash
# Test details
curl "http://localhost:9000/api/slack/channel/compute-platform/details"

# Test messages
curl "http://localhost:9000/api/slack/channel/compute-platform/messages?days=1"
```

### Example Response
```json
{
  "channel": "compute-platform",
  "earliest_date": "2018-06-26",
  "latest_date": "2026-03-12",
  "total_messages": 149674,
  "last_day_count": 37,
  "last_week_avg": 35.0,
  "total_files": 2258
}
```

## Known Issues Fixed

1. **500 Error on Summarize**: Added comprehensive error handling and logging
2. **OpenMRs refetch undefined**: Changed to use `refresh` (correct return from usePoll)

## Next Steps

To see the changes in action:
1. Backend auto-reloads (uvicorn --reload)
2. Frontend: `cd frontend && npm run dev`
3. Navigate to Slack section
4. Hover over any channel to see View/Details buttons
5. Test the modals

## Files Modified

### Backend
- `backend/app/api/slack.py` - Added endpoints, improved error handling
- `backend/app/services/slack_service.py` - Exported helper functions

### Frontend
- `frontend/src/components/cards/SlackSummary.tsx` - Added actions and modals
- `frontend/src/components/cards/ChannelMessagesModal.tsx` - NEW
- `frontend/src/components/cards/ChannelDetailsModal.tsx` - NEW
- `frontend/src/lib/api.ts` - Added API functions and interface
- `frontend/src/components/cards/OpenMRs.tsx` - Fixed refetch bug
