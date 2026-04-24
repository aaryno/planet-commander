"use client";

import { useState, useEffect, useCallback } from "react";
import {
  ShoppingCart,
  X,
  Trash2,
  Rocket,
  ArrowLeft,
  Loader2,
  GitBranch,
  FileText,
  MessageSquare,
  AlertTriangle,
  Ticket,
  GitPullRequest,
  FolderPlus,
  FolderOpen,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter,
} from "@/components/ui/sheet";
import { useCart, type CartItem } from "@/lib/cart";
import { api } from "@/lib/api";
import type {
  ContextResponse,
  AgentSummary,
  JiraIssueInContext,
  MergeRequestInContext,
  InvestigationArtifact,
  WorktreeInfo,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Step = "cart" | "configure";

interface MergedContext {
  jiraIssues: JiraIssueInContext[];
  mergeRequests: MergeRequestInContext[];
  artifacts: InvestigationArtifact[];
  slackThreadCount: number;
  incidentCount: number;
}

// ---------------------------------------------------------------------------
// CartItemCard
// ---------------------------------------------------------------------------

function CartItemCard({
  item,
  onRemove,
}: {
  item: CartItem;
  onRemove: (id: string) => void;
}) {
  const age = (() => {
    const h = Math.floor(
      (Date.now() - new Date(item.addedAt).getTime()) / 3600000,
    );
    if (h < 1) return "just now";
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  })();

  return (
    <div className="flex items-start gap-3 rounded-lg border border-zinc-800 bg-zinc-900/50 p-3 group">
      <div className="flex-1 min-w-0">
        <p className="text-sm text-zinc-200 truncate">{item.agentTitle}</p>
        <div className="flex items-center gap-1.5 mt-1 flex-wrap">
          <Badge
            variant="outline"
            className="text-[9px] px-1 py-0 text-zinc-400 border-zinc-700"
          >
            {item.project}
          </Badge>
          {item.jiraKey && (
            <span className="text-[9px] font-mono text-cyan-400 px-1 py-0.5 rounded bg-cyan-500/10">
              {item.jiraKey}
            </span>
          )}
          {item.gitBranch && item.gitBranch !== "HEAD" && (
            <span className="text-[9px] font-mono text-zinc-500 truncate max-w-[120px]">
              {item.gitBranch.split("/").pop()}
            </span>
          )}
          <span className="text-[9px] text-zinc-600 ml-auto">{age}</span>
        </div>
      </div>
      <button
        onClick={() => onRemove(item.agentId)}
        className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-900/30 transition-all shrink-0"
        title="Remove from cart"
      >
        <X className="h-3 w-3 text-zinc-500 hover:text-red-400" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dedup helpers
// ---------------------------------------------------------------------------

function dedup<T>(items: T[], keyFn: (item: T) => string): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const k = keyFn(item);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

function mergeContexts(contexts: ContextResponse[]): MergedContext {
  const jiraIssues = dedup(
    contexts.flatMap((c) => c.jira_issues),
    (i) => i.external_key,
  );
  const mergeRequests = dedup(
    contexts.flatMap((c) => c.merge_requests),
    (m) => `${m.repository}:${m.external_mr_id}`,
  );
  const artifacts = dedup(
    contexts.flatMap((c) => c.artifacts),
    (a) => a.id,
  );
  const slackThreadCount = new Set(
    contexts
      .flatMap((c) => c.links)
      .filter((l) => l.to_type === "slack_thread" || l.from_type === "slack_thread")
      .map((l) => (l.to_type === "slack_thread" ? l.to_id : l.from_id)),
  ).size;
  const incidentCount = new Set(
    contexts.flatMap((c) =>
      c.pagerduty_incidents.map((i) => i.external_incident_id),
    ),
  ).size;

  return { jiraIssues, mergeRequests, artifacts, slackThreadCount, incidentCount };
}

// ---------------------------------------------------------------------------
// ConfigureStep
// ---------------------------------------------------------------------------

function ConfigureStep({
  items,
  onBack,
  onLaunch,
}: {
  items: CartItem[];
  onBack: () => void;
  onLaunch: (config: LaunchConfig) => void;
}) {
  const [loading, setLoading] = useState(true);
  const [merged, setMerged] = useState<MergedContext | null>(null);
  const [summaries, setSummaries] = useState<Record<string, AgentSummary>>({});
  const [dominantJira, setDominantJira] = useState<string | null>(null);
  const [worktreeMode, setWorktreeMode] = useState<"new" | "reuse">("new");
  const [worktrees, setWorktrees] = useState<WorktreeInfo[]>([]);
  const [selectedWorktree, setSelectedWorktree] = useState<WorktreeInfo | null>(null);
  const [model, setModel] = useState("sonnet");
  const [userPrompt, setUserPrompt] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Fetch contexts + summaries for all cart agents
  useEffect(() => {
    let cancelled = false;

    async function fetchAll() {
      setLoading(true);
      setError(null);
      try {
        // Fetch contexts in parallel
        const contextResults = await Promise.allSettled(
          items.map((item) => api.contextByChatId(item.agentId)),
        );
        const contexts = contextResults
          .filter((r): r is PromiseFulfilledResult<ContextResponse> => r.status === "fulfilled")
          .map((r) => r.value);

        if (!cancelled) {
          setMerged(mergeContexts(contexts));

          // Auto-select most common JIRA key
          const keyCounts: Record<string, number> = {};
          for (const item of items) {
            if (item.jiraKey) {
              keyCounts[item.jiraKey] = (keyCounts[item.jiraKey] || 0) + 1;
            }
          }
          const topKey = Object.entries(keyCounts).sort((a, b) => b[1] - a[1])[0];
          if (topKey) setDominantJira(topKey[0]);
        }

        // Fetch summaries in parallel (trigger generation if needed)
        const summaryResults = await Promise.allSettled(
          items.map(async (item) => {
            let s = await api.agentSummary(item.agentId);
            if (s.status === "none") {
              s = await api.agentSummarize(item.agentId);
            }
            return { agentId: item.agentId, summary: s };
          }),
        );

        if (!cancelled) {
          const sMap: Record<string, AgentSummary> = {};
          for (const r of summaryResults) {
            if (r.status === "fulfilled") {
              sMap[r.value.agentId] = r.value.summary;
            }
          }
          setSummaries(sMap);
        }

        // Fetch worktrees
        const project = items[0]?.project;
        if (project && project !== "general") {
          const wt = await api.worktreeList(project);
          if (!cancelled) setWorktrees(wt.worktrees);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchAll();
    return () => { cancelled = true; };
  }, [items]);

  // Poll for summaries that are in_progress
  useEffect(() => {
    const inProgress = Object.entries(summaries).filter(
      ([, s]) => s.status === "in_progress",
    );
    if (inProgress.length === 0) return;

    const timer = setInterval(async () => {
      for (const [agentId] of inProgress) {
        try {
          const s = await api.agentSummary(agentId);
          if (s.status !== "in_progress") {
            setSummaries((prev) => ({ ...prev, [agentId]: s }));
          }
        } catch {}
      }
    }, 3000);

    return () => clearInterval(timer);
  }, [summaries]);

  // Build preamble
  const preamble = (() => {
    const lines: string[] = [
      `You are continuing work that spans ${items.length} previous agent sessions.`,
      "",
    ];

    for (const item of items) {
      const s = summaries[item.agentId];
      lines.push(`## Session: ${item.agentTitle}`);
      if (s?.status === "ready" && s.short) {
        lines.push(s.short);
      } else if (s?.status === "ready" && s.phrase) {
        lines.push(s.phrase);
      } else if (s?.status === "in_progress") {
        lines.push("(Summary generating...)");
      } else {
        lines.push("(No summary available)");
      }
      if (item.jiraKey) lines.push(`JIRA: ${item.jiraKey}`);
      if (item.gitBranch && item.gitBranch !== "HEAD")
        lines.push(`Branch: ${item.gitBranch}`);
      lines.push("");
    }

    if (merged?.mergeRequests.length) {
      lines.push("## Open Merge Requests");
      for (const mr of merged.mergeRequests) {
        lines.push(`- !${mr.external_mr_id}: ${mr.title} (${mr.state})`);
      }
      lines.push("");
    }

    lines.push("## Your Task");
    lines.push(userPrompt || "(describe what the new agent should do)");

    return lines.join("\n");
  })();

  const summariesReady = items.every(
    (item) =>
      summaries[item.agentId]?.status === "ready" ||
      summaries[item.agentId]?.status === "none",
  );

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 px-4">
        <Loader2 className="h-6 w-6 text-zinc-500 animate-spin" />
        <p className="text-sm text-zinc-500">Loading context from {items.length} agents...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 px-4">
        <AlertTriangle className="h-6 w-6 text-red-400" />
        <p className="text-sm text-red-400">{error}</p>
        <Button variant="ghost" size="sm" onClick={onBack}>Back</Button>
      </div>
    );
  }

  return (
    <>
      {/* Header */}
      <div className="px-4 pb-2 border-b border-zinc-800">
        <button
          onClick={onBack}
          className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300 mb-2"
        >
          <ArrowLeft className="h-3 w-3" />
          Back to cart
        </button>
        <h3 className="text-sm font-semibold text-zinc-200">Configure Launch</h3>
        <p className="text-xs text-zinc-500 mt-0.5">
          Merging {items.length} sessions into a new agent
        </p>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-4 space-y-4 py-3">
        {/* Discovered Context */}
        {merged && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Discovered Context
            </h4>
            <div className="grid grid-cols-2 gap-2">
              <Stat icon={Ticket} label="JIRA Tickets" count={merged.jiraIssues.length} color="text-cyan-400" />
              <Stat icon={GitPullRequest} label="Merge Requests" count={merged.mergeRequests.length} color="text-violet-400" />
              <Stat icon={MessageSquare} label="Slack Threads" count={merged.slackThreadCount} color="text-blue-400" />
              <Stat icon={FileText} label="Artifacts" count={merged.artifacts.length} color="text-emerald-400" />
              {merged.incidentCount > 0 && (
                <Stat icon={AlertTriangle} label="Incidents" count={merged.incidentCount} color="text-red-400" />
              )}
            </div>
          </div>
        )}

        {/* Dominant JIRA Ticket */}
        {merged && merged.jiraIssues.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Primary JIRA Ticket
            </h4>
            <p className="text-[10px] text-zinc-600">
              This ticket becomes the new agent&apos;s context origin
            </p>
            <div className="space-y-1">
              {merged.jiraIssues.map((issue) => (
                <label
                  key={issue.external_key}
                  className={`flex items-center gap-2 p-2 rounded-md cursor-pointer border transition-colors ${
                    dominantJira === issue.external_key
                      ? "border-cyan-600/50 bg-cyan-500/5"
                      : "border-zinc-800 hover:border-zinc-700"
                  }`}
                >
                  <input
                    type="radio"
                    name="dominant-jira"
                    checked={dominantJira === issue.external_key}
                    onChange={() => setDominantJira(issue.external_key)}
                    className="accent-cyan-500"
                  />
                  <span className="text-xs font-mono text-cyan-400">{issue.external_key}</span>
                  <span className="text-xs text-zinc-300 truncate flex-1">{issue.title}</span>
                  <Badge variant="outline" className="text-[9px] px-1 py-0 border-zinc-700 text-zinc-500">
                    {issue.status}
                  </Badge>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Worktree */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            Worktree
          </h4>
          <div className="flex gap-2">
            <button
              onClick={() => { setWorktreeMode("new"); setSelectedWorktree(null); }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs border transition-colors ${
                worktreeMode === "new"
                  ? "border-cyan-600/50 bg-cyan-500/5 text-cyan-300"
                  : "border-zinc-800 text-zinc-500 hover:border-zinc-700"
              }`}
            >
              <FolderPlus className="h-3 w-3" />
              Create new
            </button>
            <button
              onClick={() => setWorktreeMode("reuse")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs border transition-colors ${
                worktreeMode === "reuse"
                  ? "border-cyan-600/50 bg-cyan-500/5 text-cyan-300"
                  : "border-zinc-800 text-zinc-500 hover:border-zinc-700"
              }`}
            >
              <FolderOpen className="h-3 w-3" />
              Reuse existing
            </button>
          </div>
          {worktreeMode === "new" && dominantJira && (
            <p className="text-[10px] text-zinc-600">
              Will create branch: <span className="font-mono text-zinc-400">ao/{dominantJira.toLowerCase()}</span>
            </p>
          )}
          {worktreeMode === "reuse" && (
            <div className="space-y-1 max-h-[120px] overflow-y-auto">
              {worktrees.length === 0 ? (
                <p className="text-[10px] text-zinc-600">No worktrees found for this project</p>
              ) : (
                worktrees.map((wt) => (
                  <label
                    key={wt.path}
                    className={`flex items-center gap-2 p-2 rounded-md cursor-pointer border transition-colors ${
                      selectedWorktree?.path === wt.path
                        ? "border-cyan-600/50 bg-cyan-500/5"
                        : "border-zinc-800 hover:border-zinc-700"
                    }`}
                  >
                    <input
                      type="radio"
                      name="worktree"
                      checked={selectedWorktree?.path === wt.path}
                      onChange={() => setSelectedWorktree(wt)}
                      className="accent-cyan-500"
                    />
                    <GitBranch className="h-3 w-3 text-zinc-500" />
                    <span className="text-xs font-mono text-zinc-300 truncate">{wt.branch}</span>
                    <span className="text-[9px] text-zinc-600 ml-auto">{wt.commit.slice(0, 7)}</span>
                  </label>
                ))
              )}
            </div>
          )}
        </div>

        {/* Model */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            Model
          </h4>
          <div className="flex gap-1.5">
            {(["opus", "sonnet", "haiku"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setModel(m)}
                className={`px-3 py-1 rounded-md text-xs border transition-colors capitalize ${
                  model === m
                    ? "border-violet-600/50 bg-violet-500/10 text-violet-300"
                    : "border-zinc-800 text-zinc-500 hover:border-zinc-700"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        </div>

        {/* Session Summaries */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            Session Summaries
          </h4>
          {items.map((item) => {
            const s = summaries[item.agentId];
            return (
              <div key={item.agentId} className="rounded-md border border-zinc-800 p-2">
                <p className="text-xs font-medium text-zinc-300 truncate">{item.agentTitle}</p>
                {s?.status === "in_progress" && (
                  <div className="flex items-center gap-1.5 mt-1">
                    <Loader2 className="h-3 w-3 text-zinc-500 animate-spin" />
                    <span className="text-[10px] text-zinc-500">Generating summary...</span>
                  </div>
                )}
                {s?.status === "ready" && (
                  <p className="text-[11px] text-zinc-400 mt-1 line-clamp-3">
                    {s.short || s.phrase || "No summary content"}
                  </p>
                )}
                {(!s || s.status === "none") && (
                  <p className="text-[10px] text-zinc-600 mt-1 italic">No summary available</p>
                )}
              </div>
            );
          })}
        </div>

        {/* Prompt */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            Instructions for New Agent
          </h4>
          <textarea
            value={userPrompt}
            onChange={(e) => setUserPrompt(e.target.value)}
            placeholder="What should the new agent do with this context?"
            className="w-full h-20 bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 resize-none focus:outline-none focus:border-zinc-700"
          />
        </div>

        {/* Preamble Preview */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            Context Preamble Preview
          </h4>
          <pre className="text-[10px] text-zinc-500 bg-zinc-900/50 border border-zinc-800 rounded-md p-3 max-h-[200px] overflow-y-auto whitespace-pre-wrap font-mono">
            {preamble}
          </pre>
        </div>
      </div>

      {/* Launch Footer */}
      <SheetFooter className="border-t border-zinc-800">
        <div className="flex items-center gap-2 w-full">
          <Button variant="ghost" size="sm" className="text-xs text-zinc-500" onClick={onBack}>
            <ArrowLeft className="h-3 w-3 mr-1" />
            Back
          </Button>
          <div className="flex-1" />
          <Button
            size="sm"
            className="text-xs bg-cyan-600 hover:bg-cyan-700 text-white"
            onClick={() =>
              onLaunch({
                sourceAgentIds: items.map((i) => i.agentId),
                project: items[0]?.project || "general",
                jiraKey: dominantJira,
                worktreeMode,
                worktreePath: selectedWorktree?.path || null,
                worktreeBranch: selectedWorktree?.branch || null,
                model,
                preamble,
                userPrompt,
              })
            }
            disabled={!summariesReady}
          >
            <Rocket className="h-3 w-3 mr-1" />
            Launch Agent
          </Button>
        </div>
      </SheetFooter>
    </>
  );
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function Stat({
  icon: Icon,
  label,
  count,
  color,
}: {
  icon: typeof Ticket;
  label: string;
  count: number;
  color: string;
}) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900/50 px-3 py-2">
      <Icon className={`h-3.5 w-3.5 ${color}`} />
      <div>
        <p className="text-sm font-medium text-zinc-200">{count}</p>
        <p className="text-[10px] text-zinc-500">{label}</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Launch config type
// ---------------------------------------------------------------------------

export interface LaunchConfig {
  sourceAgentIds: string[];
  project: string;
  jiraKey: string | null;
  worktreeMode: "new" | "reuse";
  worktreePath: string | null;
  worktreeBranch: string | null;
  model: string;
  preamble: string;
  userPrompt: string;
}

// ---------------------------------------------------------------------------
// CartDrawer
// ---------------------------------------------------------------------------

export function CartDrawer() {
  const { items, removeItem, clearCart, drawerOpen, setDrawerOpen } = useCart();
  const [step, setStep] = useState<Step>("cart");
  const [launching, setLaunching] = useState(false);
  const [launchError, setLaunchError] = useState<string | null>(null);

  // Reset step when drawer closes
  useEffect(() => {
    if (!drawerOpen) {
      setStep("cart");
      setLaunchError(null);
    }
  }, [drawerOpen]);

  const handleLaunch = useCallback(
    async (config: LaunchConfig) => {
      setLaunching(true);
      setLaunchError(null);
      try {
        const result = await api.agentCartLaunch({
          source_agent_ids: config.sourceAgentIds,
          project: config.project,
          initial_prompt: config.userPrompt || undefined,
          jira_key: config.jiraKey || undefined,
          worktree_path: config.worktreeMode === "reuse" ? config.worktreePath || undefined : undefined,
          worktree_branch: config.worktreeMode === "reuse" ? config.worktreeBranch || undefined : undefined,
          model: config.model,
          context_preamble: config.preamble,
        });

        clearCart();
        setDrawerOpen(false);

        console.log(
          `Launched merged agent ${result.id} from ${result.source_agent_count} sources, ` +
          `${result.entity_links_created} entity links created`
        );
      } catch (e) {
        setLaunchError(e instanceof Error ? e.message : String(e));
      } finally {
        setLaunching(false);
      }
    },
    [clearCart, setDrawerOpen],
  );

  return (
    <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
      <SheetContent
        side="right"
        className="w-[480px] sm:max-w-[480px] bg-zinc-950 border-zinc-800 flex flex-col p-0"
        showCloseButton={false}
      >
        {step === "cart" && (
          <>
            <SheetHeader className="p-4">
              <div className="flex items-center justify-between">
                <SheetTitle className="text-zinc-100 flex items-center gap-2">
                  <ShoppingCart className="h-4 w-4 text-cyan-400" />
                  Context Cart
                  {items.length > 0 && (
                    <Badge className="text-[10px] px-1.5 py-0 bg-cyan-500/20 text-cyan-300 border-cyan-600/30">
                      {items.length}
                    </Badge>
                  )}
                </SheetTitle>
                <button
                  onClick={() => setDrawerOpen(false)}
                  className="p-1 rounded hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <SheetDescription className="text-zinc-500">
                Collect agent chats to merge into a new session
              </SheetDescription>
            </SheetHeader>

            {/* Cart items */}
            <div className="flex-1 overflow-y-auto px-4 space-y-2">
              {items.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center py-12">
                  <ShoppingCart className="h-10 w-10 text-zinc-700 mb-3" />
                  <p className="text-sm text-zinc-500 mb-1">Cart is empty</p>
                  <p className="text-xs text-zinc-600 max-w-[250px]">
                    Add agents from the agents list, chat view, or AMV using the
                    cart button
                  </p>
                </div>
              ) : (
                items.map((item) => (
                  <CartItemCard
                    key={item.agentId}
                    item={item}
                    onRemove={removeItem}
                  />
                ))
              )}
            </div>

            {/* Footer */}
            {items.length > 0 && (
              <SheetFooter className="border-t border-zinc-800 p-4">
                <div className="flex items-center gap-2 w-full">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs text-zinc-500 hover:text-red-400"
                    onClick={clearCart}
                  >
                    <Trash2 className="h-3 w-3 mr-1" />
                    Clear
                  </Button>
                  <div className="flex-1" />
                  <Button
                    size="sm"
                    className="text-xs bg-cyan-600 hover:bg-cyan-700 text-white"
                    disabled={items.length < 2}
                    onClick={() => setStep("configure")}
                    title={
                      items.length < 2
                        ? "Add at least 2 agents to merge"
                        : "Configure and launch merged agent"
                    }
                  >
                    <Rocket className="h-3 w-3 mr-1" />
                    Configure Launch...
                  </Button>
                </div>
              </SheetFooter>
            )}
          </>
        )}

        {step === "configure" && (
          <>
            {launching ? (
              <div className="flex-1 flex flex-col items-center justify-center gap-3">
                <Loader2 className="h-6 w-6 text-cyan-400 animate-spin" />
                <p className="text-sm text-zinc-400">Launching merged agent...</p>
              </div>
            ) : launchError ? (
              <div className="flex-1 flex flex-col items-center justify-center gap-3 px-4">
                <AlertTriangle className="h-6 w-6 text-red-400" />
                <p className="text-sm text-red-400 text-center">{launchError}</p>
                <Button variant="ghost" size="sm" onClick={() => setLaunchError(null)}>
                  Try Again
                </Button>
              </div>
            ) : (
              <ConfigureStep items={items} onBack={() => setStep("cart")} onLaunch={handleLaunch} />
            )}
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
