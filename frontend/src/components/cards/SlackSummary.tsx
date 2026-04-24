"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, MessageSquare, RefreshCw, Sparkles, Eye, Info } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { api } from "@/lib/api";
import type { SlackTeam, SlackStats } from "@/lib/api";
import { ChannelMessagesModal } from "./ChannelMessagesModal";
import { ChannelDetailsModal } from "./ChannelDetailsModal";
import { useUrlParam, useUrlNumberParam } from "@/lib/use-url-state";

// Primary teams shown as chips
const PRIMARY_TEAMS = ["compute", "wx", "g4", "jobs", "temporal"];

// Team badge colors (reuse project color scheme)
const TEAM_COLORS: Record<string, string> = {
  compute: "bg-zinc-500/20 text-zinc-300 border-zinc-500/40",
  wx: "bg-blue-500/20 text-blue-300 border-blue-500/40",
  g4: "bg-violet-500/20 text-violet-300 border-violet-500/40",
  jobs: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  temporal: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  dnd: "bg-pink-500/20 text-pink-300 border-pink-500/40",
  datapipeline: "bg-cyan-500/20 text-cyan-300 border-cyan-500/40",
  hobbes: "bg-orange-500/20 text-orange-300 border-orange-500/40",
  delta: "bg-rose-500/20 text-rose-300 border-rose-500/40",
  mosaics: "bg-lime-500/20 text-lime-300 border-lime-500/40",
};

const TIME_OPTIONS = [
  { label: "1d", days: 1 },
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
];

