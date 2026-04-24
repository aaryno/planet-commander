"use client";

import { useCallback, useEffect, useState } from "react";
import { MessageCircle, Users, AlertTriangle, RefreshCw, Sparkles, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { usePoll } from "@/lib/polling";
import { api, TemporalUnanswered, TemporalSlackSummary, SlackChannelFreshness } from "@/lib/api";
import { formatHoursCompact } from "@/lib/time-utils";

const CHANNELS = ["temporal-dev", "temporal-users"];

function StaleWarning({ freshness }: { freshness?: Record<string, SlackChannelFreshness> }) {
  if (!freshness) return null;
  const staleChannels = Object.entries(freshness).filter(([, f]) => f.stale);
  if (staleChannels.length === 0) return null;

  const oldest = Math.max(...staleChannels.map(([, f]) => f.days_old ?? 0));
  return (
    <div className="flex items-center gap-1.5 text-[10px] text-yellow-400/80 bg-yellow-400/5 border border-yellow-400/20 rounded px-2 py-1">
      <AlertTriangle className="h-3 w-3 shrink-0" />
      <span>Data is {oldest}d old. Sync to refresh.</span>
    </div>
  );
}

/** Simple markdown renderer for summaries */
function MarkdownContent({ content }: { content: string }) {
  const html = content
    .replace(/^### (.+)$/gm, '<h3 class="text-zinc-200 font-semibold mt-3 mb-1 text-xs">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-zinc-100 font-semibold mt-4 mb-1.5 text-sm">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-zinc-100 font-bold mt-4 mb-2 text-sm">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-zinc-200">$1</strong>')
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, '<code class="bg-zinc-800 px-1 rounded text-zinc-300">$1</code>')
    .replace(/^- (.+)$/gm, '<li class="ml-3 text-zinc-400">$1</li>')
    .replace(/\n\n/g, '</p><p class="mt-2 text-zinc-400">')
    .replace(/\n/g, "<br/>");

  return (
    <div
      className="text-zinc-400 text-xs leading-relaxed"
      dangerouslySetInnerHTML={{ __html: `<p>${html}</p>` }}
    />
  );
}

export function UnansweredSlack() {
  const [selectedChannels, setSelectedChannels] = useState<string[]>(CHANNELS);
  const [activeTab, setActiveTab] = useState<"unanswered" | "activity" | "summary">("unanswered");
  const [isSyncing, setIsSyncing] = useState(false);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [aiSummary, setAiSummary] = useState<string | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const unansweredFetcher = useCallback(
    () => api.temporalSlackUnanswered(7, selectedChannels.length < CHANNELS.length ? selectedChannels : undefined),
    [selectedChannels],
  );
  const summaryFetcher = useCallback(() => api.temporalSlackSummary(7), []);

  const { data, loading, error, refresh: refreshUnanswered } = usePoll<TemporalUnanswered>(unansweredFetcher, 300_000);
  const { data: activity, refresh: refreshActivity } = usePoll<TemporalSlackSummary>(summaryFetcher, 300_000);

  // Get freshness from whichever response we have
  const freshness = data?.freshness ?? activity?.freshness;

  // Check for cached AI summary on mount and when channels change
  useEffect(() => {
    const channelArg = selectedChannels.length < CHANNELS.length ? selectedChannels : undefined;
    api.temporalSlackAiSummary(channelArg).then((r) => {
      if (r.status === "ready" && r.summary) {
        setAiSummary(r.summary);
      } else if (r.status === "in_progress") {
        setIsSummarizing(true);
        pollForSummary();
      }
    }).catch(() => {});
  }, [selectedChannels]); // eslint-disable-line react-hooks/exhaustive-deps

  function pollForSummary() {
    const channelArg = selectedChannels.length < CHANNELS.length ? selectedChannels : undefined;
    const poll = setInterval(async () => {
      try {
        const check = await api.temporalSlackAiSummary(channelArg);
        if (check.status === "ready" && check.summary) {
          setAiSummary(check.summary);
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
  }

  function toggleChannel(ch: string) {
    setSelectedChannels((prev) => {
      if (prev.includes(ch)) {
        const next = prev.filter((c) => c !== ch);
        return next.length === 0 ? CHANNELS : next;
      }
      return [...prev, ch];
    });
  }

  async function handleSync() {
    setIsSyncing(true);
    try {
      await api.temporalSlackSync();
      // Refresh data after sync
      refreshUnanswered();
      refreshActivity();
    } catch {
      // Sync errors are non-critical
    } finally {
      setIsSyncing(false);
    }
  }

  async function handleSummarize() {
    setIsSummarizing(true);
    setSummaryError(null);
    setAiSummary(null);
    setActiveTab("summary");
    try {
      const channelArg = selectedChannels.length < CHANNELS.length ? selectedChannels : undefined;
      const result = await api.temporalSlackSummarize(7, channelArg);
      setAiSummary(result.summary);
    } catch (e) {
      setSummaryError(e instanceof Error ? e.message : "Failed to summarize");
    } finally {
      setIsSummarizing(false);
    }
  }

  return (
    <ScrollableCard
      title={`Slack${data?.total ? ` (${data.total})` : ""}`}
      icon={<MessageCircle className="h-4 w-4" />}
     
    >
      <div className="space-y-2">
        {/* Stale data warning */}
        <StaleWarning freshness={freshness} />

        {/* Tab bar + actions */}
        <div className="flex items-center justify-between">
          <div className="flex gap-1 border-b border-zinc-800 pb-1">
            <button
              onClick={() => setActiveTab("unanswered")}
              className={`text-[11px] px-2 py-0.5 rounded-t ${
                activeTab === "unanswered"
                  ? "bg-zinc-800 text-zinc-200"
                  : "text-zinc-500 hover:text-zinc-400"
              }`}
            >
              Unanswered
            </button>
            <button
              onClick={() => setActiveTab("activity")}
              className={`text-[11px] px-2 py-0.5 rounded-t ${
                activeTab === "activity"
                  ? "bg-zinc-800 text-zinc-200"
                  : "text-zinc-500 hover:text-zinc-400"
              }`}
            >
              Activity
            </button>
            <button
              onClick={() => setActiveTab("summary")}
              className={`text-[11px] px-2 py-0.5 rounded-t ${
                activeTab === "summary"
                  ? "bg-zinc-800 text-zinc-200"
                  : "text-zinc-500 hover:text-zinc-400"
              }`}
            >
              Summary
            </button>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 text-zinc-500 hover:text-zinc-300"
              onClick={handleSync}
              disabled={isSyncing}
              title="Sync new messages from Slack"
            >
              <RefreshCw className={`h-3 w-3 ${isSyncing ? "animate-spin" : ""}`} />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 text-zinc-500 hover:text-zinc-300"
              onClick={handleSummarize}
              disabled={isSummarizing}
              title="Generate AI summary"
            >
              {isSummarizing ? (
                <Loader2 className="h-3 w-3 animate-spin text-blue-400" />
              ) : (
                <Sparkles className="h-3 w-3" />
              )}
            </Button>
          </div>
        </div>

        {/* Channel filter pills */}
        <div className="flex gap-1">
          {CHANNELS.map((ch) => (
            <button
              key={ch}
              onClick={() => toggleChannel(ch)}
              className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors ${
                selectedChannels.includes(ch)
                  ? "border-emerald-600/40 bg-emerald-600/10 text-emerald-400"
                  : "border-zinc-700 text-zinc-500 hover:text-zinc-400"
              }`}
            >
              #{ch}
            </button>
          ))}
        </div>

        {/* Unanswered tab */}
        {activeTab === "unanswered" && (
          <>
            {loading && <p className="text-xs text-zinc-500">Loading...</p>}
            {error && <p className="text-xs text-red-400">Failed to load Slack data</p>}
            {data && data.total === 0 && (
              <p className="text-xs text-zinc-500">
                No unanswered questions
                {data.actual_days && data.actual_days > 7
                  ? ` (searched last ${data.actual_days} days)`
                  : " in the last 7 days"}
              </p>
            )}
            {data && data.total > 0 && (
              <div className="space-y-2">
                {data.unanswered
                  .filter((msg) => selectedChannels.includes(msg.channel))
                  .map((msg, i) => (
                  <div key={i} className="text-xs border-l-2 border-zinc-700 pl-2 py-0.5">
                    <div className="flex items-center gap-2 text-zinc-400">
                      <span className="text-zinc-500">#{msg.channel}</span>
                      <span className="font-medium text-zinc-300">@{msg.user}</span>
                      <span className="text-zinc-600">{formatHoursCompact(msg.age_hours)} ago</span>
                    </div>
                    <p className="text-zinc-400 mt-0.5 line-clamp-2">{msg.text}</p>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* Activity tab */}
        {activeTab === "activity" && activity && (
          <div className="space-y-3">
            {activity.channels
              .filter((ch) => selectedChannels.includes(ch.channel))
              .map((ch) => (
                <div key={ch.channel} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-zinc-300 font-medium">#{ch.channel}</span>
                    <span className="text-zinc-500">
                      {ch.message_count} msgs, {ch.unanswered_count} unanswered
                    </span>
                  </div>
                  {ch.active_users.length > 0 && (
                    <div className="flex items-start gap-1.5 ml-1">
                      <Users className="h-3 w-3 text-zinc-600 mt-0.5 shrink-0" />
                      <div className="flex flex-wrap gap-x-2 gap-y-0.5">
                        {ch.active_users.map((u) => (
                          <span key={u.name} className="text-[10px] text-zinc-400">
                            {u.name}
                            <span className="text-zinc-600 ml-0.5">({u.messages})</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {ch.active_users.length === 0 && (
                    <p className="text-[10px] text-zinc-600 ml-1">No activity</p>
                  )}
                </div>
              ))}
            <div className="text-[10px] text-zinc-600 pt-1 border-t border-zinc-800">
              {activity.total_messages} total messages
              {activity.actual_days && activity.actual_days > activity.days
                ? ` (last ${activity.actual_days} days — data is stale)`
                : ` in last ${activity.days} days`}
            </div>
          </div>
        )}

        {activeTab === "activity" && !activity && (
          <p className="text-xs text-zinc-500">Loading activity...</p>
        )}

        {/* AI Summary tab */}
        {activeTab === "summary" && (
          <>
            {isSummarizing && (
              <div className="flex items-center gap-2 text-zinc-400 py-4">
                <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
                <span className="text-xs">Claude is summarizing Temporal channels...</span>
              </div>
            )}
            {summaryError && <p className="text-xs text-red-400">{summaryError}</p>}
            {!isSummarizing && aiSummary && (
              <div className="rounded-md border border-zinc-800 bg-zinc-950/50 p-2.5 max-h-80 overflow-y-auto">
                <MarkdownContent content={aiSummary} />
              </div>
            )}
            {!isSummarizing && !aiSummary && !summaryError && (
              <div className="text-center py-4">
                <p className="text-xs text-zinc-500 mb-2">No summary yet</p>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-[10px] px-3 border-zinc-700 text-zinc-300 hover:bg-zinc-800"
                  onClick={handleSummarize}
                >
                  <Sparkles className="h-3 w-3 mr-1" />
                  Generate Summary
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </ScrollableCard>
  );
}
