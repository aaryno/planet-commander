"use client";

import { useCallback } from "react";
import { BarChart3 } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { usePoll } from "@/lib/polling";
import { api, TemporalSentiment } from "@/lib/api";

function SentimentBar({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-16 text-zinc-400">{label}</span>
      <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right text-zinc-500">{pct}%</span>
    </div>
  );
}

export function SlackSentimentCard() {
  const fetcher = useCallback(() => api.temporalSlackSentiment(7), []);
  const { data, loading, error } = usePoll<TemporalSentiment>(fetcher, 300_000);

  return (
    <ScrollableCard
      title="Sentiment (7d)"
      icon={<BarChart3 className="h-4 w-4" />}
    >
      {loading && <p className="text-xs text-zinc-500">Loading...</p>}
      {error && <p className="text-xs text-red-400">Failed to load</p>}
      {data && (
        <div className="space-y-1.5">
          <SentimentBar label="Positive" pct={data.positive_pct} color="bg-emerald-500" />
          <SentimentBar label="Neutral" pct={data.neutral_pct} color="bg-zinc-500" />
          <SentimentBar label="Frustrated" pct={data.frustrated_pct} color="bg-red-500" />
          <p className="text-[10px] text-zinc-600 pt-1">
            {data.total_messages} messages analyzed
          </p>
        </div>
      )}
    </ScrollableCard>
  );
}
