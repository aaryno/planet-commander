"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Loader2,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  FileCode,
  MessageSquare,
  GitBranch,
  Plus,
  CircleDot,
} from "lucide-react";
import { api } from "@/lib/api";
import type { DetailedMR, JiraTicketResult, MRPipelinesResponse, PipelineStage, PipelineJob } from "@/lib/api";
import { MRStatusBadge } from "@/components/shared/MRStatusBadge";
import { BranchBadge } from "@/components/shared/BranchBadge";
import { CIStatusLink } from "@/components/shared/CIStatusLink";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { parseJiraMarkup } from "@/lib/jira-formatting";
import { jiraUrl, gitlabMrUrl } from "@/lib/urls";

interface MRCenterPaneProps {
  mr: DetailedMR | null;
  jiraKey: string | null;
  selectedTab: "diff" | "comments" | "pipeline";
  onTabChange: (tab: "diff" | "comments" | "pipeline") => void;
  onFileSelect: (file: string | null) => void;
  onNavigate: (direction: 1 | -1) => void;
  onAddToReview?: (context: string) => void;
}

/** Map short project key to GitLab project path */
function getGitlabProjectPath(project: string): string {
  const PROJECT_PATHS: Record<string, string> = {
    wx: "wx/wx",
    jobs: "wx/wx",
    g4: "product/g4",
    temporal: "temporal/temporalio-cloud",
  };
  return PROJECT_PATHS[project] || project;
}