export function SlackSummary() {
  const [teams, setTeams] = useState<SlackTeam[]>([]);
  const [selectedTeam, setSelectedTeam] = useUrlParam("slack.team", "compute");
  const [days, setDays] = useUrlNumberParam("slack.days", 7);
  const [stats, setStats] = useState<SlackStats | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [viewingChannel, setViewingChannel] = useState<string | null>(null);
  const [detailsChannel, setDetailsChannel] = useState<string | null>(null);

  // Fetch teams on mount
  useEffect(() => {
    api.slackTeams().then((r) => setTeams(r.teams)).catch(() => {});
  }, []);

  // Fetch stats and check for cached summary when team or days change
  useEffect(() => {
    setStats(null);
    setSummary(null);
    setError(null);
    api
      .slackStats(selectedTeam, days)
      .then((r) => setStats(r))
      .catch(() => {});
    // Check for cached summary
    api
      .slackLatestSummary(selectedTeam, days)
      .then((r) => {
        if (r.status === "ready" && r.summary) {
          setSummary(r.summary);
        } else if (r.status === "in_progress") {
          // A summarization is running server-side, poll for it
          setIsSummarizing(true);
          const poll = setInterval(async () => {
            try {
              const check = await api.slackLatestSummary(selectedTeam, days);
              if (check.status === "ready" && check.summary) {
                setSummary(check.summary);
                setIsSummarizing(false);
                clearInterval(poll);
              } else if (check.status === "none") {
                setIsSummarizing(false);
                clearInterval(poll);
              }
            } catch {
              clearInterval(poll);
              setIsSummarizing(false);
            }
          }, 2000);
          // Clean up on unmount
          return () => clearInterval(poll);
        }
      })
      .catch(() => {});
  }, [selectedTeam, days]);

  const handleSummarize = useCallback(async () => {
    setIsSummarizing(true);
    setError(null);
    setSummary(null);

    // Set a timeout to detect hanging summarization
    const timeoutId = setTimeout(() => {
      if (isSummarizing) {
        setError("Summarization is taking longer than expected. The backend may be processing a large amount of messages. Please wait or try again.");
      }
    }, 30000); // 30 second warning

    try {
      const result = await api.slackSummarize(selectedTeam, days);
      clearTimeout(timeoutId);
      setSummary(result.summary);
    } catch (e) {
      clearTimeout(timeoutId);
      const errorMessage = e instanceof Error ? e.message : "Failed to summarize";
      // Check if it's a timeout or connection error
      if (errorMessage.includes("fetch") || errorMessage.includes("NetworkError") || errorMessage.includes("timeout")) {
        setError("Connection to backend failed. Please ensure the backend is running (docker-compose up).");
      } else {
        setError(errorMessage);
      }
    } finally {
      setIsSummarizing(false);
    }
  }, [selectedTeam, days, isSummarizing]);

  const handleSync = useCallback(async () => {
    setIsSyncing(true);
    setSyncStatus("Connecting...");
    setError(null);

    try {
      // Use SSE for live sync progress
      const eventSource = new EventSource(
        `/api/slack/sync-stream?team=${encodeURIComponent(selectedTeam)}`
      );

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.status === "syncing") {
            // Show progress
            const msg = `Syncing ${data.channel} (${data.channel_index}/${data.total_channels})${
              data.messages_synced > 0 ? ` · ${data.messages_synced} messages` : ""
            }`;
            setSyncStatus(msg);
          } else if (data.status === "complete") {
            // Sync complete
            const lastAge = data.last_message_age || "unknown";
            setSyncStatus(`Complete · ${data.messages_synced} messages · Last: ${lastAge} ago`);
            eventSource.close();

            // Refresh stats
            api.slackStats(selectedTeam, days).then(setStats).catch(() => {});

            // Clear status after 3 seconds
            setTimeout(() => {
              setIsSyncing(false);
              setSyncStatus(null);
            }, 3000);
          } else if (data.status === "error") {
            setError(data.error || "Sync failed");
            setSyncStatus(null);
            setIsSyncing(false);
            eventSource.close();
          }
        } catch (e) {
          console.error("SSE parse error:", e);
        }
      };

      eventSource.onerror = () => {
        setError("Sync connection failed");
        setSyncStatus(null);
        setIsSyncing(false);
        eventSource.close();
      };
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sync failed");
      setIsSyncing(false);
      setSyncStatus(null);
    }
  }, [selectedTeam, days]);

  const secondaryTeams = teams.filter((t) => !PRIMARY_TEAMS.includes(t.id));
  const selectedTeamInfo = teams.find((t) => t.id === selectedTeam);

  return (
    <div className="flex flex-col h-full">
      {/* Team selector row */}
      <div className="flex items-center gap-1.5 flex-wrap mb-3">
        {PRIMARY_TEAMS.map((id) => {
          const team = teams.find((t) => t.id === id);
          const label = team?.label || id;
          return (
            <Badge
              key={id}
              variant="outline"
              className={`cursor-pointer text-[10px] px-2 py-0.5 transition-all ${
                selectedTeam === id
                  ? `${TEAM_COLORS[id] || ""} border ring-1 ring-white/10`
                  : "border-zinc-700 text-zinc-500 hover:text-zinc-300 hover:border-zinc-600"
              }`}
              onClick={() => setSelectedTeam(id)}
            >
              {label}
            </Badge>
          );
        })}

        {secondaryTeams.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Badge
                variant="outline"
                className={`cursor-pointer text-[10px] px-2 py-0.5 ${
                  !PRIMARY_TEAMS.includes(selectedTeam)
                    ? `${TEAM_COLORS[selectedTeam] || ""} border ring-1 ring-white/10`
                    : "border-zinc-700 text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {!PRIMARY_TEAMS.includes(selectedTeam)
                  ? selectedTeamInfo?.label || selectedTeam
                  : "More..."}
              </Badge>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              className="bg-zinc-900 border-zinc-700"
            >
              {secondaryTeams.map((t) => (
                <DropdownMenuItem
                  key={t.id}
                  onClick={() => setSelectedTeam(t.id)}
                  className="text-zinc-300 focus:bg-zinc-800 focus:text-zinc-100 text-xs"
                >
                  {t.label}
                  <span className="ml-auto text-zinc-600 text-[10px]">
                    {t.channels.length} ch
                  </span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      {/* Time filter + actions row */}
      <div className="flex items-center gap-2 mb-3">
        <div className="flex rounded-md border border-zinc-700 overflow-hidden">
          {TIME_OPTIONS.map((opt) => (
            <button
              key={opt.days}
              onClick={() => setDays(opt.days)}
              className={`px-2.5 py-1 text-[10px] font-medium transition-colors ${
                days === opt.days
                  ? "bg-zinc-700 text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1.5 ml-auto">
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-[10px] px-2.5 border-zinc-700 text-zinc-300 hover:bg-zinc-800"
            onClick={handleSync}
            disabled={isSyncing}
            title="Sync new messages from Slack"
          >
            {isSyncing ? (
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            ) : (
              <RefreshCw className="h-3 w-3 mr-1" />
            )}
            Sync
          </Button>

          <Button
            variant="outline"
            size="sm"
            className="h-7 text-[10px] px-2.5 border-zinc-700 text-zinc-300 hover:bg-zinc-800"
            onClick={handleSummarize}
            disabled={isSummarizing}
          >
            {isSummarizing ? (
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            ) : (
              <Sparkles className="h-3 w-3 mr-1" />
            )}
            Summarize
          </Button>
        </div>
      </div>

      {/* Summary content area */}
      <div className="flex-1 min-h-0 overflow-y-auto rounded-md border border-zinc-800 bg-zinc-950/50 p-3">
        {isSummarizing ? (
          <div className="flex items-center gap-2 text-zinc-400 py-4">
            <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
            <span className="text-xs">
              Claude is summarizing{" "}
              {selectedTeamInfo?.label || selectedTeam} messages...
            </span>
          </div>
        ) : error ? (
          <p className="text-xs text-red-400">{error}</p>
        ) : summary ? (
          <div className="prose prose-invert prose-sm max-w-none text-xs leading-relaxed">
            <MarkdownContent content={summary} />
          </div>
        ) : stats ? (
          <div className="space-y-2">
            <p className="text-[10px] text-zinc-500 mb-2">
              {stats.total} messages across {stats.channels.length} channels (
              {days}d)
            </p>
            {stats.channels.map((ch) => (
              <div
                key={ch.name}
                className="flex items-center justify-between text-xs group hover:bg-zinc-900/50 rounded px-1 py-1 -mx-1 transition-colors"
              >
                <button
                  onClick={() => setViewingChannel(ch.name)}
                  className="text-zinc-400 hover:text-blue-400 transition-colors"
                >
                  #{ch.name}
                </button>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setViewingChannel(ch.name)}
                      className="h-5 w-5 p-0 text-zinc-500 hover:text-blue-400 hover:bg-blue-500/10"
                      title="View messages"
                    >
                      <Eye className="h-3 w-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDetailsChannel(ch.name)}
                      className="h-5 w-5 p-0 text-zinc-500 hover:text-emerald-400 hover:bg-emerald-500/10"
                      title="View details"
                    >
                      <Info className="h-3 w-3" />
                    </Button>
                  </div>
                  <span className="text-zinc-600 text-[10px]">
                    {ch.last_activity || "—"}
                  </span>
                  <Badge
                    variant="outline"
                    className="border-zinc-700 text-zinc-500 text-[10px] px-1.5 py-0"
                  >
                    {ch.count}
                  </Badge>
                </div>
              </div>
            ))}
            <p className="text-[10px] text-zinc-600 mt-3">
              Click &quot;Summarize&quot; for an AI-powered summary
            </p>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full py-8">
            <p className="text-xs text-zinc-600">Loading channel stats...</p>
          </div>
        )}
      </div>

      {/* Footer stats / sync status */}
      {syncStatus ? (
        <div className="mt-2 text-[10px] text-blue-400 flex items-center gap-1">
          {isSyncing && <Loader2 className="h-3 w-3 animate-spin" />}
          {syncStatus}
        </div>
      ) : stats ? (
        <div className="mt-2 text-[10px] text-zinc-600 flex items-center gap-1">
          <MessageSquare className="h-3 w-3" />
          {stats.total} messages · {stats.channels.length} channels ·{" "}
          {days}d window
        </div>
      ) : null}

      {/* Modals */}
      {viewingChannel && (
        <ChannelMessagesModal
          channel={viewingChannel}
          days={days}
          onClose={() => setViewingChannel(null)}
        />
      )}
      {detailsChannel && (
        <ChannelDetailsModal
          channel={detailsChannel}
          onClose={() => setDetailsChannel(null)}
        />
      )}
    </div>
  );
}

/** Simple markdown renderer for summaries */
function MarkdownContent({ content }: { content: string }) {
  // Convert markdown to basic HTML
  const html = content
    // Headers
    .replace(/^### (.+)$/gm, '<h3 class="text-zinc-200 font-semibold mt-3 mb-1 text-xs">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-zinc-100 font-semibold mt-4 mb-1.5 text-sm">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-zinc-100 font-bold mt-4 mb-2 text-sm">$1</h1>')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-zinc-200">$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="bg-zinc-800 px-1 rounded text-zinc-300">$1</code>')
    // Bullet lists
    .replace(/^- (.+)$/gm, '<li class="ml-3 text-zinc-400">$1</li>')
    // Paragraphs (double newline)
    .replace(/\n\n/g, '</p><p class="mt-2 text-zinc-400">')
    // Single newlines in context
    .replace(/\n/g, "<br/>");

  return (
    <div
      className="text-zinc-400"
      dangerouslySetInnerHTML={{ __html: `<p>${html}</p>` }}
    />
  );
}
