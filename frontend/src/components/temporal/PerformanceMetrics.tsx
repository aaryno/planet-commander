"use client";

import { useCallback } from "react";
import { Activity, CheckCircle, AlertTriangle } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { usePoll } from "@/lib/polling";
import { api, TemporalPerformance } from "@/lib/api";

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

function MetricRow({ label, value, unit, ok }: { label: string; value: string | null; unit?: string; ok?: boolean }) {
  return (
    <div className="flex items-center justify-between py-1 text-xs">
      <span className="text-zinc-400">{label}</span>
      <div className="flex items-center gap-1.5">
        <span className="text-zinc-200 font-mono">
          {value ?? "N/A"}{unit && value ? unit : ""}
        </span>
        {ok !== undefined && (
          ok
            ? <CheckCircle className="h-3 w-3 text-emerald-400" />
            : <AlertTriangle className="h-3 w-3 text-yellow-400" />
        )}
      </div>
    </div>
  );
}

export function PerformanceMetrics() {
  const fetcher = useCallback(() => api.temporalPerformance(), []);
  const { data, loading, error } = usePoll<TemporalPerformance>(fetcher, 60_000);

  return (
    <ScrollableCard
      title="Performance"
      icon={<Activity className="h-4 w-4" />}
    >
      {loading && <p className="text-xs text-zinc-500">Loading...</p>}
      {error && <p className="text-xs text-red-400">Failed to load metrics (VPN?)</p>}
      {data && (
        <div className="space-y-0.5">
          <MetricRow
            label="Workflow Success Rate"
            value={data.workflow_success_rate?.toString() ?? null}
            unit="%"
            ok={data.workflow_success_rate === null || data.workflow_success_rate > 95}
          />
          <MetricRow
            label="Completions/hr"
            value={data.workflow_completions_per_hour?.toString() ?? null}
          />
          <MetricRow
            label="Failures/hr"
            value={data.workflow_failures_per_hour?.toString() ?? null}
            ok={data.workflow_failures_per_hour === null || data.workflow_failures_per_hour < 10}
          />
          <MetricRow
            label="Activity Failures/hr"
            value={formatNumber(data.activity_failures_per_hour)}
          />
          {data.activity_failures_by_service && data.activity_failures_by_service.length > 0 && (
            <details className="mt-1">
              <summary className="text-[10px] text-zinc-500 cursor-pointer hover:text-zinc-400">
                Breakdown by service
              </summary>
              <div className="mt-1 space-y-0.5 ml-2">
                {data.activity_failures_by_service.map((s) => (
                  <div key={s.service} className="flex justify-between text-[10px]">
                    <span className="text-zinc-500 truncate">{s.service}</span>
                    <span className="text-zinc-400 font-mono ml-2">{formatNumber(s.failures_per_hour)}/hr</span>
                  </div>
                ))}
              </div>
            </details>
          )}
          <div className="pt-1 border-t border-zinc-800 mt-1">
            <span className={`text-[10px] ${data.status === "healthy" ? "text-emerald-400" : "text-yellow-400"}`}>
              Status: {data.status}
            </span>
          </div>
        </div>
      )}
    </ScrollableCard>
  );
}
