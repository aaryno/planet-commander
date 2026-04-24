"use client";

import { useCallback } from "react";
import { TrendingUp, TrendingDown } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { usePoll } from "@/lib/polling";
import { api, AccuracyTrend } from "@/lib/api";

interface AccuracyTrendChartProps {
  days?: number;
  windowDays?: number;
}

export function AccuracyTrendChart({
  days = 30,
  windowDays = 7,
}: AccuracyTrendChartProps) {
  const {
    data: trend,
    loading,
    error,
    refresh: refetch,
  } = usePoll(
    useCallback(() => api.learningAccuracyTrend(days, windowDays), [days, windowDays]),
    600_000 // 10 minutes
  );

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  };

  const getAccuracyColor = (accuracy: number) => {
    if (accuracy >= 0.8) return "bg-emerald-500/20 text-emerald-400";
    if (accuracy >= 0.6) return "bg-amber-500/20 text-amber-400";
    return "bg-red-500/20 text-red-400";
  };

  // Calculate min/max for visualization
  const minAccuracy = trend?.length
    ? Math.min(...trend.map((t) => t.accuracy))
    : 0;
  const maxAccuracy = trend?.length
    ? Math.max(...trend.map((t) => t.accuracy))
    : 1;
  const range = maxAccuracy - minAccuracy || 0.1;

  // Calculate overall trend
  const overallTrend =
    trend && trend.length >= 2
      ? trend[trend.length - 1].accuracy - trend[0].accuracy
      : null;

  const menuItems = [
    {
      label: "Refresh Trend",
      onClick: refetch,
    },
  ];

  const stickyHeader = (
    <div className="space-y-3">
      {trend && trend.length > 0 && (
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-zinc-800/50 rounded p-2">
            <div className="text-zinc-400">Latest Accuracy</div>
            <div className="text-lg font-semibold text-emerald-400">
              {(trend[trend.length - 1].accuracy * 100).toFixed(1)}%
            </div>
          </div>
          <div
            className={
              overallTrend !== null && overallTrend >= 0
                ? "bg-emerald-500/10 rounded p-2"
                : "bg-red-500/10 rounded p-2"
            }
          >
            <div className="text-zinc-400">Trend</div>
            <div
              className={`text-lg font-semibold flex items-center gap-1 ${
                overallTrend !== null && overallTrend >= 0
                  ? "text-emerald-400"
                  : "text-red-400"
              }`}
            >
              {overallTrend !== null && overallTrend >= 0 ? (
                <TrendingUp className="w-4 h-4" />
              ) : (
                <TrendingDown className="w-4 h-4" />
              )}
              {overallTrend !== null
                ? `${overallTrend >= 0 ? "+" : ""}${(overallTrend * 100).toFixed(1)}%`
                : "N/A"}
            </div>
          </div>
        </div>
      )}

      <div className="flex justify-between items-center">
        <span className="text-xs text-zinc-400">
          {trend?.length || 0} data points ({windowDays}-day windows)
        </span>
      </div>
    </div>
  );

  return (
    <ScrollableCard
      title="Accuracy Trend"
      icon={<TrendingUp className="w-4 h-4" />}
      stickyHeader={stickyHeader}
      menuItems={menuItems}
    >
      {loading && trend === undefined && (
        <p className="text-xs text-zinc-500 text-center py-8">Loading trend...</p>
      )}

      {error && (
        <div className="text-xs text-red-400 text-center py-8">
          Error loading trend: {error.message}
        </div>
      )}

      {trend && trend.length === 0 && (
        <div className="text-xs text-zinc-500 text-center py-8">
          Not enough feedback data yet
          <div className="mt-1 text-xs text-zinc-600">
            Need at least 3 feedback items per {windowDays}-day window
          </div>
        </div>
      )}

      {trend && trend.length > 0 && (
        <div className="space-y-3">
          {/* Simple bar chart visualization */}
          <div className="space-y-1">
            {trend.map((window, idx) => (
              <div key={window.date} className="space-y-1">
                {/* Date label */}
                <div className="flex justify-between items-center text-xs">
                  <span className="text-zinc-500">
                    {formatDate(window.window_start)}
                  </span>
                  <span className={getAccuracyColor(window.accuracy)}>
                    {(window.accuracy * 100).toFixed(1)}%
                  </span>
                </div>

                {/* Accuracy bar */}
                <div className="h-6 bg-zinc-800 rounded overflow-hidden">
                  <div
                    className={`h-full ${getAccuracyColor(window.accuracy)} flex items-center justify-end pr-2 transition-all`}
                    style={{ width: `${window.accuracy * 100}%` }}
                  >
                    {window.accuracy >= 0.3 && (
                      <span className="text-xs font-semibold">
                        {window.correct_predictions}/{window.total_feedback}
                      </span>
                    )}
                  </div>
                </div>

                {/* Feedback count below bar for low accuracy */}
                {window.accuracy < 0.3 && (
                  <div className="text-xs text-zinc-500 pl-1">
                    {window.correct_predictions}/{window.total_feedback}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Summary */}
          {trend.length >= 2 && (
            <div className="pt-3 border-t border-zinc-800">
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div>
                  <div className="text-zinc-500">First Window</div>
                  <div className="font-semibold">
                    {(trend[0].accuracy * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-zinc-500">Latest Window</div>
                  <div className="font-semibold">
                    {(trend[trend.length - 1].accuracy * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-zinc-500">Change</div>
                  <div
                    className={`font-semibold ${
                      overallTrend !== null && overallTrend >= 0
                        ? "text-emerald-400"
                        : "text-red-400"
                    }`}
                  >
                    {overallTrend !== null
                      ? `${overallTrend >= 0 ? "+" : ""}${(overallTrend * 100).toFixed(1)}%`
                      : "N/A"}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </ScrollableCard>
  );
}