function formatAge(hours: number): string {
  if (hours < 1) return "< 1h";
  if (hours < 24) return `${Math.round(hours)}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

// ─── JIRA Context Card ───────────────────────────────────────────────

function JiraContextCard({ jiraKey }: { jiraKey: string }) {
  const [ticket, setTicket] = useState<JiraTicketResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [descExpanded, setDescExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setTicket(null);

    api
      .jiraTicket(jiraKey)
      .then((t) => {
        if (!cancelled) setTicket(t);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load ticket");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [jiraKey]);

  if (loading) {
    return (
      <div className="border border-zinc-800 rounded-lg p-3">
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <Loader2 className="h-3 w-3 animate-spin" />
          Loading {jiraKey}...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border border-zinc-800 rounded-lg p-3">
        <div className="text-xs text-red-400">Failed to load {jiraKey}: {error}</div>
      </div>
    );
  }

  if (!ticket) return null;

  const descLines = (ticket.description || "").split("\n");
  const maxLines = 5;
  const hasMore = descLines.length > maxLines;
  const displayDesc = descExpanded
    ? ticket.description || ""
    : descLines.slice(0, maxLines).join("\n");

  const statusColors: Record<string, string> = {
    "To Do": "bg-zinc-600/20 text-zinc-400",
    "In Progress": "bg-blue-500/20 text-blue-400",
    "In Review": "bg-amber-500/20 text-amber-400",
    Done: "bg-emerald-500/20 text-emerald-400",
    Closed: "bg-emerald-500/20 text-emerald-400",
    Backlog: "bg-zinc-600/20 text-zinc-500",
    Selected: "bg-blue-500/10 text-blue-300",
  };

  const statusClass = statusColors[ticket.status] || "bg-zinc-600/20 text-zinc-400";

  return (
    <div className="border border-zinc-800 rounded-lg">
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-between w-full px-3 py-2 text-xs hover:bg-zinc-800/40 transition-colors rounded-t-lg"
      >
        <div className="flex items-center gap-2">
          <span className="text-zinc-500 font-medium">JIRA</span>
          <a
            href={jiraUrl(jiraKey)}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="font-mono text-cyan-400 hover:text-cyan-300"
          >
            {jiraKey}
          </a>
          <Badge className={`text-[10px] px-1.5 py-0 ${statusClass} border-0`}>
            {ticket.status}
          </Badge>
        </div>
        {collapsed ? (
          <ChevronDown className="h-3 w-3 text-zinc-500" />
        ) : (
          <ChevronUp className="h-3 w-3 text-zinc-500" />
        )}
      </button>

      {/* Body */}
      {!collapsed && (
        <div className="px-3 pb-3 space-y-2 text-xs">
          {/* Summary */}
          <p className="text-zinc-200 text-sm leading-snug">{ticket.summary}</p>

          {/* Metadata row */}
          <div className="flex items-center gap-4 text-zinc-500">
            <span>
              Assignee:{" "}
              <span className="text-zinc-300">{ticket.assignee || "Unassigned"}</span>
            </span>
            {ticket.priority && (
              <span>
                Priority: <span className="text-zinc-300">{ticket.priority}</span>
              </span>
            )}
          </div>

          {/* Description */}
          {ticket.description && (
            <div>
              <div
                className={`text-zinc-400 leading-relaxed ${
                  !descExpanded && hasMore ? "max-h-[7rem] overflow-hidden relative" : ""
                }`}
              >
                {parseJiraMarkup(displayDesc)}
                {!descExpanded && hasMore && (
                  <div className="absolute bottom-0 left-0 right-0 h-6 bg-gradient-to-t from-zinc-900 to-transparent" />
                )}
              </div>
              {hasMore && (
                <button
                  onClick={() => setDescExpanded(!descExpanded)}
                  className="text-blue-400 hover:text-blue-300 text-[10px] mt-1 transition-colors"
                >
                  {descExpanded ? "show less" : `show more (${descLines.length} lines)`}
                </button>
              )}
            </div>
          )}

          {/* External link */}
          <a
            href={jiraUrl(jiraKey)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            Open in JIRA <ExternalLink className="h-2.5 w-2.5" />
          </a>
        </div>
      )}
    </div>
  );
}

// ─── Tab Content Components ──────────────────────────────────────────

function DiffTab({
  mr,
  mrUrl,
  onFileSelect,
}: {
  mr: DetailedMR;
  mrUrl: string;
  onFileSelect: (file: string | null) => void;
}) {
  const [detail, setDetail] = useState<DetailedMR | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    api
      .mrDetails(mr.project, mr.iid)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch(() => {
        // Use existing mr data as fallback
        if (!cancelled) setDetail(mr);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [mr.project, mr.iid]);

  const desc = detail?.description || mr.description || "";

  return (
    <div className="space-y-4 text-xs">
      {/* MR Description */}
      {desc && (
        <div className="space-y-1">
          <h4 className="text-zinc-500 font-medium text-[10px] uppercase tracking-wide">
            Description
          </h4>
          <div className="text-zinc-400 leading-relaxed bg-zinc-800/30 rounded-lg p-3 max-h-[20rem] overflow-y-auto">
            {desc.split("\n").map((line, i) => (
              <p key={i} className={line.trim() === "" ? "h-2" : "my-0.5"}>
                {line}
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Link to full diff */}
      <div className="flex items-center gap-3">
        <a
          href={`${mrUrl}/diffs`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors"
        >
          <FileCode className="h-3.5 w-3.5" />
          View full diff on GitLab
          <ExternalLink className="h-2.5 w-2.5" />
        </a>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-zinc-500">
          <Loader2 className="h-3 w-3 animate-spin" />
          Loading details...
        </div>
      )}

      {/* Labels */}
      {(detail?.labels ?? mr.labels)?.length ? (
        <div className="space-y-1">
          <h4 className="text-zinc-500 font-medium text-[10px] uppercase tracking-wide">
            Labels
          </h4>
          <div className="flex flex-wrap gap-1">
            {(detail?.labels ?? mr.labels)!.map((label) => (
              <Badge
                key={label}
                variant="outline"
                className="text-zinc-400 border-zinc-700 bg-zinc-800/50 text-[10px] px-1.5 py-0"
              >
                {label}
              </Badge>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function CommentsTab({
  mr,
  mrUrl,
  jiraKey,
}: {
  mr: DetailedMR;
  mrUrl: string;
  jiraKey: string | null;
}) {
  const [ticket, setTicket] = useState<JiraTicketResult | null>(null);

  useEffect(() => {
    if (!jiraKey) return;
    let cancelled = false;

    api
      .jiraTicket(jiraKey)
      .then((t) => {
        if (!cancelled) setTicket(t);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [jiraKey]);

  const comments = ticket?.comments ?? [];

  return (
    <div className="space-y-4 text-xs">
      {/* GitLab comments link */}
      <div>
        <a
          href={`${mrUrl}#note_`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-blue-400 hover:text-blue-300 transition-colors"
        >
          <MessageSquare className="h-3.5 w-3.5" />
          View comments on GitLab
          <ExternalLink className="h-2.5 w-2.5" />
        </a>
      </div>

      {/* JIRA comments */}
      {jiraKey && comments.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-zinc-500 font-medium text-[10px] uppercase tracking-wide">
            JIRA Comments ({comments.length})
          </h4>
          <div className="space-y-2 max-h-[30rem] overflow-y-auto">
            {comments.map((comment) => (
              <div
                key={comment.id}
                className="bg-zinc-800/30 rounded-lg p-2.5 space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="text-zinc-300 font-medium">{comment.author}</span>
                  <span className="text-zinc-600 text-[10px]">
                    {new Date(comment.created).toLocaleDateString()}
                  </span>
                </div>
                <div className="text-zinc-400 leading-relaxed">
                  {parseJiraMarkup(comment.body)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {jiraKey && comments.length === 0 && (
        <p className="text-zinc-500 text-center py-4">No JIRA comments found</p>
      )}

      {!jiraKey && (
        <p className="text-zinc-500 text-center py-4">
          No JIRA ticket linked to this MR
        </p>
      )}

      {/* Placeholder for future inline comments */}
      <div className="border border-dashed border-zinc-800 rounded-lg p-3 text-center text-zinc-600">
        Inline review comments coming soon
      </div>
    </div>
  );
}

// ─── Pipeline Helpers ────────────────────────────────────────────────

const JOB_STATUS_CONFIG: Record<string, { icon: string; color: string; bg: string }> = {
  success: { icon: "✅", color: "text-emerald-400", bg: "bg-emerald-500/10" },
  failed: { icon: "❌", color: "text-red-400", bg: "bg-red-500/10" },
  running: { icon: "⏳", color: "text-amber-400", bg: "bg-amber-500/10" },
  pending: { icon: "⏸", color: "text-zinc-500", bg: "bg-zinc-500/10" },
  created: { icon: "○", color: "text-zinc-600", bg: "bg-zinc-500/5" },
  manual: { icon: "▶", color: "text-blue-400", bg: "bg-blue-500/10" },
  canceled: { icon: "⊘", color: "text-zinc-500", bg: "bg-zinc-500/10" },
  skipped: { icon: "⊘", color: "text-zinc-600", bg: "bg-zinc-500/5" },
};

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "–";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

function JobRow({ job, mrUrl, onAddToReview }: { job: PipelineJob; mrUrl: string; onAddToReview?: (ctx: string) => void }) {
  const cfg = JOB_STATUS_CONFIG[job.status] || JOB_STATUS_CONFIG.pending;

  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded ${cfg.bg} group`}>
      <span className="w-4 text-center shrink-0">{cfg.icon}</span>
      <a
        href={job.web_url}
        target="_blank"
        rel="noopener noreferrer"
        className={`flex-1 truncate hover:underline ${cfg.color}`}
      >
        {job.name}
      </a>
      {job.allow_failure && (
        <span className="text-[10px] text-zinc-600 shrink-0">allow fail</span>
      )}
      {job.failure_reason && (
        <span className="text-[10px] text-red-400/70 truncate max-w-[120px] shrink-0" title={job.failure_reason}>
          {job.failure_reason}
        </span>
      )}
      <span className="text-zinc-600 text-[10px] w-14 text-right shrink-0">{formatDuration(job.duration)}</span>
      {onAddToReview && (
        <button
          onClick={() => onAddToReview(`Review pipeline job "${job.name}" (${job.status}): ${job.web_url}`)}
          className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-zinc-700"
          title="Add to review"
        >
          <Plus className="h-3 w-3 text-zinc-400" />
        </button>
      )}
    </div>
  );
}

function StageSection({ stage, mrUrl, onAddToReview }: { stage: PipelineStage; mrUrl: string; onAddToReview?: (ctx: string) => void }) {
  const [expanded, setExpanded] = useState(
    stage.status === "failed" || stage.status === "running"
  );
  const cfg = JOB_STATUS_CONFIG[stage.status] || JOB_STATUS_CONFIG.pending;
  const counts = {
    total: stage.jobs.length,
    passed: stage.jobs.filter(j => j.status === "success").length,
    failed: stage.jobs.filter(j => j.status === "failed").length,
    skipped: stage.jobs.filter(j => j.status === "skipped").length,
  };

  return (
    <div className="border border-zinc-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full px-3 py-2 hover:bg-zinc-800/40 transition-colors text-left"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3 text-zinc-500 shrink-0" />
        ) : (
          <ChevronRight className="h-3 w-3 text-zinc-500 shrink-0" />
        )}
        <span className="w-4 text-center shrink-0">{cfg.icon}</span>
        <span className="font-medium text-zinc-300 flex-1">{stage.name}</span>
        <span className="text-[10px] text-zinc-500">
          {counts.passed}/{counts.total} passed
          {counts.failed > 0 && <span className="text-red-400 ml-1">{counts.failed} failed</span>}
          {counts.skipped > 0 && <span className="text-zinc-600 ml-1">{counts.skipped} skipped</span>}
        </span>
      </button>
      {expanded && (
        <div className="border-t border-zinc-800 py-1 space-y-0.5">
          {stage.jobs.map((job) => (
            <JobRow key={job.id} job={job} mrUrl={mrUrl} onAddToReview={onAddToReview} />
          ))}
        </div>
      )}
    </div>
  );
}

function PipelineTab({ mr, mrUrl, onAddToReview }: { mr: DetailedMR; mrUrl: string; onAddToReview?: (ctx: string) => void }) {
  const [data, setData] = useState<MRPipelinesResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    api
      .mrPipelines(mr.project, mr.iid)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [mr.project, mr.iid]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-zinc-500 text-xs">
        <Loader2 className="h-3 w-3 animate-spin" />
        Loading pipelines...
      </div>
    );
  }

  if (!data || data.pipelines.length === 0) {
    return (
      <div className="space-y-3 text-xs">
        <p className="text-zinc-500">No pipelines found for this MR.</p>
        <a
          href={`${mrUrl}/pipelines`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-blue-400 hover:text-blue-300 transition-colors"
        >
          View pipelines on GitLab
          <ExternalLink className="h-2.5 w-2.5" />
        </a>
      </div>
    );
  }

  const active = data.active_pipeline;
  const olderPipelines = data.pipelines.slice(1);

  return (
    <div className="space-y-4 text-xs">
      {/* Active Pipeline */}
      {active && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CircleDot className="h-3.5 w-3.5 text-blue-400" />
              <span className="font-medium text-zinc-200">Active Pipeline</span>
              <CIStatusLink status={active.status as any} pipelineUrl={active.web_url} label />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-zinc-600 font-mono">{active.sha}</span>
              {onAddToReview && (
                <button
                  onClick={() => onAddToReview(`Review the CI pipeline for MR !${mr.iid} "${mr.title}": ${active.web_url}`)}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors"
                  title="Add pipeline to review"
                >
                  <Plus className="h-3 w-3" />
                  Add to review
                </button>
              )}
            </div>
          </div>

          {/* Stages */}
          {active.stages && active.stages.length > 0 ? (
            <div className="space-y-1.5">
              {active.stages.map((stage) => (
                <StageSection key={stage.name} stage={stage} mrUrl={mrUrl} onAddToReview={onAddToReview} />
              ))}
            </div>
          ) : (
            <p className="text-zinc-500 pl-6">No stage details available.</p>
          )}

          <a
            href={active.web_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-blue-400 hover:text-blue-300 transition-colors"
          >
            View pipeline on GitLab
            <ExternalLink className="h-2.5 w-2.5" />
          </a>
        </div>
      )}

      {/* Older Pipelines */}
      {olderPipelines.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-zinc-500 font-medium text-[10px] uppercase tracking-wide">
            Previous Pipelines ({olderPipelines.length})
          </h4>
          <div className="space-y-1">
            {olderPipelines.map((p) => (
              <div key={p.id} className="flex items-center gap-3 px-2 py-1.5 rounded hover:bg-zinc-800/40">
                <CIStatusLink status={p.status as any} pipelineUrl={p.web_url} label />
                <span className="text-zinc-600 font-mono text-[10px]">{p.sha}</span>
                <span className="text-zinc-600 text-[10px]">{p.source}</span>
                <span className="flex-1" />
                <a
                  href={p.web_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-zinc-600 hover:text-zinc-400 transition-colors"
                >
                  <ExternalLink className="h-2.5 w-2.5" />
                </a>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────

export function MRCenterPane({
  mr,
  jiraKey,
  selectedTab,
  onTabChange,
  onFileSelect,
  onNavigate,
  onAddToReview,
}: MRCenterPaneProps) {
  // Empty state
  if (!mr) {
    return (
      <div className="flex items-center justify-center h-full text-zinc-500 text-sm">
        Select an MR from the list to start reviewing
      </div>
    );
  }

  const gitlabPath = getGitlabProjectPath(mr.project);
  const mrUrl =
    mr.url || gitlabMrUrl(gitlabPath, mr.iid);
  const approved = mr.reviews && mr.reviews.length > 0;

  const tabs: Array<{ key: "diff" | "comments" | "pipeline"; label: string }> = [
    { key: "diff", label: "Diff" },
    { key: "comments", label: "Comments" },
    { key: "pipeline", label: "Pipeline" },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* ─── Sticky Header Strip ─── */}
      <div className="sticky top-0 z-10 bg-zinc-900/95 backdrop-blur-sm border-b border-zinc-800 px-4 py-3 space-y-2 shrink-0">
        {/* Row 1: Title + navigation */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono text-zinc-400 text-sm shrink-0">!{mr.iid}</span>
              <h2 className="text-sm font-medium text-zinc-200 truncate">{mr.title}</h2>
            </div>
            <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
              <span>{mr.author}</span>
              <span>{formatAge(mr.age_created_hours)} ago</span>
              {mr.is_draft && (
                <Badge className="text-[10px] px-1.5 py-0 bg-amber-500/20 text-amber-400 border-0">
                  Draft
                </Badge>
              )}
            </div>
          </div>

          {/* Nav + external link */}
          <div className="flex items-center gap-1 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 text-zinc-500 hover:text-zinc-300"
              onClick={() => onNavigate(-1)}
              title="Previous MR (k)"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 text-zinc-500 hover:text-zinc-300"
              onClick={() => onNavigate(1)}
              title="Next MR (j)"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <a
              href={mrUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center h-7 w-7 text-zinc-500 hover:text-zinc-300 transition-colors"
              title="Open in GitLab"
            >
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </div>
        </div>

        {/* Row 2: Branch + CI + review status */}
        <div className="flex items-center gap-4 flex-wrap text-xs">
          <BranchBadge
            branch={mr.branch}
            targetBranch={mr.target_branch}
            project={gitlabPath}
            compact
          />

          {mr.state && (
            <MRStatusBadge
              iid={mr.iid}
              status={(mr.state as "opened" | "closed" | "merged") || "opened"}
              url={mrUrl}
              approved={!!approved}
              compact
            />
          )}

          {mr.needs_review && (
            <Badge className="text-[10px] px-1.5 py-0 bg-amber-500/20 text-amber-400 border-0">
              Needs Review
            </Badge>
          )}

          {approved && (
            <Badge className="text-[10px] px-1.5 py-0 bg-emerald-500/20 text-emerald-400 border-0">
              Approved
            </Badge>
          )}
        </div>
      </div>

      {/* ─── Scrollable Content ─── */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {/* JIRA Context Card */}
        {jiraKey && <JiraContextCard jiraKey={jiraKey} />}

        {/* Review Tabs */}
        <div className="border-b border-zinc-800">
          <div className="flex gap-0">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => onTabChange(tab.key)}
                className={`px-4 py-2 text-xs font-medium transition-colors relative ${
                  selectedTab === tab.key
                    ? "text-zinc-200"
                    : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {tab.label}
                {selectedTab === tab.key && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500 rounded-full" />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Tab Content */}
        <div className="pt-1">
          {selectedTab === "diff" && (
            <DiffTab mr={mr} mrUrl={mrUrl} onFileSelect={onFileSelect} />
          )}
          {selectedTab === "comments" && (
            <CommentsTab mr={mr} mrUrl={mrUrl} jiraKey={jiraKey} />
          )}
          {selectedTab === "pipeline" && <PipelineTab mr={mr} mrUrl={mrUrl} onAddToReview={onAddToReview} />}
        </div>
      </div>
    </div>
  );
}
