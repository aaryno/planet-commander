"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { JiraTicketEnhanced } from "@/lib/api";
import { Link as LinkIcon } from "lucide-react";
import Link from "next/link";
import { JIRA_STATUS_COLORS, JIRA_PRIORITY_COLORS, getStatusColor } from "@/lib/status-colors";
import { jiraUrl } from "@/lib/urls";

interface JiraTicketCardProps {
  ticket: JiraTicketEnhanced;
  onClick?: (jiraKey: string) => void;
  compact?: boolean;
  showRelationships?: boolean;
}

export function JiraTicketCard({ ticket, onClick, compact = false, showRelationships = true }: JiraTicketCardProps) {
  const statusColor = getStatusColor(JIRA_STATUS_COLORS, ticket.status, "bg-zinc-700 text-zinc-300");
  const priorityColor = getStatusColor(JIRA_PRIORITY_COLORS, ticket.priority, "text-zinc-400");
  const statusDisplay = ticket.status;

  const isMyTicket = ticket.my_relationships.assigned;

  // Get avatar URL (placeholder for now - would come from API)
  const avatarUrl = ticket.assignee_avatar_url;

  return (
    <div
      onClick={() => onClick?.(ticket.key)}
      className={`
        ${compact ? "p-2" : "p-3"}
        rounded-lg
        border
        ${isMyTicket ? "border-emerald-600/40 bg-emerald-950/20" : "border-zinc-800 bg-zinc-900/50"}
        hover:bg-zinc-800/50
        transition-colors
        ${onClick ? "cursor-pointer" : ""}
      `}
    >
      {/* First line: Title (wrapping) + Assignee/Reviewer on far right */}
      <div className="flex items-start gap-2 mb-2">
        <div className={`${compact ? "text-xs" : "text-sm"} text-zinc-300 font-medium flex-1`}>
          {ticket.summary}
        </div>
        <div className="flex items-center gap-2 text-[10px] shrink-0">
          {/* Assignee */}
          <div className="flex items-center gap-1.5">
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt={ticket.assignee}
                className="w-4 h-4 rounded-full"
              />
            ) : ticket.assignee !== "Unassigned" ? (
              <div className="w-4 h-4 rounded-full bg-zinc-700 flex items-center justify-center text-[8px] text-zinc-400">
                {ticket.assignee.charAt(0).toUpperCase()}
              </div>
            ) : null}
            <span className={`text-zinc-500 ${isMyTicket ? "text-emerald-400" : ""}`}>
              {ticket.assignee === "Unassigned" ? "Unassigned" : ticket.assignee}
            </span>
          </div>
        </div>
      </div>

      {/* Second line: Key, Status, Priority, Story Points + Relationships on far right */}
      <div className="flex items-center gap-2">
        <Badge
          variant="outline"
          className="text-cyan-400 border-cyan-600/50 bg-cyan-500/10 text-[10px] px-1.5 py-0.5 font-mono hover:bg-cyan-500/20 transition-colors"
        >
          <a
            href={jiraUrl(ticket.key)}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="hover:text-cyan-300"
          >
            {ticket.key}
          </a>
        </Badge>
        <Link
          href={`/context/jira/${ticket.key}`}
          onClick={(e) => e.stopPropagation()}
        >
          <Button
            variant="ghost"
            size="sm"
            className="h-5 px-1.5 text-[10px] text-blue-400 hover:text-blue-300 hover:bg-blue-500/10"
            title="View work context"
          >
            <LinkIcon className="w-3 h-3 mr-0.5" />
            Context
          </Button>
        </Link>
        <Badge className={`${statusColor} text-[10px] px-1.5 py-0`}>
          {statusDisplay}
        </Badge>
        {ticket.priority && (
          <Badge variant="outline" className={`${priorityColor} border-current/30 bg-current/5 text-[10px] px-1.5 py-0`}>
            {ticket.priority}
          </Badge>
        )}
        {ticket.story_points !== undefined && ticket.story_points > 0 && (
          <Badge variant="outline" className="text-amber-400 border-amber-600/50 bg-amber-500/10 text-[10px] px-1.5 py-0">
            {ticket.story_points} pts
          </Badge>
        )}

        {/* Relationships icons on far right */}
        {showRelationships && (
          <div className="flex items-center gap-1 ml-auto text-[10px]">
            {ticket.my_relationships.watching && (
              <span className="text-zinc-500" title="Watching">👀</span>
            )}
            {ticket.my_relationships.paired && (
              <span className="text-zinc-400" title="Paired/Reviewer">🤝</span>
            )}
            {ticket.my_relationships.mr_reviewed && (
              <span className="text-emerald-400" title="MR Reviewed">✓</span>
            )}
            {ticket.linked_mrs && ticket.linked_mrs.length > 0 && (
              <span className="text-blue-400" title={`${ticket.linked_mrs.length} MR(s)`}>
                🔗 {ticket.linked_mrs.length}
              </span>
            )}
            {ticket.my_relationships.slack_discussed && (
              <span className="text-purple-400" title="Discussed in Slack">💬</span>
            )}
          </div>
        )}

        {!compact && ticket.age_days !== undefined && (
          <span className="text-zinc-600 ml-2">
            {ticket.age_days}d
          </span>
        )}
      </div>
    </div>
  );
}
