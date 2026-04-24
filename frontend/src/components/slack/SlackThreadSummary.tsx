"use client";

import { useState } from "react";
import { MessageSquare, Users, Clock, AlertTriangle, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SlackThreadDetail } from "@/lib/api";

interface SlackThreadSummaryProps {
  thread: SlackThreadDetail;
}

export function SlackThreadSummary({ thread }: SlackThreadSummaryProps) {
  const [messagesExpanded, setMessagesExpanded] = useState(false);
  const [participantsExpanded, setParticipantsExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          {/* Channel + Incident badge */}
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm font-medium text-zinc-400">
              #{thread.channel_name || thread.channel_id}
            </span>
            {thread.is_incident && (
              <Badge variant="destructive" className="flex items-center gap-1">
                <AlertTriangle className="h-4 w-4" />
                {thread.severity ? `SEV${thread.severity}` : thread.incident_type || "Incident"}
              </Badge>
            )}
            {thread.is_active && (
              <Badge className="bg-emerald-500/20 border-emerald-500/30 text-emerald-400">
                Active
              </Badge>
            )}
          </div>

          {/* Title */}
          {thread.title && (
            <h3 className="text-lg font-semibold text-zinc-100 mb-2">
              {thread.title}
            </h3>
          )}

          {/* Metadata */}
          <div className="flex items-center gap-4 text-sm text-zinc-500">
            {thread.participant_count && (
              <div className="flex items-center gap-1.5">
                <Users className="h-4 w-4" />
                <span>{thread.participant_count} participant{thread.participant_count > 1 ? "s" : ""}</span>
              </div>
            )}
            {thread.message_count && (
              <div className="flex items-center gap-1.5">
                <MessageSquare className="h-4 w-4" />
                <span>{thread.message_count} message{thread.message_count > 1 ? "s" : ""}</span>
              </div>
            )}
            {thread.duration_display && (
              <div className="flex items-center gap-1.5">
                <Clock className="h-4 w-4" />
                <span>{thread.duration_display}</span>
              </div>
            )}
          </div>
        </div>

        {/* External link */}
        <a
          href={thread.permalink}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-shrink-0"
        >
          <Button variant="outline" size="sm" className="gap-2">
            <ExternalLink className="h-4 w-4" />
            Open in Slack
          </Button>
        </a>
      </div>

      {/* Summary text */}
      {thread.summary_text && (
        <div className="bg-zinc-800/50 rounded-lg p-3">
          <p className="text-sm text-zinc-300 leading-relaxed">
            {thread.summary_text}
          </p>
        </div>
      )}

      {/* Cross-references */}
      {thread.has_cross_references && (
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wide">
            Referenced In Thread
          </h4>
          <div className="flex flex-wrap gap-2">
            {/* JIRA keys */}
            {thread.jira_keys && thread.jira_keys.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {thread.jira_keys.map((key) => (
                  <a
                    key={key}
                    href={`https://hello.planet.com/jira/browse/${key}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-block"
                  >
                    <Badge
                      variant="outline"
                      className="bg-blue-500/10 border-blue-500/30 text-blue-400 hover:bg-blue-500/20 cursor-pointer"
                    >
                      {key}
                    </Badge>
                  </a>
                ))}
              </div>
            )}

            {/* PagerDuty incidents */}
            {thread.pagerduty_incident_ids && thread.pagerduty_incident_ids.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {thread.pagerduty_incident_ids.map((incidentId) => (
                  <Badge
                    key={incidentId}
                    variant="outline"
                    className="bg-red-500/10 border-red-500/30 text-red-400"
                  >
                    PD: {incidentId}
                  </Badge>
                ))}
              </div>
            )}

            {/* GitLab MRs */}
            {thread.gitlab_mr_refs && thread.gitlab_mr_refs.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {thread.gitlab_mr_refs.map((mrRef) => (
                  <Badge
                    key={mrRef}
                    variant="outline"
                    className="bg-purple-500/10 border-purple-500/30 text-purple-400"
                  >
                    {mrRef}
                  </Badge>
                ))}
              </div>
            )}

            {/* Cross-channel refs */}
            {thread.cross_channel_refs && thread.cross_channel_refs.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {thread.cross_channel_refs.map((channel) => (
                  <Badge
                    key={channel}
                    variant="outline"
                    className="bg-zinc-600/20 border-zinc-600/40 text-zinc-400"
                  >
                    #{channel}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Participants */}
      {thread.participants && thread.participants.length > 0 && (
        <div className="space-y-2">
          <button
            onClick={() => setParticipantsExpanded(!participantsExpanded)}
            className="flex items-center gap-2 text-xs font-medium text-zinc-400 uppercase tracking-wide hover:text-zinc-300 transition-colors"
          >
            <Users className="h-4 w-4" />
            Participants ({thread.participants.length})
            {participantsExpanded ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
          </button>
          {participantsExpanded && (
            <div className="flex flex-wrap gap-2">
              {thread.participants.map((participant) => (
                <Badge
                  key={participant.id}
                  variant="outline"
                  className="bg-zinc-800/50 border-zinc-700"
                >
                  {participant.display_name || participant.name}
                </Badge>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Reactions */}
      {thread.reactions && Object.keys(thread.reactions).length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wide">
            Reactions
          </h4>
          <div className="flex flex-wrap gap-2">
            {Object.entries(thread.reactions)
              .sort((a, b) => b[1] - a[1])
              .map(([emoji, count]) => (
                <Badge
                  key={emoji}
                  variant="outline"
                  className="bg-zinc-800/50 border-zinc-700"
                >
                  :{emoji}: {count}
                </Badge>
              ))}
          </div>
        </div>
      )}

      {/* Messages timeline */}
      {thread.messages && thread.messages.length > 0 && (
        <div className="space-y-2">
          <button
            onClick={() => setMessagesExpanded(!messagesExpanded)}
            className="flex items-center gap-2 text-xs font-medium text-zinc-400 uppercase tracking-wide hover:text-zinc-300 transition-colors"
          >
            <MessageSquare className="h-4 w-4" />
            Messages ({thread.messages.length})
            {messagesExpanded ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
          </button>
          {messagesExpanded && (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {thread.messages.map((message, idx) => (
                <div
                  key={message.ts || idx}
                  className="bg-zinc-800/50 rounded-lg p-3 space-y-1"
                >
                  <div className="flex items-center gap-2 text-xs">
                    <span className="font-medium text-zinc-300">
                      {message.user_name || message.user || "Unknown"}
                    </span>
                    <span className="text-zinc-600">
                      {message.ts ? new Date(parseFloat(message.ts) * 1000).toLocaleString() : ""}
                    </span>
                  </div>
                  {message.text && (
                    <p className="text-sm text-zinc-400 whitespace-pre-wrap">
                      {message.text}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Metadata footer */}
      <div className="pt-3 border-t border-zinc-800 text-xs text-zinc-600 space-y-1">
        {thread.start_time && (
          <p>Started: {new Date(thread.start_time).toLocaleString()}</p>
        )}
        {thread.end_time && (
          <p>Last activity: {new Date(thread.end_time).toLocaleString()}</p>
        )}
        <p>Fetched: {new Date(thread.fetched_at).toLocaleString()}</p>
        {thread.surrounding_context_fetched && (
          <p className="text-emerald-600">✓ Includes surrounding context (±24h)</p>
        )}
      </div>
    </div>
  );
}
