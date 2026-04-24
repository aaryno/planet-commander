"use client";

import { useCallback } from "react";
import { AlertTriangle } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";

interface EscalationMetrics {
  alert_name: string;
  system: string | null;
  total_warnings: number;
  escalated_count: number;
  auto_cleared_count: number;
  escalation_rate: number | null;
  avg_time_to_escalation_seconds: number | null;
  avg_time_to_clear_seconds: number | null;
  last_seen: string | null;
  last_escalated: string | null;
}

interface TopAlertsProps {
  limit?: number;
}

export function TopAlerts({ limit = 10 }: TopAlertsProps) {
  const {
    data: metrics,
    loading,
    error,
    refresh: refetch,
  } = usePoll(
    useCallback(() => api.escalationMetrics(), []),
    300_000 // 5 minutes
  );

  const getEscalationRateColor = (rate: number | null) => {
    if (rate === null) return "text-zinc-500";
    if (rate >= 0.5) return "text-red-400";
    if (rate >= 0.3) return "text-amber-400";
    return "text-emerald-400";
  };

  const getEscalationRateBgColor = (rate: number | null) => {
    if (rate === null) return "bg-zinc-800/50";
    if (rate >= 0.5) return "bg-red-500/10";
    if (rate >= 0.3) return "bg-amber-500/10";
    return "bg-emerald-500/10";
  };

  const formatDuration = (seconds: number | null) => {
    if (seconds === null) return "—";
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h`;
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "—";
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffHours < 1) return "< 1h ago";
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  // Sort by escalation rate (descending), then by total warnings
  const sortedMetrics = metrics
    ? [...metrics].sort((a, b) => {
        const rateA = a.escalation_rate ?? 0;
        const rateB = b.escalation_rate ?? 0;
        if (rateA !== rateB) return rateB - rateA;
        return b.total_warnings - a.total_warnings;
      }).slice(0, limit)
    : [];

  const menuItems = [
    {
      label: "Refresh",
      onClick: refetch,
    },
  ];

  return (
    <ScrollableCard
      title="Top Alerts by Escalation Rate"
      icon={<AlertTriangle className="w-4 h-4" />}
      menuItems={menuItems}
    >
      {loading && !metrics && (
        <p className="text-xs text-zinc-500 text-center py-8">
          Loading alert metrics...
        </p>
      )}

      {error && (
        <div className="text-xs text-red-400 text-center py-8">
          Error loading metrics: {error.message}
        </div>
      )}

      {metrics && sortedMetrics.length === 0 && (
        <p className="text-xs text-zinc-500 text-center py-8">
          No alert metrics available yet
        </p>
      )}

      {sortedMetrics.length > 0 && (
        <div className="space-y-2">
          {sortedMetrics.map((metric) => (
            <div
              key={`${metric.alert_name}-${metric.system}`}
              className={`p-3 rounded border border-zinc-800 ${getEscalationRateBgColor(
                metric.escalation_rate
              )}`}
            >
              {/* Alert name and system */}
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-zinc-200 truncate">
                    {metric.alert_name}
                  </div>
                  {metric.system && (
                    <div className="text-xs text-zinc-500 mt-0.5">
                      {metric.system}
                    </div>
                  )}
                </div>
                <div
                  className={`text-lg font-bold ml-3 ${getEscalationRateColor(
                    metric.escalation_rate
                  )}`}
                >
                  {metric.escalation_rate !== null
                    ? `${Math.round(metric.escalation_rate * 100)}%`
                    : "—"}
                </div>
              </div>

              {/* Metrics grid */}
              <div className="grid grid-cols-3 gap-3 text-xs">
                {/* Total warnings */}
                <div>
                  <div className="text-zinc-500">Total</div>
                  <div className="text-zinc-300 font-semibold">
                    {metric.total_warnings}
                  </div>
                </div>

                {/* Escalated */}
                <div>
                  <div className="text-zinc-500">Escalated</div>
                  <div className="text-red-400 font-semibold">
                    {metric.escalated_count}
                  </div>
                </div>

                {/* Auto-cleared */}
                <div>
                  <div className="text-zinc-500">Cleared</div>
                  <div className="text-emerald-400 font-semibold">
                    {metric.auto_cleared_count}
                  </div>
                </div>
              </div>

              {/* Timing metrics */}
              <div className="grid grid-cols-2 gap-3 text-xs mt-3 pt-3 border-t border-zinc-700/50">
                <div>
                  <div className="text-zinc-500">Avg time to escalate</div>
                  <div className="text-zinc-400">
                    {formatDuration(metric.avg_time_to_escalation_seconds)}
                  </div>
                </div>
                <div>
                  <div className="text-zinc-500">Last escalated</div>
                  <div className="text-zinc-400">
                    {formatDate(metric.last_escalated)}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Footer summary */}
      {sortedMetrics.length > 0 && (
        <div className="mt-4 pt-3 border-t border-zinc-800 text-xs text-zinc-500 text-center">
          Showing top {sortedMetrics.length} alerts
          {metrics && metrics.length > limit && ` of ${metrics.length} total`}
        </div>
      )}
    </ScrollableCard>
  );
}
