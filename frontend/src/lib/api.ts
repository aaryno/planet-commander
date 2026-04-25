const API_BASE = "/api";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  health: () => fetchApi<{ status: string }>("/health"),
  labels: () => fetchApi<{ labels: Record<string, Array<{ id: number; name: string; color: string }>> }>("/labels"),
  layout: (page: string = "dashboard") => fetchApi<{ page: string; layout: Array<{ i: string; x: number; y: number; w: number; h: number }>; updated_at?: string }>(`/layout?page=${page}`),
  saveLayout: (page: string, layout: Array<{ i: string; x: number; y: number; w: number; h: number }>) =>
    fetchApi<{ page: string; layout: Array<{ i: string; x: number; y: number; w: number; h: number }>; updated_at: string }>("/layout", {
      method: "PUT",
      body: JSON.stringify({ page, layout }),
    }),
  projectLinks: (project: string) => fetchApi<{ project: string; links: Record<string, Array<{ label: string; url: string; icon: string }>> }>(`/projects/${project}/links`),
  agents: (project?: string) => fetchApi<{ agents: Agent[]; total: number }>(`/agents${project ? `?project=${project}` : ""}`),
  agentsSearch: (query?: string, jiraKey?: string) => {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (jiraKey) params.set("jira_key", jiraKey);
    return fetchApi<{ results: Agent[]; total: number }>(`/agents/search?${params.toString()}`);
  },
  agentsByJira: (jiraKey: string) => fetchApi<{ agents: Agent[]; total: number }>(`/agents/by-jira/${jiraKey}`),
  agentDetail: (id: string) => fetchApi<Agent>(`/agents/${id}`),
  agentHistory: (id: string, expand?: boolean) => fetchApi<{ messages: ChatMessage[] }>(`/agents/${id}/history${expand ? "?expand=true" : ""}`),
  agentArtifactContent: (id: string, path: string) => fetchApi<ArtifactContent>(`/agents/${id}/artifact-content?path=${encodeURIComponent(path)}`),
  agentSummary: (id: string) => fetchApi<AgentSummary>(`/agents/${id}/summary`),
  agentSummarize: (id: string) => fetchApi<AgentSummary>(`/agents/${id}/summarize`, { method: "POST" }),
  agentSync: () => fetchApi<{ synced: number; new: number; updated: number }>("/agents/sync", { method: "POST" }),
  agentChat: (id: string, message: string, model?: string, source?: string) => fetchApi<{ sent: boolean; pid: number; message: string }>(`/agents/${id}/chat`, {
    method: "POST",
    body: JSON.stringify({ message, model, source }),
  }),
  agentResume: (id: string) => fetchApi<{ status: string; pid: number; session_id: string }>(`/agents/${id}/resume`, {
    method: "POST",
  }),
  agentSpawn: (opts: {
    working_directory?: string;
    project?: string;
    initial_prompt?: string;
    jira_key?: string;
    worktree_path?: string;
    worktree_branch?: string;
    model?: string;
    source?: string;
  }) =>
    fetchApi<{ id: string; session_id: string; pid: number; status: string; managed_by: string; worktree_path?: string; git_branch?: string }>("/agents", {
      method: "POST",
      body: JSON.stringify(opts),
    }),
  agentCartLaunch: (opts: {
    source_agent_ids: string[];
    project: string;
    initial_prompt?: string;
    jira_key?: string;
    worktree_path?: string;
    worktree_branch?: string;
    model?: string;
    context_preamble?: string;
  }) =>
    fetchApi<{
      id: string;
      session_id: string;
      pid: number;
      status: string;
      managed_by: string;
      worktree_path?: string;
      git_branch?: string;
      source_agent_count: number;
      entity_links_created: number;
    }>("/agents/cart-launch", {
      method: "POST",
      body: JSON.stringify(opts),
    }),
  agentStop: (id: string) => fetchApi<{ status: string }>(`/agents/${id}/stop`, { method: "POST" }),
  agentHide: (id: string) => fetchApi<{ status: string }>(`/agents/${id}/hide`, { method: "POST" }),
  agentUnhide: (id: string) => fetchApi<{ status: string }>(`/agents/${id}/unhide`, { method: "POST" }),
  agentUpdate: (id: string, updates: { jira_key?: string; project?: string; title?: string; worktree_path?: string; git_branch?: string }) =>
    fetchApi<Agent>(`/agents/${id}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    }),
  agentContextQueue: (id: string) =>
    fetchApi<{ pending_count: number; agent_id: string }>(`/agents/${id}/context-queue`),
  agentExtractUrls: (id: string) =>
    fetchApi<{ status: string; agent_id: string; urls_found: number; links_created: number }>(`/agents/${id}/extract-urls`, {
      method: "POST",
    }),
  infraOverview: (hours?: number, includePreemption?: boolean) =>
    fetchApi<InfraResponse>(`/infra/overview?hours=${hours || 6}&include_preemption=${includePreemption !== false}`),
  unknownUrls: (limit?: number) =>
    fetchApi<{ unknown_urls: Array<{ id: string; url: string; domain: string; first_seen_in_chat_id: string | null; occurrence_count: number; first_seen_at: string; last_seen_at: string; reviewed: boolean; promoted_to_pattern: boolean; ignored: boolean; review_notes: string | null }>; total: number; unreviewed_count: number }>(`/urls/unknown${limit ? `?limit=${limit}` : ""}`),
  unknownUrlUpdate: (id: string, updates: { reviewed?: boolean; ignored?: boolean; promoted_to_pattern?: boolean; review_notes?: string }) =>
    fetchApi<{ id: string; url: string; domain: string; reviewed: boolean; ignored: boolean; promoted_to_pattern: boolean; review_notes: string | null }>(`/urls/unknown/${id}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    }),
  unknownUrlGeneratePattern: (id: string) =>
    fetchApi<{ url: string; domain: string; pattern_suggestion: string; entity_type_guess: string; code_template: string }>(`/urls/unknown/${id}/generate-pattern`, {
      method: "POST",
    }),
  agentsIncludeHidden: (project?: string) =>
    fetchApi<{ agents: Agent[]; total: number }>(`/agents?include_hidden=true${project ? `&project=${project}` : ""}`),
  jiraTicket: (key: string) => fetchApi<JiraTicketResult>(`/jira/ticket/${encodeURIComponent(key)}`),
  jiraSearch: (q: string, projects?: string[]) =>
    fetchApi<{ tickets: JiraTicketResult[]; total: number }>(`/jira/search?q=${encodeURIComponent(q)}${projects?.length ? `&project=${projects.join(",")}` : ""}`),
  worktreeList: (project?: string) =>
    fetchApi<{ worktrees: WorktreeInfo[]; total: number }>(`/worktrees${project ? `?project=${project}` : ""}`),
  worktreeCreate: (project: string, jira_key?: string) =>
    fetchApi<{ path: string; branch: string; created: boolean; message: string }>("/worktrees", {
      method: "POST",
      body: JSON.stringify({ project, jira_key }),
    }),
  slackTeams: () => fetchApi<{ teams: SlackTeam[] }>("/slack/teams"),
  slackMessages: (team: string, days: number) =>
    fetchApi<{ content: string; stats: SlackStats }>(`/slack/messages?team=${encodeURIComponent(team)}&days=${days}`),
  slackStats: (team: string, days: number) =>
    fetchApi<SlackStats>(`/slack/stats?team=${encodeURIComponent(team)}&days=${days}`),
  slackSync: (team: string) =>
    fetchApi<{ synced: number; total: number; channels: Record<string, { success: boolean; output: string }> }>("/slack/sync", {
      method: "POST",
      body: JSON.stringify({ team }),
    }),
  slackSummarize: (team: string, days: number) =>
    fetchApi<{ summary: string; session_id: string | null; team: string; days: number }>("/slack/summarize", {
      method: "POST",
      body: JSON.stringify({ team, days }),
    }),
  slackLatestSummary: (team: string, days: number) =>
    fetchApi<{ summary?: string; status: "ready" | "in_progress" | "none"; team: string; days: number; cached_at?: string }>(
      `/slack/latest-summary?team=${encodeURIComponent(team)}&days=${days}`
    ),
  slackChannelMessages: (channel: string, days: number) =>
    fetchApi<{ channel: string; content: string; days: number }>(`/slack/channel/${encodeURIComponent(channel)}/messages?days=${days}`),
  slackChannelDetails: (channel: string) =>
    fetchApi<SlackChannelDetails>(`/slack/channel/${encodeURIComponent(channel)}/details`),
  slackSummary: () => fetchApi<{ channels: Array<{ name: string; unread: number; sentiment: string }>; summary: string }>("/slack/summary"),
  mrs: (projects?: string[]) => {
    const params = projects?.length ? `?${projects.map(p => `projects=${p}`).join('&')}` : '';
    return fetchApi<{ mrs: DetailedMR[]; total: number; projects: string[] }>(`/mrs${params}`);
  },
  mrDetails: (project: string, mrIid: number) =>
    fetchApi<DetailedMR>(`/mrs/${project}/${mrIid}`),
  mrPipelines: (project: string, mrIid: number) =>
    fetchApi<MRPipelinesResponse>(`/mrs/${project}/${mrIid}/pipelines`),
  mrApprove: (project: string, mrIid: number) =>
    fetchApi<{ success: boolean; message?: string; error?: string }>(`/mrs/${project}/${mrIid}/approve`, { method: "POST" }),
  mrClose: (project: string, mrIid: number) =>
    fetchApi<{ success: boolean; message?: string; error?: string }>(`/mrs/${project}/${mrIid}/close`, { method: "POST" }),
  mrToggleDraft: (project: string, mrIid: number, isDraft: boolean) =>
    fetchApi<{ success: boolean; is_draft: boolean; error?: string }>(`/mrs/${project}/${mrIid}/draft?is_draft=${isDraft}`, { method: "POST" }),
  mrReview: (project: string, mrIid: number) =>
    fetchApi<{ success: boolean; agent_id?: string; session_id?: string; message?: string; error?: string; personas?: string[]; risk_score?: number; risk_level?: string }>(`/mrs/${project}/${mrIid}/review`, { method: "POST" }),
  mrReviewFindings: (project: string, mrIid: number) =>
    fetchApi<ReviewFindings>(`/mrs/${project}/${mrIid}/review/findings`),
  myTickets: () => fetchApi<{ tickets: JiraTicket[]; total: number }>("/jira/my-tickets"),
  oncall: () => fetchApi<{ oncall: OnCallEntry[]; team: string }>("/oncall"),

  // Temporal Command Center
  temporalKeys: () => fetchApi<TemporalKeyHealth>("/temporal/keys"),
  temporalSlackUnanswered: (days: number = 7, channels?: string[]) => {
    const params = new URLSearchParams({ days: days.toString() });
    if (channels?.length) params.set("channels", channels.join(","));
    return fetchApi<TemporalUnanswered>(`/temporal/slack/unanswered?${params}`);
  },
  temporalSlackSummary: (days: number = 7) =>
    fetchApi<TemporalSlackSummary>(`/temporal/slack/summary?days=${days}`),
  temporalSlackSentiment: (days: number = 7) =>
    fetchApi<TemporalSentiment>(`/temporal/slack/sentiment?days=${days}`),
  temporalJiraTickets: () => fetchApi<TemporalJiraResponse>("/temporal/jira/tickets"),
  temporalMRs: () => fetchApi<TemporalMRsResponse>("/temporal/mrs"),
  temporalPerformance: () => fetchApi<TemporalPerformance>("/temporal/metrics/performance"),
  temporalUsage: (period: string = "30d") =>
    fetchApi<TemporalUsage>(`/temporal/metrics/usage?period=${period}`),
  temporalTenants: () => fetchApi<TemporalTenantsResponse>("/temporal/tenants"),
  temporalSlackSync: () =>
    fetchApi<{ synced: number }>("/temporal/slack/sync", { method: "POST" }),
  temporalSlackAiSummary: (channels?: string[]) => {
    const params = channels ? `?channels=${channels.join(",")}` : "";
    return fetchApi<{ summary?: string; status: string; channels: string[]; cached_at?: string }>(
      `/temporal/slack/ai-summary${params}`,
    );
  },
  temporalSlackSummarize: (days: number = 7, channels?: string[]) =>
    fetchApi<{ summary: string; status: string; channels: string[] }>(
      "/temporal/slack/ai-summary",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ days, channels: channels || null }),
      },
    ),

  // Terminal
  launchTerminal: (path: string, command: string) =>
    fetchApi<{ success: boolean; path: string; command: string }>(
      "/terminal/launch",
      {
        method: "POST",
        body: JSON.stringify({ path, command }),
      }
    ),

  // Jira Summary
  jiraSummary: (project?: string, sprint?: string) => {
    const params = new URLSearchParams();
    if (project) params.set("project", project);
    if (sprint) params.set("sprint", sprint);
    const queryString = params.toString();
    return fetchApi<JiraSummaryResponse>(`/jira/summary${queryString ? `?${queryString}` : ""}`);
  },

  // WX Deployments
  wxDeployments: () => fetchApi<WXDeploymentResponse>("/wx/deployments"),

  // Workspaces
  workspaceCreate: (request: WorkspaceCreateRequest) =>
    fetchApi<WorkspaceDetail>("/workspaces", {
      method: "POST",
      body: JSON.stringify(request),
    }),
  workspaceGet: (id: string) => fetchApi<WorkspaceDetail>(`/workspaces/${id}`),
  workspaceList: (project?: string, includeArchived: boolean = false, limit: number = 50, offset: number = 0) => {
    const params = new URLSearchParams();
    if (project) params.set("project", project);
    if (includeArchived) params.set("include_archived", "true");
    params.set("limit", limit.toString());
    params.set("offset", offset.toString());
    return fetchApi<WorkspaceListResponse>(`/workspaces?${params.toString()}`);
  },
  workspaceUpdate: (id: string, updates: { title?: string; archived?: boolean }) =>
    fetchApi<WorkspaceDetail>(`/workspaces/${id}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    }),
  workspaceDelete: (id: string) =>
    fetchApi<{ success: boolean }>(`/workspaces/${id}`, { method: "DELETE" }),

  // Workspace Resources
  workspaceAddJira: (workspaceId: string, jiraKey: string, isPrimary: boolean = false) =>
    fetchApi<WorkspaceDetail>(`/workspaces/${workspaceId}/jira`, {
      method: "POST",
      body: JSON.stringify({ jira_key: jiraKey, is_primary: isPrimary }),
    }),
  workspaceRemoveJira: (workspaceId: string, jiraKey: string) =>
    fetchApi<{ success: boolean }>(`/workspaces/${workspaceId}/jira/${jiraKey}`, { method: "DELETE" }),
  workspaceUpdateJira: (workspaceId: string, jiraKey: string, updates: {
    is_primary?: boolean;
    description_expanded?: boolean;
    comments_expanded?: boolean;
  }) =>
    fetchApi<WorkspaceDetail>(`/workspaces/${workspaceId}/jira/${jiraKey}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    }),

  workspaceAddAgent: (workspaceId: string, agentId: string, isPinned: boolean = true, linkedJiraKeys?: string[]) =>
    fetchApi<WorkspaceDetail>(`/workspaces/${workspaceId}/agents`, {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId, is_pinned: isPinned, linked_jira_keys: linkedJiraKeys }),
    }),
  workspaceRemoveAgent: (workspaceId: string, agentId: string) =>
    fetchApi<{ success: boolean }>(`/workspaces/${workspaceId}/agents/${agentId}`, { method: "DELETE" }),
  workspaceUpdateAgent: (workspaceId: string, agentId: string, updates: {
    is_pinned?: boolean;
    linked_jira_keys?: string[];
  }) =>
    fetchApi<WorkspaceDetail>(`/workspaces/${workspaceId}/agents/${agentId}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    }),

  workspaceAddBranch: (workspaceId: string, branchName: string, worktreePath?: string, isActive: boolean = false, relatedJiraKeys?: string[]) =>
    fetchApi<WorkspaceDetail>(`/workspaces/${workspaceId}/branches`, {
      method: "POST",
      body: JSON.stringify({
        branch_name: branchName,
        worktree_path: worktreePath,
        is_active: isActive,
        related_jira_keys: relatedJiraKeys,
      }),
    }),
  workspaceRemoveBranch: (workspaceId: string, branchName: string) =>
    fetchApi<{ success: boolean }>(`/workspaces/${workspaceId}/branches/${encodeURIComponent(branchName)}`, { method: "DELETE" }),

  workspaceAddMR: (workspaceId: string, mrProject: string, mrIid: number, branchName: string, status?: string, url?: string) =>
    fetchApi<WorkspaceDetail>(`/workspaces/${workspaceId}/mrs`, {
      method: "POST",
      body: JSON.stringify({
        mr_project: mrProject,
        mr_iid: mrIid,
        branch_name: branchName,
        status,
        url,
      }),
    }),
  workspaceRemoveMR: (workspaceId: string, mrProject: string, mrIid: number) =>
    fetchApi<{ success: boolean }>(`/workspaces/${workspaceId}/mrs/${encodeURIComponent(mrProject)}/${mrIid}`, { method: "DELETE" }),

  workspaceAddDeployment: (workspaceId: string, environment: string, namespace: string = "", version?: string, status?: string, url?: string) =>
    fetchApi<WorkspaceDetail>(`/workspaces/${workspaceId}/deployments`, {
      method: "POST",
      body: JSON.stringify({
        environment,
        namespace,
        version,
        status,
        url,
      }),
    }),
  workspaceRemoveDeployment: (workspaceId: string, environment: string, namespace: string = "") =>
    fetchApi<{ success: boolean }>(`/workspaces/${workspaceId}/deployments/${encodeURIComponent(environment)}/${encodeURIComponent(namespace)}`, { method: "DELETE" }),

  workspaceDiscover: (workspaceId: string) =>
    fetchApi<{ workspace: WorkspaceDetail; discovered: Record<string, number> }>(`/workspaces/${workspaceId}/discover`, { method: "POST" }),

  // Planet Commander - Context Resolution
  contextById: (id: string) => fetchApi<ContextResponse>(`/contexts/${id}`),
  contextByJiraKey: (jiraKey: string) => fetchApi<ContextResponse>(`/contexts/jira/${jiraKey}`),
  contextByChatId: (chatId: string) => fetchApi<ContextResponse>(`/contexts/chat/${chatId}`),
  contextByBranchId: (branchId: string) => fetchApi<ContextResponse>(`/contexts/branch/${branchId}`),
  contextByWorktreeId: (worktreeId: string) => fetchApi<ContextResponse>(`/contexts/worktree/${worktreeId}`),

  // Planet Commander - Link Management
  createLink: (request: CreateLinkRequest) =>
    fetchApi<LinkResponse>("/links", {
      method: "POST",
      body: JSON.stringify(request),
    }),
  confirmLink: (linkId: string) =>
    fetchApi<LinkResponse>(`/links/${linkId}/confirm`, { method: "POST" }),
  rejectLink: (linkId: string) =>
    fetchApi<LinkResponse>(`/links/${linkId}/reject`, { method: "POST" }),
  deleteLink: (linkId: string) =>
    fetchApi<{ status: string; link_id: string }>(`/links/${linkId}`, { method: "DELETE" }),
  contextLinks: (contextId: string) =>
    fetchApi<LinkResponse[]>(`/links/context/${contextId}`),
  suggestedLinks: () =>
    fetchApi<LinkResponse[]>("/links/suggested"),
  batchConfirmLinks: (linkIds: string[]) =>
    fetchApi<{ status: string; confirmed_count: number; total_requested: number }>("/links/batch-confirm", {
      method: "POST",
      body: JSON.stringify({ link_ids: linkIds }),
    }),

  // Background Jobs
  backgroundJobRuns: (limit: number = 20, jobName?: string) => {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (jobName) params.set("job_name", jobName);
    return fetchApi<{ runs: JobRunResponse[]; total: number }>(`/jobs/runs?${params}`);
  },
  backgroundJobStatus: () =>
    fetchApi<{ jobs: JobStatusResponse[]; total: number; scheduler_running: boolean }>("/jobs/status"),
  triggerBackgroundJob: (jobName: string) =>
    fetchApi<{ success: boolean; message?: string; error?: string }>(`/jobs/trigger/${jobName}`, {
      method: "POST",
    }),

  // Health Audits
  healthAuditContext: (contextId: string) =>
    fetchApi<HealthAuditResult>(`/health/audit/${contextId}`),
  healthAuditAll: () =>
    fetchApi<HealthAuditSummary>("/health/audit"),
  healthStaleContexts: (days: number = 30) =>
    fetchApi<{ stale_contexts: StaleContext[]; days_threshold: number }>(`/health/stale?days=${days}`),
  healthOrphanedEntities: () =>
    fetchApi<OrphanedEntities>("/health/orphaned"),
  healthMarkOrphaned: (days: number = 60) =>
    fetchApi<{ marked_orphaned: number; days_threshold: number }>(`/health/mark-orphaned?days=${days}`, {
      method: "POST",
    }),

  // AI Summaries & Artifacts
  summarizeChat: (chatId: string, forceRegenerate: boolean = false) =>
    fetchApi<SummaryResponse>(`/summaries/chat/${chatId}?force_regenerate=${forceRegenerate}`, {
      method: "POST",
    }),
  getChatSummary: (chatId: string) =>
    fetchApi<SummaryResponse | null>(`/summaries/chat/${chatId}`),
  generateContextOverview: (contextId: string, forceRegenerate: boolean = false) =>
    fetchApi<SummaryResponse>(`/summaries/context/${contextId}?force_regenerate=${forceRegenerate}`, {
      method: "POST",
    }),
  extractChatArtifacts: (chatId: string, forceReextract: boolean = false) =>
    fetchApi<ArtifactExtractionResult>(`/summaries/artifacts/chat/${chatId}?force_reextract=${forceReextract}`, {
      method: "POST",
    }),
  getChatArtifacts: (chatId: string, artifactType?: string) => {
    const params = artifactType ? `?artifact_type=${artifactType}` : "";
    return fetchApi<ArtifactResponse[]>(`/summaries/artifacts/chat/${chatId}${params}`);
  },
  getContextArtifacts: (contextId: string) =>
    fetchApi<ArtifactResponse[]>(`/summaries/artifacts/context/${contextId}`),

  // Workflow Automation - PR/MR
  createPRFromChat: (chatId: string, targetBranch: string = "main", autoPush: boolean = false) =>
    fetchApi<PRCreationResult>(`/automation/pr/chat/${chatId}?target_branch=${targetBranch}&auto_push=${autoPush}`, {
      method: "POST",
    }),
  createPRFromContext: (contextId: string, targetBranch: string = "main") =>
    fetchApi<PRCreationResult>(`/automation/pr/context/${contextId}?target_branch=${targetBranch}`, {
      method: "POST",
    }),

  // Workflow Automation - JIRA
  syncContextToJira: (contextId: string) =>
    fetchApi<JiraSyncResult>(`/automation/jira/sync-context/${contextId}`, {
      method: "POST",
    }),
  commentOnContextJira: (contextId: string, comment: string) =>
    fetchApi<JiraSyncResult>(`/automation/jira/comment-context/${contextId}`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    }),

  // Workflow Automation - Slack
  notifyPRCreated: (channel: string, prUrl: string, title: string, author: string, jiraKey?: string) =>
    fetchApi<SlackNotificationResult>("/automation/slack/notify-pr", {
      method: "POST",
      body: JSON.stringify({ channel, pr_url: prUrl, title, author, jira_key: jiraKey }),
    }),
  notifyStatusChange: (channel: string, contextTitle: string, oldStatus: string, newStatus: string, jiraKeys?: string[]) =>
    fetchApi<SlackNotificationResult>("/automation/slack/notify-status-change", {
      method: "POST",
      body: JSON.stringify({ channel, context_title: contextTitle, old_status: oldStatus, new_status: newStatus, jira_keys: jiraKeys }),
    }),
  notifyHealthAlert: (channel: string, contextTitle: string, healthStatus: string, issues: string[]) =>
    fetchApi<SlackNotificationResult>("/automation/slack/notify-health-alert", {
      method: "POST",
      body: JSON.stringify({ channel, context_title: contextTitle, health_status: healthStatus, issues }),
    }),

  // Workflow Automation - GitLab
  approveMR: (project: string, mrIid: number, worktreePath?: string) =>
    fetchApi<GitLabMRResult>(`/automation/gitlab/approve-mr?project=${encodeURIComponent(project)}&mr_iid=${mrIid}${worktreePath ? `&worktree_path=${encodeURIComponent(worktreePath)}` : ""}`, {
      method: "POST",
    }),
  mergeMR: (project: string, mrIid: number, whenPipelineSucceeds: boolean = true, deleteSourceBranch: boolean = true, squash: boolean = false, worktreePath?: string) => {
    const params = new URLSearchParams({
      project,
      mr_iid: mrIid.toString(),
      when_pipeline_succeeds: whenPipelineSucceeds.toString(),
      delete_source_branch: deleteSourceBranch.toString(),
      squash: squash.toString(),
    });
    if (worktreePath) params.set("worktree_path", worktreePath);
    return fetchApi<GitLabMRResult>(`/automation/gitlab/merge-mr?${params}`, {
      method: "POST",
    });
  },
  checkMRStatus: (project: string, mrIid: number, worktreePath?: string) => {
    const params = new URLSearchParams({ project, mr_iid: mrIid.toString() });
    if (worktreePath) params.set("worktree_path", worktreePath);
    return fetchApi<GitLabMRStatusResult>(`/automation/gitlab/mr-status?${params}`);
  },
  autoApproveMergeMR: (project: string, mrIid: number, worktreePath?: string, squash: boolean = false) => {
    const params = new URLSearchParams({
      project,
      mr_iid: mrIid.toString(),
      squash: squash.toString(),
    });
    if (worktreePath) params.set("worktree_path", worktreePath);
    return fetchApi<GitLabMRResult>(`/automation/gitlab/auto-approve-merge?${params}`, {
      method: "POST",
    });
  },

  // PagerDuty Incidents
  pagerdutyIncidents: (status?: string, urgency?: string, team?: string, service?: string, days: number = 7, limit: number = 50) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (urgency) params.set("urgency", urgency);
    if (team) params.set("team", team);
    if (service) params.set("service", service);
    params.set("days", days.toString());
    params.set("limit", limit.toString());
    return fetchApi<PagerDutyIncidentListResponse>(`/pagerduty?${params}`);
  },
  pagerdutyComputeTeamIncidents: (status?: string, days: number = 7, limit: number = 50) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    params.set("days", days.toString());
    params.set("limit", limit.toString());
    return fetchApi<PagerDutyIncidentListResponse>(`/pagerduty/compute-team?${params}`);
  },
  pagerdutyIncident: (incidentId: string) =>
    fetchApi<PagerDutyIncidentDetail>(`/pagerduty/${incidentId}`),
  pagerdutySyncIncident: (incidentId: string) =>
    fetchApi(`/pagerduty/sync/${incidentId}`, { method: "POST" }),
  pagerdutyScanRecent: (days: number = 1, statuses?: string[], computeTeamOnly: boolean = true) => {
    const params = new URLSearchParams();
    params.set("days", days.toString());
    params.set("compute_team_only", computeTeamOnly.toString());
    if (statuses) {
      statuses.forEach(s => params.append("statuses", s));
    }
    return fetchApi(`/pagerduty/scan-recent?${params}`, { method: "POST" });
  },
  pagerdutyEnrichText: (text: string) => {
    const params = new URLSearchParams();
    params.set("text", text);
    return fetchApi(`/pagerduty/enrich-text?${params}`, { method: "POST" });
  },

  // Artifacts
  artifacts: (project?: string, artifactType?: string, keywords?: string, limit: number = 50) => {
    const params = new URLSearchParams();
    if (project) params.set("project", project);
    if (artifactType) params.set("artifact_type", artifactType);
    if (keywords) params.set("keywords", keywords);
    params.set("limit", limit.toString());
    return fetchApi<InvestigationArtifact[]>(`/artifacts?${params}`);
  },
  artifact: (artifactId: string) =>
    fetchApi<InvestigationArtifact>(`/artifacts/${artifactId}`),
  searchArtifacts: (jiraKey?: string, keywords?: string, project?: string, dateFrom?: string, dateTo?: string, limit: number = 20) => {
    const params = new URLSearchParams();
    if (jiraKey) params.set("jira_key", jiraKey);
    if (keywords) params.set("keywords", keywords);
    if (project) params.set("project", project);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    params.set("limit", limit.toString());
    return fetchApi<InvestigationArtifact[]>(`/artifacts/search?${params}`);
  },
  similarArtifacts: (artifactId: string, limit: number = 5) =>
    fetchApi<InvestigationArtifact[]>(`/artifacts/similar/${artifactId}?limit=${limit}`),
  refreshArtifact: (artifactId: string) =>
    fetchApi<InvestigationArtifact>(`/artifacts/${artifactId}/refresh`, { method: "POST" }),
  contextArtifacts: (contextId: string) =>
    fetchApi<InvestigationArtifact[]>(`/artifacts/context/${contextId}`),
  scanArtifacts: () =>
    fetchApi<{ total_scanned: number; new_alerts: number; updated_alerts: number; error_count: number; errors: any[] }>(
      "/artifacts/scan",
      { method: "POST" }
    ),

  // Grafana Alerts
  alertDefinitions: (team?: string, project?: string, severity?: string, limit: number = 100) => {
    const params = new URLSearchParams();
    if (team) params.set("team", team);
    if (project) params.set("project", project);
    if (severity) params.set("severity", severity);
    params.set("limit", limit.toString());
    return fetchApi<GrafanaAlertDefinition[]>(`/grafana/alerts?${params}`);
  },
  alertDefinition: (alertName: string) =>
    fetchApi<GrafanaAlertDefinition>(`/grafana/alerts/${encodeURIComponent(alertName)}`),
  searchAlertDefinitions: (query: string, team?: string, project?: string, limit: number = 20) => {
    const params = new URLSearchParams();
    params.set("query", query);
    if (team) params.set("team", team);
    if (project) params.set("project", project);
    params.set("limit", limit.toString());
    return fetchApi<GrafanaAlertDefinition[]>(`/grafana/alerts/search?${params}`);
  },
  createAlertFromName: (alertName: string, summary?: string, severity?: string) =>
    fetchApi<GrafanaAlertDefinition>("/grafana/alerts", {
      method: "POST",
      body: JSON.stringify({ alert_name: alertName, summary, severity }),
    }),
  scanAlertRepo: () =>
    fetchApi<{ total_scanned: number; new_alerts: number; updated_alerts: number; error_count: number; note?: string }>(
      "/grafana/alerts/scan",
      { method: "POST" }
    ),
  alertFirings: (alertName: string, limit: number = 20) =>
    fetchApi<AlertFiring[]>(`/grafana/alerts/${encodeURIComponent(alertName)}/firings?limit=${limit}`),

  // Project Documentation
  projectDocs: (team?: string, staleOnly: boolean = false, limit: number = 50) => {
    const params = new URLSearchParams();
    if (team) params.set("team", team);
    if (staleOnly) params.set("stale_only", "true");
    params.set("limit", limit.toString());
    return fetchApi<ProjectDoc[]>(`/project-docs?${params}`);
  },
  projectDoc: (projectName: string) =>
    fetchApi<ProjectDoc>(`/project-docs/${encodeURIComponent(projectName)}`),
  projectSections: (projectName: string) =>
    fetchApi<ProjectDocSection[]>(`/project-docs/${encodeURIComponent(projectName)}/sections`),
  searchProjectDocs: (query: string, project?: string, team?: string, limit: number = 20) => {
    const params = new URLSearchParams();
    params.set("query", query);
    if (project) params.set("project", project);
    if (team) params.set("team", team);
    params.set("limit", limit.toString());
    return fetchApi<ProjectDoc[]>(`/project-docs/search?${params}`);
  },
  scanProjectDocs: () =>
    fetchApi<{ total_scanned: number; new_docs: number; updated_docs: number; unchanged_docs: number; error_count: number; note?: string }>(
      "/project-docs/scan",
      { method: "POST" }
    ),

  // Google Drive Documents
  googleDriveDocuments: (sharedDrive?: string, documentKind?: string, project?: string, limit: number = 50) => {
    const params = new URLSearchParams();
    if (sharedDrive) params.set("shared_drive", sharedDrive);
    if (documentKind) params.set("document_kind", documentKind);
    if (project) params.set("project", project);
    params.set("limit", limit.toString());
    return fetchApi<GoogleDriveDocumentListResponse>(`/google-drive/documents?${params}`);
  },
  googleDriveSearch: (q: string, sharedDrive?: string, documentKind?: string, project?: string, limit: number = 20) => {
    const params = new URLSearchParams();
    params.set("q", q);
    if (sharedDrive) params.set("shared_drive", sharedDrive);
    if (documentKind) params.set("document_kind", documentKind);
    if (project) params.set("project", project);
    params.set("limit", limit.toString());
    return fetchApi<GoogleDriveDocumentListResponse>(`/google-drive/search?${params}`);
  },
  googleDriveJira: (jiraKey: string) =>
    fetchApi<GoogleDriveDocumentListResponse>(`/google-drive/jira/${encodeURIComponent(jiraKey)}`),
  googleDrivePostmortems: (project?: string, limit: number = 50) => {
    const params = new URLSearchParams();
    if (project) params.set("project", project);
    params.set("limit", limit.toString());
    return fetchApi<GoogleDriveDocumentListResponse>(`/google-drive/postmortems?${params}`);
  },
  googleDriveDocument: (externalDocId: string) =>
    fetchApi<GoogleDriveDocument>(`/google-drive/documents/${encodeURIComponent(externalDocId)}`),
  googleDriveScan: () =>
    fetchApi<GoogleDriveScanStats>("/google-drive/scan", { method: "POST" }),

  // GitLab Merge Requests
  gitlabMRs: (repository?: string, state?: string, author?: string, jiraKey?: string, limit: number = 50) => {
    const params = new URLSearchParams();
    if (repository) params.set("repository", repository);
    if (state) params.set("state", state);
    if (author) params.set("author", author);
    if (jiraKey) params.set("jira_key", jiraKey);
    params.set("limit", limit.toString());
    return fetchApi<GitLabMRListResponse>(`/gitlab/mrs?${params}`);
  },
  gitlabMRSearch: (q: string, repository?: string, state?: string, limit: number = 50) => {
    const params = new URLSearchParams();
    params.set("q", q);
    if (repository) params.set("repository", repository);
    if (state) params.set("state", state);
    params.set("limit", limit.toString());
    return fetchApi<GitLabMRListResponse>(`/gitlab/mrs/search?${params}`);
  },
  gitlabMRByJira: (jiraKey: string) =>
    fetchApi<GitLabMRListResponse>(`/mrs/by-jira/${encodeURIComponent(jiraKey)}`),
  gitlabMRByBranch: (branchName: string) =>
    fetchApi<GitLabMRListResponse>(`/gitlab/mrs/branch/${encodeURIComponent(branchName)}`),
  gitlabMR: (repository: string, mrNumber: number) =>
    fetchApi<GitLabMR>(`/gitlab/mrs/${encodeURIComponent(repository)}/${mrNumber}`),
  gitlabMRScan: (repositories?: string[], state: string = "opened", limit: number = 100) =>
    fetchApi<GitLabMRScanStats[]>("/gitlab/mrs/scan", {
      method: "POST",
      body: JSON.stringify({ repositories, state, limit }),
    }),

  // Slack Threads
  slackThreads: (channelId?: string, isIncident?: boolean, hasJiraKey?: string, sinceDays: number = 7, limit: number = 50) => {
    const params = new URLSearchParams();
    if (channelId) params.set("channel_id", channelId);
    if (isIncident !== undefined) params.set("is_incident", isIncident.toString());
    if (hasJiraKey) params.set("has_jira_key", hasJiraKey);
    params.set("since_days", sinceDays.toString());
    params.set("limit", limit.toString());
    return fetchApi<SlackThreadListResponse>(`/slack/threads/threads?${params}`);
  },
  slackThread: (threadId: string) =>
    fetchApi<SlackThreadDetail>(`/slack/threads/threads/${threadId}`),
  slackThreadsByJira: (jiraKey: string) =>
    fetchApi<SlackThreadListResponse>(`/slack/threads/threads/by-jira/${encodeURIComponent(jiraKey)}`),
  slackThreadParseUrl: (slackUrl: string, includeSurrounding: boolean = false) =>
    fetchApi<ParseUrlResponse>("/slack/threads/parse-url", {
      method: "POST",
      body: JSON.stringify({ slack_url: slackUrl, include_surrounding: includeSurrounding }),
    }),
  slackThreadParseJira: (jiraKey: string, includeSurrounding: boolean = false) =>
    fetchApi<ParseJiraResponse>(`/slack/threads/parse-jira/${encodeURIComponent(jiraKey)}?include_surrounding=${includeSurrounding}`, {
      method: "POST",
    }),
  slackThreadRefresh: (threadId: string, includeSurrounding: boolean = false) =>
    fetchApi<SlackThread>(`/slack/threads/threads/${threadId}/refresh`, {
      method: "POST",
      body: JSON.stringify({ include_surrounding: includeSurrounding }),
    }),

  // Skills Auto-Suggestion
  skillsSuggestions: (contextId: string, minConfidence: number = 0.3) =>
    fetchApi<SkillSuggestionsResponse>(`/skills/contexts/${contextId}/suggested-skills?min_confidence=${minConfidence}`),
  skillsRecordAction: (contextId: string, skillId: string, action: string, feedback?: string) =>
    fetchApi<{ status: string; context_id: string; skill_id: string; action: string }>(`/skills/contexts/${contextId}/suggested-skills/${skillId}/action`, {
      method: "POST",
      body: JSON.stringify({ action, feedback }),
    }),
  skillsRegistry: (category?: string) =>
    fetchApi<SkillListResponse>(`/skills/registry${category ? `?category=${category}` : ""}`),
  skillsReindex: () =>
    fetchApi<IndexingStatsResponse>("/skills/reindex", { method: "POST" }),

  // Warning Monitor
  warnings: (activeOnly: boolean = true) =>
    fetchApi<WarningEvent[]>(`/warnings?active_only=${activeOnly}`),
  warningsSummary: () =>
    fetchApi<WarningsSummary>("/warnings/summary"),
  warningDetail: (id: string) =>
    fetchApi<WarningEvent>(`/warnings/${id}`),
  warningStandbyContext: (id: string) =>
    fetchApi<StandbyContext>(`/warnings/${id}/standby`),
  escalationMetrics: () =>
    fetchApi<EscalationMetrics[]>("/warnings/metrics/all"),
  escalationMetricsForAlert: (alertName: string) =>
    fetchApi<EscalationMetrics>(`/warnings/metrics/${encodeURIComponent(alertName)}`),
  escalationTrends: (days: number = 7) =>
    fetchApi<EscalationTrends>(`/warnings/trends?days=${days}`),
  predictionAccuracy: (days: number = 30) =>
    fetchApi<PredictionAccuracy>(`/warnings/accuracy?days=${days}`),

  // Feedback API
  submitPredictionFeedback: (warningId: string, feedback: PredictionFeedback) =>
    fetchApi<FeedbackResponse>(`/warnings/${warningId}/feedback/prediction`, {
      method: "POST",
      body: JSON.stringify(feedback),
    }),
  submitContextFeedback: (warningId: string, feedback: ContextFeedback) =>
    fetchApi<FeedbackResponse>(`/warnings/${warningId}/feedback/context`, {
      method: "POST",
      body: JSON.stringify(feedback),
    }),
  feedbackStats: () =>
    fetchApi<FeedbackStats>("/warnings/feedback/stats"),

  // Learning System API
  learningAlerts: (days: number = 30) =>
    fetchApi<AlertPerformance[]>(`/warnings/learning/alerts?days=${days}`),
  learningAccuracyTrend: (days: number = 30, windowDays: number = 7) =>
    fetchApi<AccuracyTrend[]>(`/warnings/learning/accuracy-trend?days=${days}&window_days=${windowDays}`),
  learningAlertTuning: (alertName: string, system?: string) =>
    fetchApi<AlertTuning>(`/warnings/learning/tune/${encodeURIComponent(alertName)}${system ? `?system=${encodeURIComponent(system)}` : ""}`),
  learningSummary: () =>
    fetchApi<LearningSummary>("/warnings/learning/summary"),

  // Service Health Dashboard
  serviceHealth: (hours: number = 24) =>
    fetchApi<ServiceHealthResponse>(`/service-health?hours=${hours}`),
  serviceDetail: (serviceName: string, hours: number = 24) =>
    fetchApi<ServiceDetailResponse>(`/service-health/service/${encodeURIComponent(serviceName)}?hours=${hours}`),

  // Audit System
  auditCta: (targetType: string, targetId: string) =>
    fetchApi<CTAState>(`/audits/cta/${encodeURIComponent(targetType)}/${encodeURIComponent(targetId)}`),

  // Coach Sessions
  coachCreateSession: (targetType: string, targetId: string, auditRunId?: string) =>
    fetchApi<CoachSession>("/coach/sessions", {
      method: "POST",
      body: JSON.stringify({ target_type: targetType, target_id: targetId, audit_run_id: auditRunId }),
    }),
  coachGetSession: (sessionId: string) =>
    fetchApi<CoachSession>(`/coach/sessions/${sessionId}`),
  coachTransitionItem: (sessionId: string, itemId: string, status: string, resolution?: string, notes?: string) =>
    fetchApi<CoachTransitionResponse>(`/coach/sessions/${sessionId}/items/${itemId}/transition`, {
      method: "POST",
      body: JSON.stringify({ status, resolution, notes }),
    }),
  coachDeleteSession: (sessionId: string) =>
    fetchApi<void>(`/coach/sessions/${sessionId}`, { method: "DELETE" }),
  coachExplainItem: (sessionId: string, itemId: string) =>
    fetchApi<ExplainResponse>(`/coach/sessions/${sessionId}/items/${itemId}/explain`, {
      method: "POST",
    }),
  coachRespondItem: (sessionId: string, itemId: string, response: string) =>
    fetchApi<EvaluateResponse>(`/coach/sessions/${sessionId}/items/${itemId}/respond`, {
      method: "POST",
      body: JSON.stringify({ response }),
    }),

  // Filesystem
  browseDirectory: (path: string = "~") =>
    fetchApi<BrowseResponse>(`/fs/browse?path=${encodeURIComponent(path)}`),

  // Permissions
  getPermissions: () =>
    fetchApi<PermissionsResponse>("/permissions"),
  updatePermissions: (raw: string) =>
    fetchApi<PermissionsResponse>("/permissions", {
      method: "PUT",
      body: JSON.stringify({ raw }),
    }),
  addPermission: (tool: string) =>
    fetchApi<PermissionsResponse>("/permissions/add", {
      method: "POST",
      body: JSON.stringify({ tool }),
    }),
  removePermission: (tool: string) =>
    fetchApi<PermissionsResponse>(`/permissions/${encodeURIComponent(tool)}`, {
      method: "DELETE",
    }),
};

export interface DirectoryEntry {
  name: string;
  path: string;
  is_dir: boolean;
  is_git: boolean;
}

export interface BrowseResponse {
  path: string;
  parent: string | null;
  entries: DirectoryEntry[];
}

export interface PermissionsResponse {
  tools: string[];
  raw: string;
  count: number;
}

export interface PermissionDenial {
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_use_id?: string;
  session_id?: string;
}

export interface Agent {
  id: string;
  claude_session_id: string;
  project: string;
  status: "live" | "idle" | "dead";
  managed_by: "vscode" | "dashboard";
  title: string;
  first_prompt: string;
  git_branch: string | null;
  worktree_path: string | null;
  working_directory: string | null;
  dev_env_url: string | null;
  message_count: number;
  total_tokens: number;
  num_prompts: number;
  jira_key: string | null;
  hidden_at: string | null;
  created_at: string;
  last_active_at: string;
  labels: Array<{ name: string; category: string; color: string }>;
  artifacts: Array<{ type: string; path: string }>;
}

export interface AgentSummary {
  status: "ready" | "in_progress" | "none";
  agent_id: string;
  phrase?: string;
  short?: string;
  detailed?: string;
  generated_at?: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  timestamp: string;
  content?: string;
  summary?: string;
  tool_calls?: Array<{ name: string; input_preview: string }>;
  tool_call_count?: number;
  has_thinking?: boolean;
  thinking?: string;
  model?: string;
  artifacts?: Array<{ path: string; type: string; tool: string }>;
}

export interface ArtifactContent {
  path: string;
  filename: string;
  content: string;
  language: string;
  size: number;
}

export interface MR {
  id: number;
  title: string;
  author: string;
  reviewer: string | null;
  age_hours: number;
  commits: number;
  ticket: string | null;
  url: string;
  project: string;
}

export interface DetailedMR {
  project: string;
  iid: number;
  title: string;
  description?: string;
  author: string;
  url: string;
  branch: string;
  target_branch?: string;
  sha?: string;
  age_created_hours: number;
  age_last_commit_hours: number;
  is_draft: boolean;
  is_mine: boolean;
  state?: string;
  labels?: string[];
  needs_review?: boolean;
  reviews?: Array<{
    agent_id: string;
    session_id: string;
    commit_sha: string;
    timestamp: string;
  }>;
}

export interface PipelineJob {
  id: number;
  name: string;
  status: string;
  stage: string;
  duration: number | null;
  web_url: string;
  failure_reason: string | null;
  allow_failure: boolean;
  started_at: string | null;
  finished_at: string | null;
}

export interface PipelineStage {
  name: string;
  status: string;
  jobs: PipelineJob[];
}

export interface PipelineSummary {
  id: number;
  status: string;
  ref: string;
  sha: string;
  web_url: string;
  created_at: string;
  source: string;
  stages?: PipelineStage[];
}

export interface MRPipelinesResponse {
  pipelines: PipelineSummary[];
  active_pipeline?: PipelineSummary;
}

export interface ReviewFinding {
  id: string;
  code: string;
  category: string;
  severity: string;
  title: string;
  description: string;
  blocking: boolean;
  auto_fixable: boolean;
  source_file?: string;
  source_line?: number;
  status: string;
}

export interface PersonaResult {
  persona: string;
  verdict: string;
  model: string;
  duration_ms: number;
  cost_usd: number;
  risk_score?: number;
  risk_level?: string;
  finding_count: number;
  blocking_count: number;
  findings: ReviewFinding[];
}

export interface ReviewFindings {
  status: string;
  verdict?: string;
  finding_count?: number;
  blocking_count?: number;
  risk_score?: number;
  risk_level?: string;
  total_cost_usd?: number;
  personas: PersonaResult[];
}

export interface JiraTicket {
  key: string;
  summary: string;
  status: string;
  assignee: string;
  priority: string;
}

export interface OnCallEntry {
  name: string;
  start: string;
  end: string;
  escalation_level: number;
}

export interface JiraComment {
  id: string;
  author: string;
  author_email: string;
  avatar_url: string;
  body: string;
  created: string;
  updated: string;
}

export interface JiraTicketResult {
  key: string;
  summary: string;
  description?: string;
  status: string;
  assignee: string;
  assignee_avatar_url?: string;  // Avatar from Slack, GitLab, or JIRA
  priority: string;
  type: string;
  fix_versions: string[];
  labels: string[];
  comments: JiraComment[];
}

export interface WorktreeInfo {
  path: string;
  branch: string;
  commit: string;
}

export interface SlackTeam {
  id: string;
  label: string;
  channels: string[];
  project: string | null;
}

export interface SlackStats {
  channels: Array<{ name: string; count: number; last_activity: string | null }>;
  total: number;
}

export interface SlackChannelDetails {
  channel: string;
  earliest_date: string | null;
  latest_date: string | null;
  total_messages: number;
  last_day_count: number;
  last_week_avg: number;
  total_files: number;
}

// Temporal Command Center types
export interface TemporalKeyInfo {
  tenant: string;
  key_name: string;
  color: string;
  account_type: string;
  is_current: boolean;
  expiry: string;
  days_until: number;
  status: "expired" | "expiring" | "ok";
  sa_name?: string;
}

export interface TemporalKeyHealth {
  keys: TemporalKeyInfo[];
  expired_count: number;
  expiring_count: number;
  ok_count: number;
  total_tenants: number;
  inventory_updated: string;
  inventory_age_days: number;
  error?: string;
}

export interface TemporalUnansweredMessage {
  channel: string;
  user: string;
  time: string;
  text: string;
  age_hours: number;
}

export interface SlackChannelFreshness {
  latest_date: string | null;
  stale: boolean;
  days_old: number | null;
}

export interface TemporalUnanswered {
  unanswered: TemporalUnansweredMessage[];
  total: number;
  channels_checked: string[];
  actual_days?: number;
  freshness?: Record<string, SlackChannelFreshness>;
}

export interface TemporalSentiment {
  positive: number;
  neutral: number;
  frustrated: number;
  positive_pct: number;
  neutral_pct: number;
  frustrated_pct: number;
  total_messages: number;
  sample_frustrated: string[];
  days: number;
}

export interface TemporalJiraResponse {
  tickets: JiraTicketResult[];
  by_status: Record<string, number>;
  total: number;
  error?: string;
}

export interface TemporalMR {
  iid: number;
  title: string;
  branch?: string;
  url?: string;
}

export interface TemporalMRsResponse {
  open_mrs: TemporalMR[];
  main_pipeline: { status: string; raw?: string };
  total: number;
  repo: string;
  error?: string;
}

export interface TemporalPerformance {
  workflow_success_rate: number | null;
  workflow_completions_per_hour: number | null;
  workflow_failures_per_hour: number | null;
  activity_failures_per_hour: number;
  activity_failures_by_service?: Array<{ service: string; failures_per_hour: number }>;
  status: string;
}

export interface TemporalUsage {
  total_activities: number;
  by_service: Array<{ service: string; activity_count: number; percent: number }>;
  period: string;
}

export interface TemporalSlackChannelSummary {
  channel: string;
  message_count: number;
  active_users: Array<{ name: string; messages: number }>;
  unanswered_count: number;
}

export interface TemporalSlackSummary {
  channels: TemporalSlackChannelSummary[];
  days: number;
  actual_days?: number;
  total_messages: number;
  freshness?: Record<string, SlackChannelFreshness>;
}

export interface TemporalTenant {
  uid: string;
  name: string;
  email: string;
  namespaces: string[];
  namespace_count: number;
  users: Array<{ email: string; name: string; permission: string }>;
  user_count: number;
  slack_channels: string[];
  repos: string[];
  products: string[];
  has_export: boolean;
  has_nexus: boolean;
  has_custom_sa: boolean;
}

export interface TemporalTenantsResponse {
  tenants: TemporalTenant[];
  users: Array<{ email: string; name: string; tenant: string; team: string; tenants: string[]; permission: string }>;
  total_tenants: number;
  total_users: number;
}

// WX Deployments types
export interface WXEnvironmentDeployment {
  name: string;
  build_id: string;
  deployed_at?: string;
  commit_url?: string;
  argocd_url?: string;
  tigercli_url?: string;
  status?: "healthy" | "degraded" | "down";
  tier?: "staging" | "prod";
}

export interface WXDeploymentResponse {
  environments: WXEnvironmentDeployment[];
  last_updated: string;
}

// Jira Summary types
export interface JiraTicketEnhanced extends JiraTicketResult {
  my_relationships: {
    assigned: boolean;
    watching: boolean;
    paired: boolean;
    mr_reviewed: boolean;
    slack_discussed: boolean;
  };
  linked_mrs?: Array<{
    project: string;
    iid: number;
    title: string;
    url: string;
  }>;
  slack_mentions?: Array<{
    channel: string;
    timestamp: string;
    user: string;
  }>;
  age_days: number;
  last_updated: string;
  sprint?: string;
  story_points?: number;
}

export interface JiraSummaryResponse {
  me: {
    assigned: JiraTicketEnhanced[];
    watching: JiraTicketEnhanced[];
    paired: JiraTicketEnhanced[];
    mr_reviewed: JiraTicketEnhanced[];
    slack_discussed: JiraTicketEnhanced[];
  };
  team: {
    by_status: {
      backlog: JiraTicketEnhanced[];
      selected: JiraTicketEnhanced[];
      in_progress: JiraTicketEnhanced[];
      in_review: JiraTicketEnhanced[];
      ready_to_deploy: JiraTicketEnhanced[];
      monitoring: JiraTicketEnhanced[];
      done: JiraTicketEnhanced[];
    };
    stats: {
      backlog_count: number;
      selected_count: number;
      in_progress_count: number;
      in_review_count: number;
      ready_to_deploy_count: number;
      monitoring_count: number;
      done_count: number;
    };
  };
  current_sprint?: string;
  project: string;
}

// Workspace types
export interface WorkspaceDetail {
  id: string;
  title: string;
  project: string;
  created_from: {
    type: "jira" | "agent" | "mr" | "deployment";
    id: string;
  };
  jira_tickets: JiraTicketReference[];
  agents: AgentReference[];
  branches: BranchReference[];
  merge_requests: MRReference[];
  deployments: DeploymentReference[];
  created_at: string;
  last_active_at: string;
  archived_at?: string;
}

export interface WorkspaceSummary {
  id: string;
  title: string;
  project: string;
  primary_jira_key?: string;
  resource_counts: {
    jira_tickets: number;
    agents: number;
    branches: number;
    merge_requests: number;
    deployments: number;
  };
  last_active_at: string;
}

export interface JiraTicketReference {
  key: string;
  is_primary: boolean;
  description_expanded?: boolean;
  comments_expanded?: boolean;
  pinned_at: string;
}

export interface AgentReference {
  id: string;
  session_id?: string;
  title?: string;
  first_prompt?: string;
  status: "live" | "idle" | "dead";
  is_pinned: boolean;
  message_count: number;
  added_at: string;
  last_active_at?: string;
}

export interface BranchReference {
  name: string;
  worktree_path?: string;
  is_active: boolean;
  added_at: string;
}

export interface MRReference {
  project: string;
  iid: number;
  branch_name: string;
  status?: string;
  url?: string;
  added_at: string;
}

export interface DeploymentReference {
  environment: string;
  namespace?: string;
  version?: string;
  status?: string;
  url?: string;
  added_at: string;
  updated_at: string;
}

export interface WorkspaceCreateRequest {
  created_from_type: "jira" | "agent" | "mr" | "deployment";
  created_from_id: string;
  project?: string;
  title?: string;
  auto_discover?: boolean;
}

export interface WorkspaceListResponse {
  workspaces: WorkspaceDetail[];
  total: number;
}

// Planet Commander - Context Resolution types
export interface JiraIssueInContext {
  id: string;
  external_key: string;
  title: string;
  status: string;
  priority: string | null;
  assignee: string | null;
  url: string;
}

export interface ChatInContext {
  id: string;
  title: string | null;
  status: string;
  project: string | null;
  jira_key: string | null;
  message_count: number;
  last_active_at: string | null;
}

export interface BranchInContext {
  id: string;
  repo: string;
  branch_name: string;
  status: string;
  ahead_count: number | null;
  behind_count: number | null;
  has_open_pr: boolean;
  linked_ticket_key_guess: string | null;
}

export interface WorktreeInContext {
  id: string;
  path: string;
  repo: string;
  status: string;
  is_active: boolean;
  has_uncommitted_changes: boolean;
  has_untracked_files: boolean;
  is_rebasing: boolean;
}

export interface EntityLinkInContext {
  id: string;
  from_type: string;
  from_id: string;
  to_type: string;
  to_id: string;
  link_type: string;
  source_type: string;
  status: string;
  confidence_score: number | null;
  link_metadata: Record<string, any> | null;
}

export interface V2DocLayer {
  name: string;
  tokens: number;
  layer: number;
}

export interface V2DocsMetadata {
  layers: V2DocLayer[];
  total_tokens: number;
  budget_limit: number;
  budget_exceeded: boolean;
}

export interface ContextHealth {
  has_ticket: boolean;
  has_branch: boolean;
  has_active_worktree: boolean;
  has_chat: boolean;
  overall: "green" | "yellow" | "red";
}

export interface MergeRequestInContext {
  id: string;
  external_mr_id: number;
  repository: string;
  title: string;
  url: string;
  source_branch: string;
  target_branch: string;
  author: string;
  state: string;
  approval_status: string | null;
  ci_status: string | null;
  jira_keys: string[];
  created_at: string;
  updated_at: string;
  merged_at: string | null;
  is_approved: boolean;
  is_ci_passing: boolean;
  is_merged: boolean;
  is_open: boolean;
  age_days: number;
  project_name: string;
}

export interface AuditRunSummary {
  id: string;
  family: string;
  verdict: string;
  finding_count: number;
  blocking_count: number;
  risk_score: number | null;
  dimension_scores: Record<string, number> | null;
  created_at: string;
}

export interface FindingsSummary {
  total: number;
  errors: number;
  warnings: number;
  info: number;
  blocking: number;
  auto_fixable: number;
}

export interface ContextResponse {
  id: string;
  title: string;
  slug: string;
  origin_type: string;
  status: string;
  health_status: string;
  summary_text: string | null;
  owner: string | null;
  jira_issues: JiraIssueInContext[];
  chats: ChatInContext[];
  branches: BranchInContext[];
  worktrees: WorktreeInContext[];
  pagerduty_incidents: PagerDutyIncident[];
  grafana_alerts: GrafanaAlertDefinition[];
  artifacts: InvestigationArtifact[];
  merge_requests: MergeRequestInContext[];
  audit_runs: AuditRunSummary[];
  findings_summary: FindingsSummary | null;
  links: EntityLinkInContext[];
  v2_docs: V2DocsMetadata | null;
  health: ContextHealth;
}

// Planet Commander - Link Management types
export interface CreateLinkRequest {
  from_type: string;
  from_id: string;
  to_type: string;
  to_id: string;
  link_type: string;
  source_type?: string;
  confidence_score?: number | null;
}

export interface LinkResponse {
  id: string;
  from_type: string;
  from_id: string;
  to_type: string;
  to_id: string;
  link_type: string;
  source_type: string;
  status: string;
  confidence_score: number | null;
  created_at: string;
  updated_at: string;
}

// Infrastructure types
export interface InfraResponse {
  timestamp: string;
  preemption: {
    zones: Array<{
      zone: string;
      hourly_counts: Array<{ time: string; count: number }>;
      current_rate_hr: number;
    }>;
    total_hr: number;
    total_instances: number;
    pct: number;
    history: Array<{ weeks_ago: number; rate_hr: number | null }>;
  };
  g4_scale: Array<{
    cluster: string;
    pool_size: number;
    success_rate_hr: number;
    failure_rate_hr: number;
    queue_backlog: number;
    backlog_by_priority: Record<string, number>;
  }>;
  g4_total_pool: number;
  k8s_clusters: Array<{
    cluster: string;
    nodes: number;
    pods: number | null;
  }>;
  k8s_total_nodes: number;
  jobs_queue: {
    total_queued: number;
    top_programs: Array<{ program: string; queued: number }>;
  };
  pipeline_throughput_hr: number;
}

// Background Jobs types
export interface JobRunResponse {
  id: number;
  job_name: string;
  started_at: string;
  completed_at: string | null;
  status: "running" | "success" | "failed";
  records_processed: number;
  error_message: string | null;
  duration_seconds: number | null;
}

export interface JobStatusResponse {
  job_id: string;
  next_run_time: string | null;
}

// Health Audit types
export interface HealthAuditResult {
  context_id: string;
  score: number;
  health_status: "green" | "yellow" | "red" | "unknown";
  issues: string[];
  updated_at: string;
}

export interface HealthAuditSummary {
  total_contexts: number;
  audited: number;
  health_distribution: {
    green: number;
    yellow: number;
    red: number;
    unknown: number;
  };
}

export interface StaleContext {
  id: string;
  title: string;
  status: string;
  days_since_update: number;
  last_updated: string;
}

export interface OrphanedEntities {
  branches: Array<{ id: string; name: string; repo: string }>;
  worktrees: Array<{ id: string; path: string }>;
  chats: Array<{ id: string; name: string; jira_key: string | null }>;
  jira_issues: Array<{ id: string; key: string; summary: string }>;
}

// AI Summaries & Artifacts types
export interface SummaryResponse {
  one_liner: string;
  short: string;
  detailed: string;
  cached?: boolean;
  model?: string;
  created_at?: string;
}

export interface ArtifactResponse {
  id: string;
  type: "code_snippet" | "command" | "config" | "sql_query" | "error_message" | "url" | "file_path" | "decision";
  title: string;
  content: string;
  language: string | null;
  importance: number;
  chat_id?: string;
  created_at: string;
}

export interface ArtifactExtractionResult {
  chat_id: string;
  extracted: number;
  total: number;
  cached: boolean;
}

// Workflow Automation types
export interface PRCreationResult {
  status: "success" | "error";
  message: string;
  mr_url?: string;
  mr_iid?: number;
  chat_id: string;
  branch: string;
  target_branch?: string;
}

export interface JiraSyncResult {
  context_id: string;
  synced_count?: number;
  commented_count?: number;
  total_links: number;
  errors: string[];
}

export interface SlackNotificationResult {
  success: boolean;
  channel: string;
  message?: string;
  error?: string;
}

export interface GitLabMRResult {
  success: boolean;
  project: string;
  mr_iid: number;
  message?: string;
  error?: string;
  approved?: boolean;
  merged?: boolean;
  when_pipeline_succeeds?: boolean;
  step?: string;
  has_conflicts?: boolean;
}

export interface GitLabMRStatusResult {
  success: boolean;
  project: string;
  mr_iid: number;
  state?: string;
  mergeable?: boolean;
  pipeline_status?: string;
  approvals?: number;
  has_conflicts?: boolean;
  error?: string;
}

export interface PagerDutyIncident {
  id: string;
  external_incident_id: string;
  incident_number: number | null;
  title: string;
  status: string;
  urgency: string | null;
  service_name: string | null;
  escalation_policy_name: string | null;
  assigned_to: Array<{ id: string; email: string; name: string }> | null;
  teams: Array<{ id: string; name: string }> | null;
  triggered_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  incident_url: string | null;
  html_url: string | null;

  // Computed properties
  is_active: boolean;
  is_resolved: boolean;
  is_high_urgency: boolean;
  duration_minutes: number | null;
  time_to_ack_minutes: number | null;
  team_names: string[];
  assigned_user_names: string[];
  is_compute_team: boolean;
  age_minutes: number;
}

export interface PagerDutyIncidentDetail extends PagerDutyIncident {
  description: string | null;
  priority: any | null;
  acknowledgements: any[] | null;
  assignments: any[] | null;
  log_entries: any[] | null;
  alerts: any[] | null;
  incident_key: string | null;
  last_status_change_at: string | null;
}

export interface PagerDutyIncidentListResponse {
  incidents: PagerDutyIncident[];
  total: number;
}

export interface InvestigationArtifact {
  id: string;
  file_path: string;
  filename: string;
  file_size: number | null;
  project: string | null;
  artifact_type: string | null;
  created_at: string;
  title: string | null;
  description: string | null;
  content_preview: string;
  jira_keys: string[];
  keywords: string[];
  entities: {
    systems?: string[];
    alerts?: string[];
  };
  file_modified_at: string | null;
  indexed_at: string;
  age_days: number;
  is_recent: boolean;
  has_jira_keys: boolean;
}

export interface GrafanaAlertDefinition {
  id: string;
  alert_name: string;
  file_path: string;
  team: string | null;
  project: string | null;
  alert_expr: string;
  alert_for: string | null;
  labels: Record<string, string>;
  annotations: Record<string, string>;
  severity: string | null;
  runbook_url: string | null;
  summary: string | null;
  file_modified_at: string | null;
  last_synced_at: string;
  is_active: boolean;
  is_critical: boolean;
  is_warning: boolean;
  has_runbook: boolean;
}

export interface AlertFiring {
  id: string;
  alert_definition_id: string | null;
  alert_name: string;
  fired_at: string;
  resolved_at: string | null;
  state: string | null;
  labels: Record<string, string>;
  annotations: Record<string, string>;
  fingerprint: string | null;
  value: number | null;
  external_alert_id: string | null;
  fetched_at: string;
  duration_seconds: number | null;
  is_resolved: boolean;
  is_firing: boolean;
}

export interface ProjectDoc {
  id: string;
  project_name: string;
  file_path: string;
  team: string | null;
  primary_contact: string | null;
  repositories: string[];
  slack_channels: string[];
  word_count: number;
  is_stale: boolean;
  last_updated_days_ago: number;
  file_modified_at: string | null;
  last_synced_at: string;
  keywords: string[];
}

export interface ProjectDocSection {
  id: string;
  section_name: string;
  heading_level: number;
  content: string;
  order_index: number;
}

// Google Drive Documents
export interface GoogleDriveDocument {
  id: string;
  external_doc_id: string;
  doc_type: string;
  url: string;
  title: string;
  file_path: string;
  filename: string | null;
  shared_drive: string | null;
  folder_path: string | null;
  project: string | null;
  document_kind: string | null;
  last_modified_at: string | null;
  owner: string | null;
  jira_keys: string[] | null;
  keywords: string[] | null;
  last_indexed_at: string;
  created_at: string;
  updated_at: string;
  // Computed properties
  is_stale: boolean;
  is_postmortem: boolean;
  is_rfd: boolean;
  has_jira_keys: boolean;
  age_days: number;
}

export interface GoogleDriveDocumentListResponse {
  documents: GoogleDriveDocument[];
  total: number;
}

export interface GoogleDriveScanStats {
  total_scanned: number;
  new_docs: number;
  updated_docs: number;
  unchanged_docs: number;
  errors: string[];
}

// GitLab Merge Requests
export interface GitLabMR {
  id: string;
  external_mr_id: number;
  repository: string;
  title: string;
  description: string | null;
  url: string;
  source_branch: string;
  target_branch: string;
  author: string;
  reviewers: { username: string; name: string }[] | null;
  approval_status: string | null;
  ci_status: string | null;
  state: string;
  jira_keys: string[] | null;
  created_at: string;
  updated_at: string;
  merged_at: string | null;
  closed_at: string | null;
  last_synced_at: string;
  // Computed properties
  is_approved: boolean;
  is_ci_passing: boolean;
  is_merged: boolean;
  is_open: boolean;
  is_stale: boolean;
  age_days: number;
  has_jira_keys: boolean;
  short_repository: string;
  project_name: string;
}

export interface GitLabMRListResponse {
  mrs: GitLabMR[];
  total: number;
}

export interface GitLabMRScanStats {
  repository: string;
  state: string;
  total_scanned: number;
  new_mrs: number;
  updated_mrs: number;
  unchanged_mrs: number;
  errors: string[];
}

// Slack Threads
export interface SlackThread {
  id: string;
  channel_id: string;
  channel_name: string | null;
  thread_ts: string;
  permalink: string;

  // Metadata
  participant_count: number | null;
  message_count: number | null;
  start_time: string | null;
  end_time: string | null;
  duration_hours: number | null;

  // Summary
  summary_id: string | null;
  title: string | null;
  summary_text: string | null;

  // Context flags
  is_incident: boolean;
  severity: string | null;
  incident_type: string | null;
  surrounding_context_fetched: boolean;

  // Cross-references
  jira_keys: string[] | null;
  pagerduty_incident_ids: string[] | null;
  gitlab_mr_refs: string[] | null;
  cross_channel_refs: string[] | null;

  // Tracking
  fetched_at: string;
  last_updated_at: string;

  // Computed properties
  is_active: boolean;
  has_cross_references: boolean;
  duration_display: string;
  reference_count: number;
}

export interface SlackThreadDetail extends SlackThread {
  messages: any[] | null;
  participants: Array<{ id: string; name: string; display_name?: string; email?: string }> | null;
  reactions: Record<string, number> | null;
}

export interface SlackThreadListResponse {
  threads: SlackThread[];
  total: number;
}

export interface ParseUrlResponse {
  thread: SlackThread;
  newly_created: boolean;
}

export interface ParseJiraResponse {
  jira_key: string;
  threads_found: number;
  threads_synced: number;
  threads: SlackThread[];
}

// Skills Auto-Suggestion
export interface SkillRegistry {
  id: string;
  skill_name: string;
  title: string;
  description: string | null;
  category: string | null;
  complexity: string | null;
  estimated_duration: string | null;
  trigger_keywords: string[] | null;
  trigger_labels: string[] | null;
  trigger_systems: string[] | null;
  invocation_count: number;
  last_invoked_at: string | null;
}

export interface MatchReason {
  type: string;
  values?: string[];
  weight: number;
}

export interface SuggestedSkill {
  skill: SkillRegistry;
  confidence: number;
  match_reasons: MatchReason[];
}

export interface SkillSuggestionsResponse {
  context_id: string;
  suggestions: SuggestedSkill[];
  count: number;
}

export interface SkillListResponse {
  skills: SkillRegistry[];
  count: number;
}

export interface IndexingStatsResponse {
  indexed: number;
  updated: number;
  removed: number;
  errors: string[];
}

// Warning Monitor
export interface WarningEvent {
  id: string;
  alert_name: string;
  system: string | null;
  channel_name: string;
  severity: string;
  escalation_probability: number;
  escalation_reason: string | null;
  escalated: boolean;
  auto_cleared: boolean;
  first_seen: string;
  last_seen: string;
  escalated_at: string | null;
  cleared_at: string | null;
  age_minutes: number;
  has_standby_context: boolean;
  standby_context_id: string | null;
  incident_context_id: string | null;
}

export interface StandbyContext {
  id: string;
  title: string;
  summary_text: string | null;
  health_status: string;
  created_at: string;
  artifact_count: number;
  alert_definition_count: number;
}

export interface EscalationMetrics {
  alert_name: string;
  system: string | null;
  total_warnings: number;
  escalated_count: number;
  auto_cleared_count: number;
  escalation_rate: number | null;
  avg_time_to_escalation_seconds: number | null;
  avg_time_to_clear_seconds: number | null;
  last_seen: string | null;
  last_escalated: string | null;
}

export interface WarningsSummary {
  active_warnings: number;
  high_risk_warnings: number;
  escalated_today: number;
  auto_cleared_today: number;
  avg_escalation_probability: number;
}

export interface TrendDataPoint {
  date: string;  // YYYY-MM-DD
  warnings: number;
  escalated: number;
  auto_cleared: number;
}

export interface EscalationTrends {
  trends: TrendDataPoint[];
  period_days: number;
}

export interface PredictionAccuracy {
  total_predictions: number;
  correct_predictions: number;
  accuracy: number;  // 0.0 - 1.0
  false_positives: number;
  false_negatives: number;
}

// Feedback interfaces

export interface PredictionFeedback {
  prediction_was_correct: boolean;
  actual_escalated: boolean;
  predicted_probability: number;
  submitted_by?: string;
  comment?: string;
}

export interface ContextFeedback {
  context_was_useful: boolean;
  missing_information?: string;
  submitted_by?: string;
  comment?: string;
}

export interface FeedbackResponse {
  id: string;
  warning_event_id: string;
  feedback_type: string;
  submitted_at: string;
}

export interface FeedbackStats {
  total_feedback: number;
  prediction_accuracy: {
    total: number;
    correct: number;
    accuracy: number;
  };
  context_usefulness: {
    total: number;
    useful: number;
    usefulness_rate: number;
  };
}

// Learning System Interfaces

export interface AlertPerformance {
  alert_name: string;
  system: string | null;
  total_warnings: number;
  escalated_count: number;
  escalation_rate: number;
  avg_predicted_probability: number;
  feedback_count: number;
  correct_predictions: number;
  false_negatives: number;
  false_positives: number;
  accuracy: number | null;
  improvement_potential: number;
}

export interface AccuracyTrend {
  date: string;
  window_start: string;
  window_end: string;
  total_feedback: number;
  correct_predictions: number;
  accuracy: number;
}

export interface AlertTuning {
  alert_name: string;
  system: string | null;
  has_feedback: boolean;
  total_feedback?: number;
  accuracy?: number;
  false_positives?: number;
  false_negatives?: number;
  actual_escalation_rate?: number;
  avg_predicted_probability?: number;
  adjustment?: string;
  suggested_probability?: number;
  reason?: string;
  confidence?: string;
  suggestion?: string;
}

export interface LearningSummary {
  total_feedback: number;
  total_alerts_analyzed: number;
  alerts_with_feedback: number;
  well_tuned_alerts: number;
  high_potential_alerts: number;
  accuracy_improvement: number | null;
  current_accuracy: number | null;
  trend_windows: number;
}

// ECC Pattern Suggestion types
export interface SuggestedPattern {
  title: string;
  pattern_type: string;
  confidence: number;
  similarity_score: number;
  combined_score: number;
  matched_keywords: string[];
  relevance: string;
  trigger: string;
  approach: string;
  source_artifact: string;
}

// Service Health Dashboard
export interface ServiceStatus {
  service_name: string;
  display_name: string;
  team: string;
  total_alerts: number;
  green_count: number;
  yellow_count: number;
  orange_count: number;
  red_count: number;
  status: "green" | "yellow" | "orange" | "red";
  prodissue: string | null;
  prodissue_title: string | null;
  assigned_to: string | null;
}

export interface TeamGroup {
  team: string;
  status: "green" | "yellow" | "orange" | "red";
  services: ServiceStatus[];
}

export interface ServiceHealthResponse {
  timestamp: string;
  overall_status: "green" | "yellow" | "orange" | "red";
  teams: TeamGroup[];
  active_prodissues: Array<{ key: string; title: string; status: string }>;
  summary: {
    total_services: number;
    green: number;
    yellow: number;
    orange: number;
    red: number;
    active_prodissues: number;
    grafana_alert_definitions: number;
    lookback_hours: number;
  };
}

export interface IncidentDetail {
  incident_id: string;
  title: string;
  description: string | null;
  status: string;
  urgency: string;
  priority: string | null;
  triggered_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  duration_seconds: number;
  assigned_to: string | null;
  acknowledged_by: string | null;
  pd_url: string | null;
  prodissue_key: string | null;
  jira_keys: string[];
  slack_refs: string[];
  gitlab_refs: string[];
  grafana_refs: string[];
}

export interface ServiceDetailResponse {
  service_name: string;
  display_name: string;
  team: string;
  status: string;
  incidents: IncidentDetail[];
  summary: {
    total: number;
    active: number;
    resolved: number;
    triggered: number;
    acknowledged: number;
    high_urgency: number;
    low_urgency: number;
    p1: number;
    p2: number;
    p3: number;
  };
}

// Audit System types

export interface RiskFactor {
  id: string;
  score: number;
  detail: string;
}

export interface ChangeRiskResult {
  score: number;
  level: string;
  factors: RiskFactor[];
}

export interface AuditFinding {
  id: string;
  code: string;
  category: string;
  severity: string;
  confidence: string;
  title: string;
  description: string;
  blocking: boolean;
  auto_fixable: boolean;
  actions: Record<string, unknown>[] | null;
  status: string;
  resolution: string | null;
  source_file: string | null;
  source_line: number | null;
  related_entity_type: string | null;
  related_entity_id: string | null;
}

export interface AuditRun {
  id: string;
  audit_family: string;
  audit_tier: number;
  source: string;
  target_type: string;
  target_id: string;
  verdict: string;
  confidence: number;
  finding_count: number;
  blocking_count: number;
  auto_fixable_count: number;
  dimension_scores: Record<string, number> | null;
  risk_score: number | null;
  risk_level: string | null;
  risk_factors: Record<string, unknown>[] | null;
  duration_ms: number;
  findings: AuditFinding[];
  created_at: string;
}

export interface DimensionScores {
  objective_clarity: number;
  target_surface: number;
  acceptance_criteria: number;
  dependencies: number;
  validation_path: number;
  scope_boundaries: number;
  missing_decisions: number;
  execution_safety: number;
}

export interface CTAState {
  label: string;
  action: string;
  subtext: string;
  style: string;
  secondary_actions: Array<{ label: string; action: string }>;
}

// Coach Session types

export interface CoachItem {
  id: string;
  title: string | null;
  description: string | null;
  status: string;
  resolution: string | null;
  code: string | null;
  category: string | null;
  severity: string | null;
  blocking: boolean;
  notes: string | null;
}

export interface CoachSession {
  id: string;
  target_type: string;
  target_id: string;
  readiness: string;
  active_item_id: string | null;
  completed_count: number;
  total_count: number;
  items: CoachItem[];
  audit_run_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExplainResponse {
  explanation: string;
  recommended_approach: string;
  exact_edit: string | null;
  question: string;
  usage: Record<string, unknown>;
}

export interface EvaluateResponse {
  complete: boolean;
  follow_up: string | null;
  summary: string;
  suggested_resolution: string;
  usage: Record<string, unknown>;
}

export interface CoachTransitionResponse {
  item: CoachItem;
  next_item: CoachItem | null;
  all_done: boolean;
}
