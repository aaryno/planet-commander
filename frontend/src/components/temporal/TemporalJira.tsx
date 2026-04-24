"use client";

import { useCallback } from "react";
import { CheckSquare } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { usePoll } from "@/lib/polling";
import { api, TemporalJiraResponse } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { JIRA_STATUS_COLORS } from "@/lib/status-colors";

export function TemporalJira() {
  const fetcher = useCallback(() => api.temporalJiraTickets(), []);
  const { data, loading, error } = usePoll<TemporalJiraResponse>(fetcher, 300_000);

  return (
    <ScrollableCard
      title={`JIRA Tickets${data?.total ? ` (${data.total})` : ""}`}
      icon={<CheckSquare className="h-4 w-4" />}
    >
      {loading && <p className="text-xs text-zinc-500">Loading...</p>}
      {error && <p className="text-xs text-red-400">Failed to load JIRA data</p>}
      {data && data.total === 0 && (
        <p className="text-xs text-zinc-500">No open Temporal tickets</p>
      )}
      {data && data.total > 0 && (
        <div className="space-y-2">
          {/* Status summary */}
          <div className="flex gap-2 flex-wrap">
            {Object.entries(data.by_status).map(([status, count]) => (
              <span key={status} className="text-[10px] text-zinc-400">
                {status}: <span className="text-zinc-300">{count}</span>
              </span>
            ))}
          </div>

          {/* Ticket list */}
          <div className="space-y-1">
            {data.tickets.slice(0, 8).map((ticket) => (
              <div key={ticket.key} className="flex items-start gap-2 text-xs py-0.5">
                <Badge className={`${JIRA_STATUS_COLORS[ticket.status] || "bg-zinc-700 text-zinc-300"} text-[10px] px-1.5 py-0 shrink-0`}>
                  {ticket.status}
                </Badge>
                <div className="min-w-0">
                  <span className="text-zinc-500 font-mono">{ticket.key}</span>
                  <span className="text-zinc-300 ml-1.5">{ticket.summary}</span>
                  {ticket.assignee !== "Unassigned" && (
                    <span className="text-zinc-600 ml-1">({ticket.assignee})</span>
                  )}
                </div>
              </div>
            ))}
            {data.total > 8 && (
              <p className="text-[10px] text-zinc-600">+{data.total - 8} more</p>
            )}
          </div>
        </div>
      )}
    </ScrollableCard>
  );
}
