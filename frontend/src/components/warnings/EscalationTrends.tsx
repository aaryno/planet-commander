"use client";

import { useCallback } from "react";
import { TrendingUp, TrendingDown } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { usePoll } from "@/lib/polling";
import { api, EscalationTrends as TrendsData } from "@/lib/api";

interface EscalationTrendsProps {
  days?: number;
}

export function EscalationTrends({ days = 7 }: EscalationTrendsProps) {
  const {
    data: trends,
    loading,
    error,
    refresh: refetch,
  } = usePoll(
    useCallback(() => api.escalationTrends(days), [days]),
    300_000 // 5 minutes
  );

  const getMaxValue = () => {
    if (!trends) return 0;
    return Math.max(
      ...trends.trends.map((t) => Math.max(t.warnings, t.escalated, t.auto_cleared))
    );
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  const menuItems = [
    {
      label: "Refresh",
      onClick: refetch,
    },
  ];

  return (
    <ScrollableCard
      title="Escalation Trends"
      icon={<TrendingUp className="w-4 h-4" />}
      menuItems={menuItems}
    >
      {loading && !trends && (
        <p className="text-xs text-zinc-500 text-center py-8">Loading trends...</p>
      )}

      {error && (
        <div className="text-xs text-red-400 text-center py-8">
          Error loading trends: {error.message}
        </div>
      )}

      {trends && trends.trends.length === 0 && (
        <p className="text-xs text-zinc-500 text-center py-8">
          No data available for the selected period
        </p>
      )}

      {trends && trends.trends.length > 0 && (
        <div className="space-y-4">
          {/* Legend */}
          <div className="flex gap-4 text-xs">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-amber-500" />
              <span className="text-zinc-400">Warnings</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-red-500" />
              <span className="text-zinc-400">Escalated</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-emerald-500" />
              <span className="text-zinc-400">Cleared</span>
            </div>
          </div>

          {/* Chart */}
          <div className="space-y-2">
            {trends.trends.map((point, index) => (
              <TrendBar
                key={point.date}
                date={point.date}
                warnings={point.warnings}
                escalated={point.escalated}
                autoCleared={point.auto_cleared}
                maxValue={getMaxValue()}
                formatDate={formatDate}
                isFirst={index === 0}
                isLast={index === trends.trends.length - 1}
              />
            ))}
          </div>

          {/* Summary Stats */}
          <div className="pt-4 border-t border-zinc-800 grid grid-cols-3 gap-2 text-xs">
            <div>
              <div className="text-zinc-500">Total Warnings</div>
              <div className="text-lg font-semibold text-amber-400">
                {trends.trends.reduce((sum, t) => sum + t.warnings, 0)}
              </div>
            </div>
            <div>
              <div className="text-zinc-500">Escalated</div>
              <div className="text-lg font-semibold text-red-400">
                {trends.trends.reduce((sum, t) => sum + t.escalated, 0)}
              </div>
            </div>
            <div>
              <div className="text-zinc-500">Cleared</div>
              <div className="text-lg font-semibold text-emerald-400">
                {trends.trends.reduce((sum, t) => sum + t.auto_cleared, 0)}
              </div>
            </div>
          </div>
        </div>
      )}
    </ScrollableCard>
  );
}

interface TrendBarProps {
  date: string;
  warnings: number;
  escalated: number;
  autoCleared: number;
  maxValue: number;
  formatDate: (date: string) => string;
  isFirst: boolean;
  isLast: boolean;
}

function TrendBar({
  date,
  warnings,
  escalated,
  autoCleared,
  maxValue,
  formatDate,
  isFirst,
  isLast,
}: TrendBarProps) {
  const getBarWidth = (value: number) => {
    if (maxValue === 0) return "0%";
    return `${(value / maxValue) * 100}%`;
  };

  return (
    <div className="space-y-1">
      <div className="flex justify-between items-baseline">
        <div className="text-xs text-zinc-400 w-16">
          {formatDate(date)}
          {isFirst && <span className="text-zinc-600 ml-1">(old)</span>}
          {isLast && <span className="text-zinc-600 ml-1">(new)</span>}
        </div>
        <div className="flex gap-2 text-xs text-zinc-500">
          <span>{warnings}w</span>
          <span className="text-red-400">{escalated}e</span>
          <span className="text-emerald-400">{autoCleared}c</span>
        </div>
      </div>

      {/* Stacked bar */}
      <div className="flex gap-0.5 h-6 bg-zinc-900 rounded overflow-hidden">
        {/* Warnings bar */}
        <div
          className="bg-amber-500/50 transition-all"
          style={{ width: getBarWidth(warnings) }}
          title={`${warnings} warnings`}
        />
        {/* Escalated bar */}
        <div
          className="bg-red-500/50 transition-all"
          style={{ width: getBarWidth(escalated) }}
          title={`${escalated} escalated`}
        />
        {/* Cleared bar */}
        <div
          className="bg-emerald-500/50 transition-all"
          style={{ width: getBarWidth(autoCleared) }}
          title={`${autoCleared} cleared`}
        />
      </div>
    </div>
  );
}
