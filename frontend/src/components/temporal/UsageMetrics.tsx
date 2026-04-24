"use client";

import { useCallback } from "react";
import { TrendingUp } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { usePoll } from "@/lib/polling";
import { api, TemporalUsage } from "@/lib/api";

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

export function UsageMetrics() {
  const fetcher = useCallback(() => api.temporalUsage("30d"), []);
  const { data, loading, error } = usePoll<TemporalUsage>(fetcher, 60_000);

  return (
    <ScrollableCard
      title="Usage (30d)"
      icon={<TrendingUp className="h-4 w-4" />}
    >
      {loading && <p className="text-xs text-zinc-500">Loading...</p>}
      {error && <p className="text-xs text-red-400">Failed to load usage (VPN?)</p>}
      {data && (
        <div className="space-y-2">
          <div className="text-xs">
            <span className="text-zinc-400">Total Activities: </span>
            <span className="text-zinc-200 font-mono">{formatCount(data.total_activities)}</span>
          </div>

          {data.by_service.length > 0 && (
            <div className="space-y-1">
              <p className="text-[10px] text-zinc-500 uppercase tracking-wide">By Service</p>
              {data.by_service.map((s) => (
                <div key={s.service} className="flex items-center gap-2 text-xs">
                  <div className="flex-1 flex items-center gap-2">
                    <span className="text-zinc-300 truncate">{s.service}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <div className="w-16 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-500 rounded-full"
                        style={{ width: `${Math.min(s.percent, 100)}%` }}
                      />
                    </div>
                    <span className="text-zinc-500 w-12 text-right font-mono">
                      {formatCount(s.activity_count)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {data.by_service.length === 0 && (
            <p className="text-xs text-zinc-500">No activity data available</p>
          )}
        </div>
      )}
    </ScrollableCard>
  );
}
