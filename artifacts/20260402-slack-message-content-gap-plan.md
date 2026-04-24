# Plan: Fix Slack Thread Message Content Gap

**Date**: 2026-04-02
**Author**: Aaryn Olsson
**Status**: Ready to implement
**Blocked by**: Nothing — can start immediately

---

## Problem

Slack threads are stored without message content. This breaks the entire context matching pipeline.

### Root Cause

Two ingestion paths create SlackThread records:

| Path | Source | Frequency | Stores `messages`? | Stores `gitlab_mr_refs`? |
|------|--------|:---------:|:------------------:|:------------------------:|
| `sync-all-to-db.py` | Slack channel markdown files | 24h (launchd) | **NO** | **NO** |
| `slack_thread_sync` | JIRA description URLs → Slack API | 1h | Yes | Yes |

**`sync-all-to-db.py`** creates 99.8% of recent threads (667 of 668 in last 7 days). It inserts:
- channel_id, channel_name, thread_ts, permalink
- title (first line of first message)
- participant_count, message_count
- jira_keys (regex on title text)
- pagerduty_incident_ids (regex on title text)

It does **NOT** insert:
- `messages` JSONB (NULL)
- `gitlab_mr_refs` (NULL)
- `cross_channel_refs` (NULL)

### Impact

Without `messages`:
- `detect_cross_references()` has nothing to scan → no MR refs, no branch mentions
- `find_agents_for_thread()` branch matching scans message text → finds nothing
- `backfill_agent_context()` scans message text → finds nothing
- Context queue never gets populated for most threads

**The entire context matching system is blind to 99.8% of Slack threads.**

### Concrete Example

Aaryn posted in #wx-dev:
> "this doesnt look like it needs approval but I would like a review anyway https://hello.planet.com/code/build-deploy/planet-idp/components/rbac-resources/-/merge_requests/74"

This thread (`c6283a51`) has:
- `title`: the message text (truncated)
- `messages`: NULL
- `gitlab_mr_refs`: NULL

The MR URL is right there in the title but never extracted.

---

## Fix

Two changes, both in `~/tools/db/sync-all-to-db.py`:

### Fix 1: Store message content

When inserting/updating threads, include the message text in the `messages` JSONB field.

The sync script already has access to the full message text (it uses it for the `title` field). Store it as a single-element array:

```python
messages_json = json.dumps([{
    "text": text,
    "user": thread.get("user", "unknown"),
    "ts": ts,
}])
```

Add to the INSERT:
```sql
messages = %(messages)s::jsonb
```

And to the ON CONFLICT UPDATE:
```sql
messages = COALESCE(EXCLUDED.messages, slack_threads.messages)
```

(Don't overwrite richer message data from the Slack API sync with our single-message version.)

### Fix 2: Extract cross-references from available text

After constructing the thread data, run cross-reference detection on the text:

```python
# Extract MR refs from text
mr_refs = list(set(
    re.findall(r'merge_requests/(\d+)', text) +
    re.findall(r'!(\d+)', text)
))
gitlab_mr_refs = [f"!{ref}" for ref in mr_refs] if mr_refs else None

# Extract channel refs
channel_refs = list(set(re.findall(r'#([a-z0-9_-]+)', text))) or None
```

Add to the INSERT:
```sql
gitlab_mr_refs = %(mr_refs)s::jsonb,
cross_channel_refs = %(channel_refs)s::jsonb
```

And to the ON CONFLICT UPDATE:
```sql
gitlab_mr_refs = COALESCE(EXCLUDED.gitlab_mr_refs, slack_threads.gitlab_mr_refs),
cross_channel_refs = COALESCE(EXCLUDED.cross_channel_refs, slack_threads.cross_channel_refs)
```

### Fix 3: Backfill existing threads

After deploying the fix, run a one-time update to populate `messages` and `gitlab_mr_refs` for existing threads that have titles but NULL messages:

```sql
UPDATE slack_threads
SET messages = jsonb_build_array(jsonb_build_object(
        'text', title,
        'user', 'unknown',
        'ts', thread_ts
    )),
    gitlab_mr_refs = (
        SELECT jsonb_agg(DISTINCT '!' || match)
        FROM regexp_matches(title, 'merge_requests/(\d+)', 'g') AS m(match)
        WHERE title ~ 'merge_requests/\d+'
    )
WHERE messages IS NULL
  AND title IS NOT NULL
  AND start_time > now() - interval '14 days';
```

---

## Files Modified

| File | Change |
|------|--------|
| `~/tools/db/sync-all-to-db.py` | Add `messages`, `gitlab_mr_refs`, `cross_channel_refs` to INSERT |
| Database (one-time) | Backfill SQL for existing threads |

---

## Execution

1. Edit `sync-all-to-db.py` (Fix 1 + Fix 2) — ~15 min
2. Run backfill SQL (Fix 3) — ~1 min
3. Verify: thread `c6283a51` should now have `messages` and `gitlab_mr_refs = ["!74"]`
4. Re-run `sync-all-to-db.py` to populate recent threads
5. Test: PATCH agent with JIRA key → backfill should find matching threads

---

## Validation

After implementation:

```sql
-- Should be mostly non-NULL now
SELECT
  count(*) FILTER (WHERE messages IS NOT NULL) as has_msgs,
  count(*) FILTER (WHERE messages IS NULL) as null_msgs,
  count(*) FILTER (WHERE gitlab_mr_refs IS NOT NULL AND gitlab_mr_refs::text != '[]' AND gitlab_mr_refs::text != 'null') as has_mr_refs
FROM slack_threads
WHERE start_time > now() - interval '7 days';
```

Expected: `has_msgs` ≈ 668, `null_msgs` ≈ 0, `has_mr_refs` > 0.
