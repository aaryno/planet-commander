"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { Search, RefreshCw, Plus, X, GitBranch, Ticket, FolderOpen, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getLabelColor } from "@/lib/label-colors";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";
import type { Agent, JiraTicketResult, WorktreeInfo } from "@/lib/api";
import { AgentRow } from "@/components/agents/AgentRow";
import { ChatSidebar } from "@/components/agents/ChatSidebar";
import { DirectoryPicker } from "@/components/agents/DirectoryPicker";
import { useDirectoryHistory } from "@/hooks/useDirectoryHistory";
import { useUrlNullableParam, useUrlBoolParam } from "@/lib/use-url-state";

const PROJECTS = ["wx", "g4", "jobs", "temporal", "general"];
const STATUSES = ["live", "idle", "dead"] as const;
const SOURCES = ["dashboard", "vscode"] as const;

export default function AgentsPage() {
  const [projectFilter, setProjectFilter] = useUrlNullableParam("project");
  const [statusFilter, setStatusFilter] = useUrlNullableParam("status");
  const [sourceFilter, setSourceFilter] = useUrlNullableParam("source");
  const [search, setSearch] = useState("");
  const [showHidden, setShowHidden] = useUrlBoolParam("hidden");
  const [syncing, setSyncing] = useState(false);
  const [showSpawnDialog, setShowSpawnDialog] = useState(false);

  // Chat sidebar state — agent ID in URL, object resolved from data
  const [sidebarAgentId, setSidebarAgentId] = useUrlNullableParam("agent");
  const [sidebarDocked, setSidebarDocked] = useUrlBoolParam("docked");

  // Derived sidebar state
  const [sidebarAgent, setSidebarAgent] = useState<Agent | null>(null);
  const sidebarOpen = sidebarAgentId !== null;

  const fetcher = useCallback(
    () =>
      showHidden
        ? api.agentsIncludeHidden(projectFilter ?? undefined)
        : api.agents(projectFilter ?? undefined),
    [projectFilter, showHidden],
  );

  const { data, loading, refresh } = usePoll(fetcher, 30000);

  let agents = data?.agents ?? [];

  // Client-side filters
  if (statusFilter) {
    agents = agents.filter((a: Agent) => a.status === statusFilter);
  }
  if (sourceFilter) {
    agents = agents.filter((a: Agent) => a.managed_by === sourceFilter);
  }
  if (search) {
    const q = search.toLowerCase();
    agents = agents.filter(
      (a: Agent) =>
        a.title.toLowerCase().includes(q) ||
        (a.git_branch && a.git_branch.toLowerCase().includes(q)) ||
        (a.first_prompt && a.first_prompt.toLowerCase().includes(q)),
    );
  }

  const handleSync = async () => {
    setSyncing(true);
    try {
      await api.agentSync();
      refresh();
    } finally {
      setSyncing(false);
    }
  };

  // Resolve agent object from ID when data loads
  useEffect(() => {
    if (sidebarAgentId && data?.agents) {
      const found = data.agents.find((a: Agent) => a.id === sidebarAgentId);
      setSidebarAgent(found ?? null);
    } else if (!sidebarAgentId) {
      setSidebarAgent(null);
    }
  }, [sidebarAgentId, data]);

  const handleAgentClick = useCallback((agent: Agent) => {
    setSidebarAgent(agent);
    setSidebarAgentId(agent.id);
  }, [setSidebarAgentId]);

  const handleSidebarClose = useCallback((open: boolean) => {
    if (!open) {
      setSidebarAgentId(null);
    }
  }, [setSidebarAgentId]);

  const handleHide = useCallback(async (id: string) => {
    try {
      await api.agentHide(id);
      // Close sidebar if hiding the current agent
      if (sidebarAgent?.id === id) {
        setSidebarAgentId(null);
      }
      refresh();
    } catch {
      // ignore
    }
  }, [sidebarAgent, refresh]);

  const handleUnhide = useCallback(async (id: string) => {
    try {
      await api.agentUnhide(id);
      refresh();
    } catch {
      // ignore
    }
  }, [refresh]);

  // Count by source
  const allAgents = data?.agents ?? [];
  const dashboardCount = allAgents.filter((a: Agent) => a.managed_by === "dashboard").length;
  const vscodeCount = allAgents.filter((a: Agent) => a.managed_by === "vscode").length;
  const hiddenCount = allAgents.filter((a: Agent) => a.hidden_at).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">All Agents</h1>
          <p className="text-sm text-zinc-500">
            {data?.total ?? 0} Claude Code sessions across all projects
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="border-cyan-700 text-cyan-300 hover:bg-cyan-900/30"
            onClick={() => setShowSpawnDialog(true)}
          >
            <Plus className="h-3.5 w-3.5 mr-2" />
            Launch Agent
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
            onClick={handleSync}
            disabled={syncing}
          >
            <RefreshCw className={`h-3.5 w-3.5 mr-2 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? "Syncing..." : "Sync"}
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
          <Input
            placeholder="Search agents, prompts, branches..."
            className="pl-9 bg-zinc-900 border-zinc-700 text-zinc-200 placeholder:text-zinc-500"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          {PROJECTS.map((p) => (
            <Badge
              key={p}
              variant="outline"
              className={`cursor-pointer border transition-colors ${
                projectFilter === p
                  ? getLabelColor(p, "project")
                  : "border-zinc-700 text-zinc-500 hover:text-zinc-300 hover:border-zinc-600"
              }`}
              onClick={() => setProjectFilter(projectFilter === p ? null : p)}
            >
              {p}
            </Badge>
          ))}
        </div>
        <div className="flex gap-2 ml-2">
          {STATUSES.map((s) => (
            <Badge
              key={s}
              variant="outline"
              className={`cursor-pointer border transition-colors ${
                statusFilter === s
                  ? s === "live"
                    ? "text-green-400 border-green-500 bg-green-500/10"
                    : s === "idle"
                      ? "text-yellow-400 border-yellow-500 bg-yellow-500/10"
                      : "text-zinc-400 border-zinc-500 bg-zinc-500/10"
                  : "border-zinc-700 text-zinc-500 hover:text-zinc-300 hover:border-zinc-600"
              }`}
              onClick={() => setStatusFilter(statusFilter === s ? null : s)}
            >
              {s}
            </Badge>
          ))}
        </div>
        {/* Source filter */}
        <div className="flex gap-2 ml-2">
          {SOURCES.map((s) => (
            <Badge
              key={s}
              variant="outline"
              className={`cursor-pointer border transition-colors ${
                sourceFilter === s
                  ? s === "dashboard"
                    ? "text-cyan-400 border-cyan-500 bg-cyan-500/10"
                    : "text-violet-400 border-violet-500 bg-violet-500/10"
                  : "border-zinc-700 text-zinc-500 hover:text-zinc-300 hover:border-zinc-600"
              }`}
              onClick={() => setSourceFilter(sourceFilter === s ? null : s)}
            >
              {s === "dashboard" ? `dashboard (${dashboardCount})` : `vscode (${vscodeCount})`}
            </Badge>
          ))}
        </div>
        {/* Hidden toggle */}
        <Badge
          variant="outline"
          className={`cursor-pointer border transition-colors ml-2 ${
            showHidden
              ? "text-orange-400 border-orange-500 bg-orange-500/10"
              : "border-zinc-700 text-zinc-500 hover:text-zinc-300 hover:border-zinc-600"
          }`}
          onClick={() => setShowHidden(!showHidden)}
        >
          {showHidden ? `hidden (${hiddenCount})` : "show hidden"}
        </Badge>
      </div>

      {/* Agent list */}
      {loading && agents.length === 0 ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="h-5 w-5 text-zinc-500 animate-spin" />
        </div>
      ) : agents.length === 0 ? (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-8 text-center">
          <p className="text-sm text-zinc-500">
            {search || projectFilter || statusFilter || sourceFilter
              ? "No agents match the current filters."
              : "No agents discovered yet. Click Sync to index sessions."}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {agents.map((agent: Agent) => (
            <AgentRow
              key={agent.id}
              agent={agent}
              onAgentClick={handleAgentClick}
              onHide={handleHide}
              onUnhide={handleUnhide}
            />
          ))}
        </div>
      )}

      {/* Spawn Agent Dialog */}
      {showSpawnDialog && (
        <SpawnAgentDialog
          onClose={() => setShowSpawnDialog(false)}
          onSpawned={() => {
            setShowSpawnDialog(false);
            refresh();
          }}
        />
      )}

      {/* Chat Sidebar */}
      <ChatSidebar
        agent={sidebarAgent}
        open={sidebarOpen}
        docked={sidebarDocked}
        onOpenChange={handleSidebarClose}
        onDockedChange={setSidebarDocked}
      />
    </div>
  );
}

// --- Searchable Dropdown ---

function SearchDropdown<T>({
  placeholder,
  icon: Icon,
  value,
  displayValue,
  onSelect,
  onClear,
  fetchResults,
  renderItem,
  getKey,
}: {
  placeholder: string;
  icon: React.ComponentType<{ className?: string }>;
  value: T | null;
  displayValue: string;
  onSelect: (item: T) => void;
  onClear: () => void;
  fetchResults: (query: string) => Promise<T[]>;
  renderItem: (item: T) => React.ReactNode;
  getKey: (item: T) => string;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<T[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);

  // Debounced search
  useEffect(() => {
    if (!open) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await fetchResults(query);
        setResults(r);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query, open, fetchResults]);

  // Click outside to close
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  if (value) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5">
        <Icon className="h-3.5 w-3.5 text-zinc-400 shrink-0" />
        <span className="text-sm text-zinc-200 truncate flex-1">{displayValue}</span>
        <button onClick={onClear} className="text-zinc-500 hover:text-zinc-300">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <Icon className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500" />
        <Input
          placeholder={placeholder}
          className="pl-9 bg-zinc-800 border-zinc-700 text-zinc-200 placeholder:text-zinc-600 text-sm"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setOpen(true)}
        />
        {loading && (
          <Loader2 className="absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500 animate-spin" />
        )}
      </div>
      {open && results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full max-h-48 overflow-y-auto rounded-md border border-zinc-700 bg-zinc-800 shadow-xl">
          {results.map((item) => (
            <button
              key={getKey(item)}
              className="w-full px-3 py-2 text-left hover:bg-zinc-700/50 transition-colors border-b border-zinc-700/50 last:border-0"
              onClick={() => {
                onSelect(item);
                setOpen(false);
                setQuery("");
              }}
            >
              {renderItem(item)}
            </button>
          ))}
        </div>
      )}
      {open && !loading && query && results.length === 0 && (
        <div className="absolute z-50 mt-1 w-full rounded-md border border-zinc-700 bg-zinc-800 shadow-xl px-3 py-2">
          <p className="text-xs text-zinc-500">No results</p>
        </div>
      )}
    </div>
  );
}

// --- Spawn Agent Dialog ---

function SpawnAgentDialog({
  onClose,
  onSpawned,
}: {
  onClose: () => void;
  onSpawned: () => void;
}) {
  const [workingDir, setWorkingDir] = useState("");
  const [project, setProject] = useState("");
  const [prompt, setPrompt] = useState("");
  const [spawning, setSpawning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { addToHistory } = useDirectoryHistory();

  // JIRA ticket selection
  const [selectedTicket, setSelectedTicket] = useState<JiraTicketResult | null>(null);

  // Worktree selection
  const [selectedWorktree, setSelectedWorktree] = useState<WorktreeInfo | null>(null);
  const [createWorktree, setCreateWorktree] = useState(true);

  // Whether project supports worktrees
  const supportsWorktree = ["wx", "jobs", "temporal"].includes(project);

  // Auto-fill working dir from worktree selection
  useEffect(() => {
    if (selectedWorktree) {
      setWorkingDir(selectedWorktree.path);
    }
  }, [selectedWorktree]);

  // JIRA search fetcher (memoized per project)
  const fetchJiraResults = useCallback(
    async (q: string) => {
      const data = await api.jiraSearch(q, project ? ["COMPUTE"] : undefined);
      return data.tickets;
    },
    [project],
  );

  // Worktree list fetcher (memoized per project)
  const fetchWorktreeResults = useCallback(
    async (q: string) => {
      const data = await api.worktreeList(project || undefined);
      const wts = data.worktrees;
      if (!q) return wts;
      const lq = q.toLowerCase();
      return wts.filter(
        (w) =>
          w.branch.toLowerCase().includes(lq) ||
          w.path.toLowerCase().includes(lq),
      );
    },
    [project],
  );

  const handleSpawn = async () => {
    if (!project) {
      setError("Select a project first");
      return;
    }
    setSpawning(true);
    setError(null);
    try {
      // If creating a new worktree, don't send working_directory (backend auto-creates)
      const shouldAutoCreate = createWorktree && !selectedWorktree && supportsWorktree;
      await api.agentSpawn({
        working_directory: shouldAutoCreate ? undefined : (workingDir || undefined),
        project: project || undefined,
        initial_prompt: prompt || undefined,
        jira_key: selectedTicket?.key,
        worktree_path: selectedWorktree?.path,
        worktree_branch: selectedWorktree?.branch,
      });
      if (workingDir) addToHistory(workingDir);
      onSpawned();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSpawning(false);
    }
  };

  // What the worktree will be named
  const newWorktreeName = selectedTicket
    ? `ao/${selectedTicket.key.toLowerCase()}`
    : "ao/(random)";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative w-full max-w-lg mx-4 rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-zinc-100">Launch Agent</h2>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-300"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4">
          {/* Project selector */}
          <div>
            <label className="block text-xs text-zinc-400 mb-1">Project</label>
            <div className="flex gap-2">
              {PROJECTS.map((p) => (
                <Badge
                  key={p}
                  variant="outline"
                  className={`cursor-pointer border transition-colors ${
                    project === p
                      ? getLabelColor(p, "project")
                      : "border-zinc-700 text-zinc-500 hover:text-zinc-300"
                  }`}
                  onClick={() => {
                    setProject(project === p ? "" : p);
                    // Clear worktree/ticket when project changes
                    setSelectedWorktree(null);
                    setSelectedTicket(null);
                    setWorkingDir("");
                  }}
                >
                  {p}
                </Badge>
              ))}
            </div>
          </div>

          {/* JIRA ticket search */}
          <div>
            <label className="block text-xs text-zinc-400 mb-1">
              <Ticket className="inline h-3 w-3 mr-1" />
              JIRA Ticket (optional)
            </label>
            <SearchDropdown<JiraTicketResult>
              placeholder="Search COMPUTE-1234 or keywords..."
              icon={Ticket}
              value={selectedTicket}
              displayValue={selectedTicket ? `${selectedTicket.key}: ${selectedTicket.summary}` : ""}
              onSelect={(t) => {
                setSelectedTicket(t);
                // If no prompt yet, pre-fill with ticket summary
                if (!prompt) {
                  setPrompt(`Work on ${t.key}: ${t.summary}`);
                }
              }}
              onClear={() => setSelectedTicket(null)}
              fetchResults={fetchJiraResults}
              renderItem={(t) => (
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-cyan-400">{t.key}</span>
                    <span className="text-xs text-zinc-500">{t.status}</span>
                    {t.assignee !== "Unassigned" && (
                      <span className="text-xs text-zinc-600 ml-auto">{t.assignee}</span>
                    )}
                  </div>
                  <p className="text-sm text-zinc-300 truncate">{t.summary}</p>
                </div>
              )}
              getKey={(t) => t.key}
            />
          </div>

          {/* Git Worktree */}
          {supportsWorktree && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-xs text-zinc-400">
                  <GitBranch className="inline h-3 w-3 mr-1" />
                  Git Worktree
                </label>
                <label className="flex items-center gap-1.5 text-xs text-zinc-500 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={createWorktree}
                    onChange={(e) => {
                      setCreateWorktree(e.target.checked);
                      if (e.target.checked) {
                        setSelectedWorktree(null);
                        setWorkingDir("");
                      }
                    }}
                    className="rounded border-zinc-600 bg-zinc-800 h-3.5 w-3.5 text-cyan-500"
                  />
                  Create new
                </label>
              </div>

              {createWorktree && !selectedWorktree ? (
                <div className="rounded-md border border-dashed border-zinc-700 bg-zinc-800/50 px-3 py-2">
                  <p className="text-xs text-zinc-400">
                    New worktree: <span className="font-mono text-cyan-400">{newWorktreeName}</span>
                  </p>
                  <p className="text-xs text-zinc-600 mt-0.5">
                    Working directory will be auto-set to the worktree path
                  </p>
                </div>
              ) : (
                <SearchDropdown<WorktreeInfo>
                  placeholder="Search branches or worktree paths..."
                  icon={GitBranch}
                  value={selectedWorktree}
                  displayValue={selectedWorktree ? `${selectedWorktree.branch} (${selectedWorktree.path})` : ""}
                  onSelect={(w) => {
                    setSelectedWorktree(w);
                    setCreateWorktree(false);
                  }}
                  onClear={() => {
                    setSelectedWorktree(null);
                    setWorkingDir("");
                  }}
                  fetchResults={fetchWorktreeResults}
                  renderItem={(w) => (
                    <div>
                      <div className="flex items-center gap-2">
                        <GitBranch className="h-3 w-3 text-zinc-500 shrink-0" />
                        <span className="text-sm text-zinc-200 truncate">{w.branch}</span>
                        <span className="text-xs font-mono text-zinc-600 ml-auto">{w.commit}</span>
                      </div>
                      <p className="text-xs text-zinc-500 truncate">{w.path}</p>
                    </div>
                  )}
                  getKey={(w) => w.path}
                />
              )}
            </div>
          )}

          {/* Working directory (auto-filled from worktree, overridable) */}
          <div>
            <label className="block text-xs text-zinc-400 mb-1">
              <FolderOpen className="inline h-3 w-3 mr-1" />
              Working Directory
              {selectedWorktree && <span className="text-cyan-500/60 ml-1">(from worktree)</span>}
              {createWorktree && !selectedWorktree && supportsWorktree && (
                <span className="text-cyan-500/60 ml-1">(auto from new worktree)</span>
              )}
            </label>
            <DirectoryPicker
              value={workingDir}
              onChange={setWorkingDir}
              disabled={createWorktree && !selectedWorktree && supportsWorktree}
              placeholder={
                createWorktree && supportsWorktree
                  ? "(auto-resolved from worktree)"
                  : "~/workspaces/wx-1"
              }
            />
          </div>

          {/* Initial prompt */}
          <div>
            <label className="block text-xs text-zinc-400 mb-1">
              Initial Prompt (optional)
            </label>
            <textarea
              placeholder="What should this agent work on?"
              className="w-full resize-y min-h-[80px] max-h-[200px] rounded-md border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </div>

          {error && (
            <p className="text-xs text-red-400">{error}</p>
          )}

          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              className="border-zinc-700 text-zinc-400"
              onClick={onClose}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              className="bg-cyan-600 hover:bg-cyan-700 text-white"
              onClick={handleSpawn}
              disabled={spawning || !project}
            >
              {spawning ? "Launching..." : "Launch"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
