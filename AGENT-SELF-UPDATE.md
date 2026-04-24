# Agent Self-Update API

Agents running in the Commander Dashboard can update their own metadata using the self-update API.

## Update Your JIRA Ticket

When you create or discover a JIRA ticket related to your work, register it with the dashboard:

```bash
curl -X PATCH "http://backend:9000/api/agents/self?session_id=$CLAUDE_SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"jira_key": "COMPUTE-2152"}'
```

**When to use this:**
- After creating a new JIRA ticket for your task
- When you discover your work is related to an existing ticket
- When switching focus to a different ticket

## Update Your Project

Register or change your project association:

```bash
curl -X PATCH "http://backend:9000/api/agents/self?session_id=$CLAUDE_SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"project": "wx"}'
```

## Update Your Title

Change how you appear in the dashboard:

```bash
curl -X PATCH "http://backend:9000/api/agents/self?session_id=$CLAUDE_SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"title": "Implementing OOM detection"}'
```

## Update Multiple Fields

You can update multiple fields at once:

```bash
curl -X PATCH "http://backend:9000/api/agents/self?session_id=$CLAUDE_SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"jira_key": "COMPUTE-2152", "project": "wx", "title": "Fix memory leak in task manager"}'
```

## Environment Variables

The `$CLAUDE_SESSION_ID` environment variable is automatically available in your environment. The backend endpoint is accessible at `http://backend:9000` from within the agent process.

## Response

On success, you'll receive the updated agent object:

```json
{
  "id": "...",
  "jira_key": "COMPUTE-2152",
  "project": "wx",
  "title": "Fix memory leak in task manager",
  ...
}
```

## Benefits

Updating your metadata helps:
- **Team visibility**: Others can see what ticket you're working on
- **Context awareness**: Your JIRA context is automatically included in future messages
- **Organization**: Makes it easier to find and filter agents by project/ticket
- **Handoff**: Makes it easier for other agents or team members to continue your work
