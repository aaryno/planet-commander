"use client";

import { useState, useEffect, useCallback } from "react";
import { ExternalLink, PanelRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MRStatusBadge } from "@/components/shared/MRStatusBadge";
import { AgentBadge } from "@/components/shared/AgentBadge";
import { CommentIndicator } from "@/components/shared/CommentIndicator";
import { ExternalLinks } from "@/components/shared/ExternalLinks";
import { parseJiraMarkup } from "@/lib/jira-formatting";
import { api } from "@/lib/api";
import type { Agent } from "@/lib/api";

interface JiraTicketExpandedProps {
  jiraKey: string;
  onOpenAgent?: (agentId: string) => void;
  onOpenInSidebar?: (jiraKey: string) => void;
}

export function JiraTicketExpanded({ jiraKey, onOpenAgent, onOpenInSidebar }: JiraTicketExpandedProps) {
  const [ticket, setTicket] = useState<any>(null);
  const [linkedMRs, setLinkedMRs] = useState<any[]>([]);
  const [linkedAgents, setLinkedAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [descriptionExpanded, setDescriptionExpanded] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ticketRes, mrsRes, agentsRes] = await Promise.allSettled([
        api.jiraTicket(jiraKey),
        api.gitlabMRByJira(jiraKey).catch(() => ({ mrs: [] })),
        api.agentsByJira(jiraKey).catch(() => ({ agents: [] })),
      ]);

      if (ticketRes.status === "fulfilled") setTicket(ticketRes.value);
      if (mrsRes.status === "fulfilled") setLinkedMRs((mrsRes.value as any).mrs || []);
      if (agentsRes.status === "fulfilled") setLinkedAgents((agentsRes.value as any).agents || []);
      if (ticketRes.status === "rejected") setError("Failed to load ticket details");
    } catch {
      setError("Failed to load details");
    } finally {
      setLoading(false);
    }
  }, [jiraKey]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) {
    return (
      <div className="space-y-3 animate-pulse">
        <div className="h-3 bg-zinc-800 rounded w-3/4" />
        <div className="h-3 bg-zinc-800 rounded w-1/2" />
        <div className="flex gap-4">
          <div className="h-3 bg-zinc-800 rounded w-20" />
          <div className="h-3 bg-zinc-800 rounded w-20" />
        </div>
      </div>
    );
  }

  if (error && !ticket) return <p className="text-xs text-red-400">{error}</p>;
  if (!ticket) return null;

  // Description: truncate to ~8 lines for collapsed view
  const descriptionText = ticket.description || "";
  const descriptionLines = descriptionText.split("\n");
  const maxLines = 8;
  const hasMoreDescription = descriptionLines.length > maxLines;
  const displayedDescription = descriptionExpanded
    ? descriptionText
    : descriptionLines.slice(0, maxLines).join("\n");

  const commentCount = ticket.comments?.length ?? 0;
  const lastComment = ticket.comments?.length
    ? ticket.comments[ticket.comments.length - 1]
    : null;

  const externalLinks: Array<{ label: string; url: string }> = [
    { label: "JIRA", url: `https://hello.planet.com/jira/browse/${jiraKey}` },
  ];
  if (ticket.epic_key) {
    externalLinks.push({ label: "Epic", url: `https://hello.planet.com/jira/browse/${ticket.epic_key}` });
  }

  return (
    <div className="space-y-3 text-xs">
      {/* Action buttons — top of expanded card */}
      <div className="flex items-center gap-2">
        {onOpenInSidebar && (
          <Button
            variant="outline"
            size="sm"
            className="h-6 text-[10px] px-2 border-zinc-700 text-blue-400 hover:text-blue-300 hover:bg-blue-500/10"
            onClick={(e) => { e.stopPropagation(); onOpenInSidebar(jiraKey); }}
          >
            <PanelRight className="h-3 w-3 mr-1" />
            Open in Sidebar
          </Button>
        )}
        <a
          href={`https://hello.planet.com/jira/browse/${jiraKey}`}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="inline-flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          Open in JIRA <ExternalLink className="h-2.5 w-2.5" />
        </a>
      </div>

      {/* Description — rendered with JIRA markup parser */}
      {descriptionText && (
        <div>
          <div className={`text-zinc-400 leading-relaxed ${!descriptionExpanded ? "max-h-[12rem] overflow-hidden relative" : ""}`}>
            {parseJiraMarkup(displayedDescription)}
            {!descriptionExpanded && hasMoreDescription && (
              <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-zinc-900 to-transparent" />
            )}
          </div>
          {hasMoreDescription && (
            <button
              onClick={(e) => { e.stopPropagation(); setDescriptionExpanded(!descriptionExpanded); }}
              className="text-blue-400 hover:text-blue-300 text-[10px] mt-1 transition-colors"
            >
              {descriptionExpanded ? "show less" : `show more (${descriptionLines.length} lines)`}
            </button>
          )}
        </div>
      )}

      {/* Metadata grid */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
        {ticket.labels && ticket.labels.length > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="text-zinc-600 w-16 shrink-0">Labels</span>
            <div className="flex flex-wrap gap-1">
              {ticket.labels.map((label: string) => (
                <Badge key={label} variant="outline" className="text-zinc-400 border-zinc-700 bg-zinc-800/50 text-[10px] px-1.5 py-0">
                  {label}
                </Badge>
              ))}
            </div>
          </div>
        )}
        {ticket.story_points != null && (
          <div className="flex items-center gap-1.5">
            <span className="text-zinc-600 w-16 shrink-0">Points</span>
            <span className="text-zinc-300 font-medium">{ticket.story_points}</span>
          </div>
        )}
        <div className="flex items-center gap-1.5">
          <span className="text-zinc-600 w-16 shrink-0">Assignee</span>
          <span className="text-zinc-300">{ticket.assignee || "Unassigned"}</span>
        </div>
        {ticket.type && (
          <div className="flex items-center gap-1.5">
            <span className="text-zinc-600 w-16 shrink-0">Type</span>
            <span className="text-zinc-400">{ticket.type}</span>
          </div>
        )}
        {ticket.priority && (
          <div className="flex items-center gap-1.5">
            <span className="text-zinc-600 w-16 shrink-0">Priority</span>
            <span className="text-zinc-400">{ticket.priority}</span>
          </div>
        )}
        {ticket.sprint && (
          <div className="flex items-center gap-1.5">
            <span className="text-zinc-600 w-16 shrink-0">Sprint</span>
            <span className="text-zinc-400">{ticket.sprint}</span>
          </div>
        )}
        {ticket.fix_versions && ticket.fix_versions.length > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="text-zinc-600 w-16 shrink-0">Fix Ver</span>
            <span className="text-zinc-400">{ticket.fix_versions.join(", ")}</span>
          </div>
        )}
      </div>

      {/* Activity */}
      <CommentIndicator
        count={commentCount}
        lastActivityAt={lastComment?.updated || lastComment?.created}
      />

      {/* Linked MRs */}
      {linkedMRs.length > 0 && (
        <div className="space-y-1.5">
          <h4 className="text-zinc-500 font-medium text-[10px] uppercase tracking-wide">Linked MRs</h4>
          <div className="space-y-1">
            {linkedMRs.map((mr: any) => (
              <div key={mr.id || mr.iid} className="flex items-center gap-2">
                <MRStatusBadge
                  iid={mr.external_mr_id || mr.iid}
                  status={(mr.state || "opened") as "opened" | "closed" | "merged"}
                  pipelineStatus={mr.ci_status || mr.pipeline_status}
                  approved={mr.is_approved}
                  url={mr.url || mr.web_url}
                  compact
                />
                <span className="text-zinc-400 truncate flex-1" title={mr.title}>{mr.title}</span>
                <span className="text-zinc-600 shrink-0">{mr.author}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Linked Agents */}
      {linkedAgents.length > 0 && (
        <div className="space-y-1.5">
          <h4 className="text-zinc-500 font-medium text-[10px] uppercase tracking-wide">Agents</h4>
          <div className="space-y-1">
            {linkedAgents.map((agent) => (
              <AgentBadge
                key={agent.id}
                id={agent.id}
                title={agent.title}
                status={agent.status}
                lastActivity={agent.last_active_at}
                messageCount={agent.num_prompts}
                onClick={() => onOpenAgent?.(agent.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* External Links */}
      <ExternalLinks links={externalLinks} />
    </div>
  );
}
