"use client";

import { MessageSquare, Users, Clock, AlertTriangle, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { SlackThread } from "@/lib/api";

interface SlackThreadCardProps {
  thread: SlackThread;
  onThreadClick?: (threadId: string) => void;
}

export function SlackThreadCard({ thread, onThreadClick }: SlackThreadCardProps) {
  const handleClick = () => {
    if (onThreadClick) {
      onThreadClick(thread.id);
    }
  };

  return (
    <div
      className="group relative rounded-lg border border-zinc-800 bg-zinc-900/50 p-3 hover:bg-zinc-900 hover:border-zinc-700 transition-colors cursor-pointer"
      onClick={handleClick}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          {/* Channel name + Incident badge */}
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-xs font-medium text-zinc-400">
              #{thread.channel_name || thread.channel_id}
            </span>
            {thread.is_incident && (
              <Badge variant="destructive" className="flex items-center gap-1 text-xs">
                <AlertTriangle className="h-3 w-3" />
                {thread.severity ? `SEV${thread.severity}` : "Incident"}
              </Badge>
            )}
          </div>

          {/* Thread title */}
          {thread.title && (
            <h4 className="text-sm font-medium text-zinc-200 line-clamp-2 group-hover:text-zinc-100">
              {thread.title}
            </h4>
          )}
        </div>

        {/* External link icon */}
        <a
          href={thread.permalink}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="flex-shrink-0 text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          <ExternalLink className="h-4 w-4" />
        </a>
      </div>

      {/* Metadata row */}
      <div className="flex items-center gap-3 text-xs text-zinc-500 mb-2">
        {thread.participant_count && (
          <div className="flex items-center gap-1">
            <Users className="h-3 w-3" />
            <span>{thread.participant_count}</span>
          </div>
        )}
        {thread.message_count && (
          <div className="flex items-center gap-1">
            <MessageSquare className="h-3 w-3" />
            <span>{thread.message_count}</span>
          </div>
        )}
        {thread.duration_display && (
          <div className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            <span>{thread.duration_display}</span>
          </div>
        )}
        {thread.start_time && (
          <span className="text-zinc-600">
            {new Date(thread.start_time).toLocaleDateString()}
          </span>
        )}
      </div>

      {/* Cross-reference badges */}
      {thread.has_cross_references && (
        <div className="flex flex-wrap gap-1.5">
          {thread.jira_keys && thread.jira_keys.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {thread.jira_keys.slice(0, 3).map((key) => (
                <Badge
                  key={key}
                  variant="outline"
                  className="text-xs bg-blue-500/10 border-blue-500/30 text-blue-400"
                >
                  {key}
                </Badge>
              ))}
              {thread.jira_keys.length > 3 && (
                <Badge
                  variant="outline"
                  className="text-xs bg-blue-500/10 border-blue-500/30 text-blue-400"
                >
                  +{thread.jira_keys.length - 3}
                </Badge>
              )}
            </div>
          )}
          {thread.pagerduty_incident_ids && thread.pagerduty_incident_ids.length > 0 && (
            <Badge
              variant="outline"
              className="text-xs bg-red-500/10 border-red-500/30 text-red-400"
            >
              {thread.pagerduty_incident_ids.length} PD incident{thread.pagerduty_incident_ids.length > 1 ? "s" : ""}
            </Badge>
          )}
          {thread.gitlab_mr_refs && thread.gitlab_mr_refs.length > 0 && (
            <Badge
              variant="outline"
              className="text-xs bg-purple-500/10 border-purple-500/30 text-purple-400"
            >
              {thread.gitlab_mr_refs.length} MR{thread.gitlab_mr_refs.length > 1 ? "s" : ""}
            </Badge>
          )}
          {thread.cross_channel_refs && thread.cross_channel_refs.length > 0 && (
            <Badge
              variant="outline"
              className="text-xs bg-zinc-600/20 border-zinc-600/40 text-zinc-400"
            >
              {thread.cross_channel_refs.length} channel{thread.cross_channel_refs.length > 1 ? "s" : ""}
            </Badge>
          )}
        </div>
      )}

      {/* Summary preview */}
      {thread.summary_text && (
        <p className="mt-2 text-xs text-zinc-500 line-clamp-2">
          {thread.summary_text}
        </p>
      )}

      {/* Active indicator */}
      {thread.is_active && (
        <div className="absolute top-2 right-2">
          <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
        </div>
      )}
    </div>
  );
}
