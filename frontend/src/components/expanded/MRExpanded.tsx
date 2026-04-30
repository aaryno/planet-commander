"use client";

import { useState, useEffect } from "react";
import { Loader2, Bot } from "lucide-react";
import Link from "next/link";
import { api, Agent } from "@/lib/api";
import { MRStatusBadge } from "@/components/shared/MRStatusBadge";
import { BranchBadge } from "@/components/shared/BranchBadge";
import { CIStatusLink } from "@/components/shared/CIStatusLink";
import { CommentIndicator } from "@/components/shared/CommentIndicator";
import { AgentBadge } from "@/components/shared/AgentBadge";
import { ExternalLinks } from "@/components/shared/ExternalLinks";
import { Badge } from "@/components/ui/badge";
import { extractJiraKey } from "@/lib/utils";
import { jiraUrl, gitlabMrUrl } from "@/lib/urls";

interface MRExpandedProps {
  project: string;
  iid: number;
  title: string;
  onOpenAgent?: (agentId: string) => void;
}

interface MRDetail {
  status: string;
  is_draft: boolean;
  branch: string;
  target_branch?: string;
  url: string;
  pipeline_status?: string;
  pipeline_web_url?: string;
  has_conflicts?: boolean;
  user_notes_count?: number;
  upvotes?: number;
  description?: string;
}

export function MRExpanded({ project, iid, title, onOpenAgent }: MRExpandedProps) {
  const [mrDetail, setMrDetail] = useState<MRDetail | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const jiraKey = extractJiraKey(title, mrDetail?.branch);

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      setLoading(true);
      setError(null);

      try {
        // Fetch MR details
        const detail = await api.mrDetails(project, iid);
        if (cancelled) return;

        setMrDetail({
          status: detail.state || "opened",
          is_draft: detail.is_draft,
          branch: detail.branch,
          target_branch: detail.target_branch,
          url: detail.url,
          pipeline_status: (detail as any).pipeline_status,
          pipeline_web_url: (detail as any).pipeline_web_url,
          has_conflicts: (detail as any).has_conflicts,
          user_notes_count: (detail as any).user_notes_count,
          upvotes: (detail as any).upvotes,
          description: detail.description,
        });

        // Fetch linked agents if JIRA key found
        if (jiraKey) {
          try {
            const agentResult = await api.agentsByJira(jiraKey);
            if (!cancelled) {
              setAgents(agentResult.agents || []);
            }
          } catch {
            // Non-critical: agents lookup can fail silently
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load MR details");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchData();
    return () => { cancelled = true; };
  }, [project, iid, jiraKey]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-3 text-xs text-zinc-500">
        <Loader2 className="h-3 w-3 animate-spin" />
        Loading MR details...
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-3 text-xs text-red-400">
        {error}
      </div>
    );
  }

  if (!mrDetail) return null;

  const gitlabProjectPath = getGitlabProjectPath(project);
  const mrUrl = mrDetail.url || gitlabMrUrl(gitlabProjectPath, iid);

  const externalLinks = [
    { label: "GitLab", url: mrUrl },
    { label: "Diff", url: `${mrUrl}/diffs` },
  ];

  if (mrDetail.pipeline_web_url) {
    externalLinks.push({ label: "Pipeline", url: mrDetail.pipeline_web_url });
  }

  const approved = (mrDetail.upvotes ?? 0) > 0;

  return (
    <div className="space-y-3 text-xs">
      {/* Status row */}
      <div className="flex items-center gap-4 flex-wrap">
        <span className="text-zinc-500">Status:</span>
        <MRStatusBadge
          iid={iid}
          status={mrDetail.status as "opened" | "closed" | "merged"}
          pipelineStatus={mrDetail.pipeline_status as any}
          pipelineUrl={mrDetail.pipeline_web_url}
          hasConflicts={mrDetail.has_conflicts}
          approved={approved}
          url={mrUrl}
        />
        {mrDetail.is_draft && (
          <span className="text-zinc-500">Draft: <span className="text-amber-400">yes</span></span>
        )}
      </div>

      {/* Branch row */}
      <div className="flex items-center gap-4">
        <span className="text-zinc-500">Branch:</span>
        <BranchBadge
          branch={mrDetail.branch}
          targetBranch={mrDetail.target_branch}
          project={gitlabProjectPath}
        />
      </div>

      {/* CI row */}
      {mrDetail.pipeline_status && (
        <div className="flex items-center gap-4">
          <span className="text-zinc-500">CI:</span>
          <CIStatusLink
            status={mrDetail.pipeline_status as any}
            pipelineUrl={mrDetail.pipeline_web_url}
            label
          />
        </div>
      )}

      {/* Comments row */}
      <div className="flex items-center gap-4">
        <span className="text-zinc-500">Comments:</span>
        <CommentIndicator count={mrDetail.user_notes_count ?? 0} />
      </div>

      {/* Rebase row */}
      {mrDetail.has_conflicts && (
        <div className="flex items-center gap-4">
          <span className="text-zinc-500">Rebase:</span>
          <span className="text-amber-400">needed</span>
        </div>
      )}

      {/* JIRA + Agent section */}
      {(jiraKey || agents.length > 0) && (
        <div className="border-t border-zinc-800/60 pt-2 space-y-2">
          {jiraKey && (
            <div className="flex items-center gap-4">
              <span className="text-zinc-500">JIRA:</span>
              <Badge
                variant="outline"
                className="text-cyan-400 border-cyan-600/50 bg-cyan-500/10 text-[10px] px-1.5 py-0.5 font-mono hover:bg-cyan-500/20 transition-colors"
              >
                <a
                  href={jiraUrl(jiraKey!)}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="hover:text-cyan-300"
                >
                  {jiraKey}
                </a>
              </Badge>
            </div>
          )}

          {agents.map((agent) => (
            <div key={agent.id} className="flex items-center gap-4">
              <span className="text-zinc-500">Agent:</span>
              <AgentBadge
                id={agent.id}
                title={agent.title}
                status={agent.status}
                lastActivity={agent.last_active_at}
                messageCount={agent.num_prompts}
                onClick={() => onOpenAgent?.(agent.id)}
              />
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="border-t border-zinc-800/60 pt-2 flex items-center gap-3">
        <Link
          href={`/review?mr=${project}-${iid}`}
          onClick={(e) => e.stopPropagation()}
          className="inline-flex items-center gap-1.5 text-[11px] font-medium text-cyan-400 hover:text-cyan-300 bg-cyan-500/10 hover:bg-cyan-500/15 px-2.5 py-1 rounded-md transition-colors"
        >
          <Bot className="h-3 w-3" />
          Review in Cockpit
        </Link>
        <ExternalLinks links={externalLinks} />
      </div>
    </div>
  );
}

/** Map short project key to GitLab project path */
function getGitlabProjectPath(project: string): string {
  const PROJECT_PATHS: Record<string, string> = {
    wx: "wx/wx",
    jobs: "wx/wx",  // jobs is in the wx repo
    g4: "product/g4",
    temporal: "temporal/temporalio-cloud",
  };
  return PROJECT_PATHS[project] || project;
}
