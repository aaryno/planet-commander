"use client";

import { useEffect, useState } from "react";
import { MessageSquare, Zap, FolderOpen, Clock, Hash, LayoutGrid } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MRStatusBadge } from "@/components/shared/MRStatusBadge";
import { BranchBadge } from "@/components/shared/BranchBadge";
import { ExternalLinks } from "@/components/shared/ExternalLinks";
import { formatTimestampAgo } from "@/lib/time-utils";
import type { Agent, DetailedMR } from "@/lib/api";
import { addAgentToAMV } from "@/lib/amv";
import { useToast } from "@/components/ui/toast-simple";

interface AgentExpandedProps {
  agent: Agent;
  onJoinChat?: () => void;
  onSummarize?: () => void;
}

interface LastPrompt {
  content: string | null;
  timestamp: string | null;
  truncated?: boolean;
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return "--";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) +
    " " +
    d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
}

function formatTokens(n: number): string {
  if (n === 0) return "0";
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0)}K`;
  return `${(n / 1_000_000).toFixed(1)}M`;
}

export function AgentExpanded({ agent, onJoinChat, onSummarize }: AgentExpandedProps) {
  const toast = useToast();
  const [lastPrompt, setLastPrompt] = useState<LastPrompt | null>(null);
  const [promptLoading, setPromptLoading] = useState(true);
  const [linkedMRs, setLinkedMRs] = useState<DetailedMR[]>([]);
  const [mrsLoading, setMrsLoading] = useState(false);
  const [promptExpanded, setPromptExpanded] = useState(false);

  // Fetch last prompt
  useEffect(() => {
    setPromptLoading(true);
    fetch(`/api/agents/${agent.id}/last-prompt`)
      .then((r) => r.json())
      .then((data) => setLastPrompt(data))
      .catch(() => setLastPrompt(null))
      .finally(() => setPromptLoading(false));
  }, [agent.id]);

  // Fetch linked MRs: by JIRA key first, then by branch
  useEffect(() => {
    let cancelled = false;

    async function fetchMRs() {
      setMrsLoading(true);
      try {
        // Try by JIRA key first
        if (agent.jira_key) {
          const res = await fetch(`/api/mrs/by-jira/${encodeURIComponent(agent.jira_key)}`);
          const data = await res.json();
          if (!cancelled && data.mrs?.length > 0) {
            setLinkedMRs(data.mrs);
            setMrsLoading(false);
            return;
          }
        }

        // Fall back to branch search
        if (agent.git_branch) {
          const res = await fetch(`/api/mrs?${new URLSearchParams()}`);
          const data = await res.json();
          if (!cancelled) {
            const branchMRs = (data.mrs || []).filter(
              (mr: DetailedMR) => mr.branch === agent.git_branch
            );
            setLinkedMRs(branchMRs);
          }
        }
      } catch {
        // silently fail
      } finally {
        if (!cancelled) setMrsLoading(false);
      }
    }

    if (agent.jira_key || agent.git_branch) {
      fetchMRs();
    }

    return () => {
      cancelled = true;
    };
  }, [agent.jira_key, agent.git_branch]);

  const workingDir = agent.worktree_path || agent.working_directory;
  const displayDir = workingDir?.replace(/^\/Users\/aaryn\//, "~/") || null;

  const externalLinks = [];
  if (agent.jira_key) {
    externalLinks.push({
      label: agent.jira_key,
      url: `https://hello.planet.com/jira/browse/${agent.jira_key}`,
    });
  }

  return (
    <div className="space-y-3 text-xs">
      {/* Metadata grid */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-zinc-400">
        <div className="flex items-center gap-1.5">
          <Clock className="h-3 w-3 text-zinc-500" />
          <span className="text-zinc-500">Created:</span>
          <span>{formatTimestamp(agent.created_at)}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Clock className="h-3 w-3 text-zinc-500" />
          <span className="text-zinc-500">Last chat:</span>
          <span>{formatTimestamp(agent.last_active_at)}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Hash className="h-3 w-3 text-zinc-500" />
          <span className="text-zinc-500">Prompts:</span>
          <span>{agent.num_prompts}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Zap className="h-3 w-3 text-zinc-500" />
          <span className="text-zinc-500">Context:</span>
          <span>{formatTokens(agent.total_tokens)} tokens</span>
        </div>
        <div className="flex items-center gap-1.5">
          <MessageSquare className="h-3 w-3 text-zinc-500" />
          <span className="text-zinc-500">Managed by:</span>
          <span>{agent.managed_by}</span>
        </div>
        {displayDir && (
          <div className="flex items-center gap-1.5">
            <FolderOpen className="h-3 w-3 text-zinc-500" />
            <span className="text-zinc-500">Working dir:</span>
            <span className="truncate" title={workingDir || undefined}>
              {displayDir}
            </span>
          </div>
        )}
      </div>

      {/* Last prompt */}
      <div className="space-y-1">
        <span className="text-zinc-500 text-[11px] font-medium uppercase tracking-wider">
          Last prompt
        </span>
        {promptLoading ? (
          <div className="text-zinc-600 italic">Loading...</div>
        ) : lastPrompt?.content ? (
          <div
            className="bg-zinc-800/50 rounded px-2.5 py-2 text-zinc-300 leading-relaxed cursor-pointer hover:bg-zinc-800/70 transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              setPromptExpanded(!promptExpanded);
            }}
          >
            <span className="text-zinc-500">&ldquo;</span>
            {promptExpanded
              ? lastPrompt.content
              : lastPrompt.content.length > 150
                ? lastPrompt.content.slice(0, 150) + "..."
                : lastPrompt.content}
            <span className="text-zinc-500">&rdquo;</span>
            {lastPrompt.truncated && !promptExpanded && (
              <span className="text-zinc-600 ml-1">(truncated)</span>
            )}
          </div>
        ) : (
          <div className="text-zinc-600 italic">No prompts found</div>
        )}
      </div>

      {/* JIRA + Branch + MR row */}
      {(agent.jira_key || agent.git_branch || linkedMRs.length > 0) && (
        <div className="space-y-2">
          {agent.jira_key && (
            <div className="flex items-center gap-2">
              <span className="text-zinc-500">JIRA:</span>
              <a
                href={`https://hello.planet.com/jira/browse/${agent.jira_key}`}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
              >
                <Badge
                  variant="outline"
                  className="text-cyan-400 border-cyan-600/50 bg-cyan-500/10 text-[10px] px-1.5 py-0.5 hover:bg-cyan-500/20 transition-colors"
                >
                  {agent.jira_key}
                </Badge>
              </a>
            </div>
          )}

          {agent.git_branch && (
            <div className="flex items-center gap-2">
              <span className="text-zinc-500">Branch:</span>
              <BranchBadge
                branch={agent.git_branch}
                project={agent.project ? `wx/${agent.project}` : undefined}
              />
            </div>
          )}

          {mrsLoading ? (
            <div className="text-zinc-600 italic">Loading MRs...</div>
          ) : (
            linkedMRs.map((mr) => (
              <div key={mr.iid} className="flex items-center gap-2">
                <span className="text-zinc-500">MR:</span>
                <MRStatusBadge
                  iid={mr.iid}
                  status={(mr.state as "opened" | "closed" | "merged") || "opened"}
                  pipelineStatus={undefined}
                  hasConflicts={false}
                  unresolvedCount={0}
                  url={mr.url}
                  project={mr.project}
                />
              </div>
            ))
          )}
        </div>
      )}

      {/* External links */}
      {externalLinks.length > 0 && <ExternalLinks links={externalLinks} />}

      {/* Action buttons */}
      <div className="flex items-center gap-2 pt-1">
        {onJoinChat && (
          <Button
            size="sm"
            className="h-7 text-xs bg-blue-600 hover:bg-blue-500 text-white"
            onClick={(e) => {
              e.stopPropagation();
              onJoinChat();
            }}
          >
            Join Chat
          </Button>
        )}
        {onSummarize && (
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs border-zinc-700 text-zinc-300 hover:bg-zinc-800"
            onClick={(e) => {
              e.stopPropagation();
              onSummarize();
            }}
          >
            Summarize
          </Button>
        )}
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-xs border-zinc-700 text-amber-400 hover:bg-amber-500/10"
          onClick={(e) => {
            e.stopPropagation();
            addAgentToAMV(agent);
            toast.showToast({
              message: "Agent added to Multi-View",
              link: { label: "Go to AMV", href: "/multiview" },
            });
          }}
        >
          <LayoutGrid className="h-3 w-3 mr-1" />
          Add to AMV
        </Button>
      </div>
    </div>
  );
}
