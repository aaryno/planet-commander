# Commander Changelog

Development changelog with links to implementation artifacts. New agents: read this to understand what's been built, the patterns used, and where to find details.

---

## 2026-04-20 — Review Page: Pipeline Tab, Agent Spawn, Chat Rendering

**Artifact**: [20260420-0836-review-page-pipeline-and-chat-improvements.md](artifacts/20260420-0836-review-page-pipeline-and-chat-improvements.md)

Three review page improvements:
- **Pipeline tab rewrite** — hierarchical stages/jobs from GitLab API, with status rollups, expand/collapse, durations, and "Add to review" buttons that pre-populate the agent chat
- **Agent spawn fix** — `MRAgentPane` now uses `agentDetail(spawnResult.id)` instead of fragile JIRA key lookup, so ChatView+WebSocket always renders after spawn
- **Task notification XML parsing** — `<task-notification>` blocks in chat messages parsed into structured cards (status badge + markdown-rendered result) instead of raw XML

**Patterns introduced**:
- Backend: GitLab pipeline/jobs API integration (`get_mr_pipelines`)
- Frontend: `onAddToReview` callback chain (CenterPane → ReviewPage → AgentPane via `pendingPrompt`)
- Frontend: XML-to-structured-card parsing in `ChatMessage.tsx` (`parseTaskNotification`)

---

## 2026-04-02 — Agent Chat & Context Injection

**Artifacts** (in `dashboard/artifacts/`):
- [Agent Chat Interfaces Analysis](artifacts/20260401-agent-chat-interfaces-analysis.md) — Chat UI architecture review
- [Context Cart RFD](artifacts/20260402-context-cart-rfd.md) — Cart pattern for collecting context before agent spawn
- [Live Agent Context Matching](artifacts/20260402-live-agent-context-matching-rfd.md) — Auto-matching agents to MRs/tickets
- [Slack Live Context Injection](artifacts/20260402-slack-live-context-injection-rfd.md) — Injecting Slack messages into agent conversations
- [Slack Message Content Gap](artifacts/20260402-slack-message-content-gap-plan.md) — Plan for missing message content

---

## 2026-03-20 — Phase 2 Integrations & JIRA Enrichment

**Artifacts** (in `~/claude/artifacts/`):
- [Phase 2 Integration Summary](../artifacts/20260320-1930-phase2-integrations-summary.md) — 4 integrations in 2h10m, established 5-step EntityLink pattern
- [PagerDuty Context Integration](../artifacts/20260320-1730-pagerduty-context-integration-complete.md)
- [Grafana Alerts Context Integration](../artifacts/20260320-1800-grafana-alerts-context-integration-complete.md)
- [Artifact Indexing Context Integration](../artifacts/20260320-1830-artifact-indexing-context-integration-complete.md)
- [GitLab MRs Context Integration](../artifacts/20260320-1900-gitlab-mrs-context-integration-complete.md)
- [JIRA Enrichment MVP](../artifacts/20260320-2030-jira-enrichment-mvp-complete.md) — Bidirectional linking (JIRA ↔ Slack, PagerDuty)
- [Entity Enrichment Implementation](../artifacts/20260320-2210-entity-enrichment-implementation-complete.md)
- [URL Extraction & Review Workflow](../artifacts/20260320-2030-url-extraction-phase5-review-workflow-complete.md)
- [ECC-Commander Integration](../artifacts/20260320-2230-ecc-commander-integration-complete.md)
- [Commander API Client](../artifacts/20260320-1720-commander-api-client-complete.md)

**Key pattern**: EntityLink-based architecture — build infrastructure once (model, background job, UI card), then integrate new entity types in ~30 minutes via the 5-step pattern documented in [CLAUDE.md](CLAUDE.md#work-context-integration-pattern).

---

## 2026-03-17–18 — Phase 1 Foundation & Architecture

**Artifacts** (in `~/claude/artifacts/`):
- [Gap Analysis](../artifacts/20260317-1800-planet-commander-gap-analysis.md) — Current vs proposed state
- [Context Integration Complete](../artifacts/20260317-2045-context-integration-complete.md) — WorkContext, EntityLink models
- [Phases 2-5 Plan](../artifacts/20260317-2026-planet-commander-phases2-5-FINAL-COMPLETE.md)
- [Multi-Instance Plan](../artifacts/20260317-commander-multi-instance-plan.md)
- [Enrichment Opportunities](../artifacts/20260318-1430-commander-enrichment-opportunities.md)

---

## How to Add Entries

When completing Commander work, create an artifact in `dashboard/artifacts/` with the standard naming (`YYYYMMDD-HHMM-description.md`), then add an entry here with:
1. Date and title
2. Link to the artifact
3. 2-3 sentence summary of what changed
4. Key patterns introduced (so future agents can find them)
