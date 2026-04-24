# Slack Summarization Hang Fix

## Problem

Clicking "Summarize" causes the UI to hang indefinitely showing "Claude is summarizing Compute messages..." with no timeout or error feedback.

## Root Causes Identified

1. **Backend not running**: Containers `planet-ops-backend` and `planet-ops-frontend` are not active
   - `planet-ops-db`: Running (healthy)
   - `planet-ops-frontend`: Exited 3 days ago
   - `planet-ops-backend`: Not found

2. **No timeout feedback**: Frontend waited indefinitely without showing error
3. **No progress logging**: Backend didn't log summarization progress
4. **Short timeout**: Original 60s timeout too short for large summarizations

## Fixes Applied

### 1. Extended Backend Timeout

**Before**: 60 seconds max wait
```python
for _ in range(120):  # 120 * 0.5s = 60s max
    await asyncio.sleep(0.5)
    if not session.is_processing:
        break
```

**After**: 120 seconds (2 minutes) with progress logging
```python
max_wait_seconds = 120  # 2 minutes
iterations = max_wait_seconds * 2
for i in range(iterations):
    await asyncio.sleep(0.5)
    if not session.is_processing:
        logger.info(f"Summarization completed after {i * 0.5}s")
        break
    if i % 20 == 0:  # Log every 10 seconds
        logger.info(f"Summarization still in progress... {i * 0.5}s elapsed")
else:
    # Timed out - clean up and return error
    logger.warning(f"Summarization timed out after {max_wait_seconds}s")
    _summary_cache.pop(in_progress_key, None)
    session.unsubscribe_stdout(capture_broadcast)
    raise HTTPException(
        status_code=504,
        detail="Summarization timed out after 120s. Try reducing the number of days or syncing fewer channels."
    )
```

### 2. Frontend Timeout Detection

**Added 30-second warning**:
```typescript
const timeoutId = setTimeout(() => {
  if (isSummarizing) {
    setError("Summarization is taking longer than expected. The backend may be processing a large amount of messages. Please wait or try again.");
  }
}, 30000);
```

### 3. Better Error Messages

**Connection failures now show**:
```
"Connection to backend failed. Please ensure the backend is running (docker-compose up)."
```

Instead of generic:
```
"Failed to summarize"
```

### 4. Progress Logging

Backend now logs every 10 seconds:
```
INFO [app.api.slack] Summarization still in progress... 10.0s elapsed
INFO [app.api.slack] Summarization still in progress... 20.0s elapsed
INFO [app.api.slack] Summarization still in progress... 30.0s elapsed
...
INFO [app.api.slack] Summarization completed after 45.5s
```

## How to Fix Running State

### Start Backend (Recommended)

```bash
cd ~/claude/dashboard
docker-compose up -d
```

This starts:
- `planet-ops-db` (PostgreSQL)
- `planet-ops-backend` (FastAPI)
- `planet-ops-frontend` (Next.js)

### Check Status

```bash
docker ps --filter "name=planet-ops"
```

Should show all 3 containers running:
```
planet-ops-db         Up X hours (healthy)
planet-ops-backend    Up X hours
planet-ops-frontend   Up X hours
```

### View Logs

```bash
# Backend logs (see summarization progress)
docker logs -f planet-ops-backend

# Frontend logs
docker logs -f planet-ops-frontend
```

## Debugging Stuck Summarization

### 1. Check Backend Status
```bash
docker ps --filter "name=backend"
```

If not running:
```bash
cd ~/claude/dashboard
docker-compose up -d backend
```

### 2. Monitor Summarization
```bash
docker logs -f planet-ops-backend | grep -i summar
```

You should see:
```
INFO [app.api.slack] Summarization still in progress... 10.0s elapsed
INFO [app.api.slack] Summarization still in progress... 20.0s elapsed
INFO [app.api.slack] Summarization completed after 45.5s
```

### 3. Check for Errors
```bash
docker logs planet-ops-backend --tail 100 | grep ERROR
```

Common errors:
- **"Failed to spawn summarize agent"**: Claude Code not accessible
- **"Failed to read messages"**: Slack data directory not mounted
- **Timeout after 120s**: Too many messages, reduce days or sync fewer channels

### 4. Test with Smaller Dataset

If summarization times out:
```
1. Reduce days: 7d → 1d
2. Use smaller team: temporal, jobs (fewer channels)
3. Check Slack data: ~/tools/slack/data/messages/
```

## Files Modified

```
backend/app/api/slack.py
  - Extended timeout 60s → 120s
  - Added progress logging every 10s
  - Added proper timeout error handling
  - Clean up in-progress flag on timeout

frontend/src/components/cards/SlackSummary.tsx
  - Added 30s timeout warning
  - Better error messages for connection failures
  - Detect network errors specifically
```

## Expected Timeline

Typical summarization times:
- **1 day, 1 channel**: 5-15 seconds
- **7 days, 3 channels**: 20-45 seconds
- **30 days, 5 channels**: 60-90 seconds

If exceeding 120 seconds:
- Too many messages (reduce days)
- Too many channels (select specific team)
- Backend performance issue (check logs)

## User Experience

### Before
```
Click Summarize → Spinner forever → No feedback → Browser tab hangs
```

### After
```
Click Summarize
  ↓
Spinner with "Claude is summarizing..."
  ↓ (30s)
Warning: "Taking longer than expected... please wait"
  ↓ (continue)
Summary appears
  OR
  ↓ (120s)
Error: "Timed out after 120s. Try reducing days."
```

## Prevention

1. **Always check backend status** before using dashboard
2. **Start with small datasets** (1-7 days) to test
3. **Monitor logs** during first summarization
4. **Reduce scope** if timeouts occur

## Testing

1. **Start backend**:
   ```bash
   cd ~/claude/dashboard
   docker-compose up -d
   ```

2. **Test small summarization** (should complete <30s):
   - Team: temporal
   - Days: 1d
   - Click Summarize

3. **Monitor logs**:
   ```bash
   docker logs -f planet-ops-backend
   ```

4. **Verify completion**:
   - Summary appears
   - No errors in console
   - Status clears properly
