"use client";

import { useCallback } from "react";
import {
  Server,
  Zap,
  Database,
  Layers,
  Activity,
  AlertTriangle,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toFixed(0);
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${ok ? "bg-emerald-400" : "bg-red-400"}`}
    />
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function InfrastructurePage() {
  const fetcher = useCallback(() => api.infraOverview(6), []);
  const { data, loading, error } = usePoll(fetcher, 60_000);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <Activity className="h-6 w-6 text-zinc-500 animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 text-red-400 text-sm">
        Failed to load infrastructure data: {error.message}
      </div>
    );
  }

  if (!data) return null;

  const preemptionTotal = data.preemption.total_hr;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Server className="h-6 w-6 text-orange-400" />
        <h1 className="text-xl font-bold text-zinc-100">Infrastructure</h1>
        <Badge variant="outline" className="text-[10px] text-zinc-500 border-zinc-700">
          {new Date(data.timestamp).toLocaleTimeString()}
        </Badge>
      </div>

      {/* Top-level stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          label="Preemptions/hr"
          value={fmt(preemptionTotal)}
          icon={Zap}
          color="text-red-400"
          bgColor="bg-red-500/10"
          detail={`${data.preemption.zones.length} zones`}
        />
        <StatCard
          label="G4 Pool"
          value={fmt(data.g4_total_pool)}
          icon={Database}
          color="text-violet-400"
          bgColor="bg-violet-500/10"
          detail={`${data.g4_scale.length} clusters`}
        />
        <StatCard
          label="K8s Nodes"
          value={fmt(data.k8s_total_nodes)}
          icon={Layers}
          color="text-blue-400"
          bgColor="bg-blue-500/10"
          detail={`${data.k8s_clusters.length} clusters`}
        />
        <StatCard
          label="Pipeline/hr"
          value={fmt(data.pipeline_throughput_hr)}
          icon={Activity}
          color="text-emerald-400"
          bgColor="bg-emerald-500/10"
          detail={`${fmt(data.jobs_queue.total_queued)} queued`}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Preemption */}
        <ScrollableCard
          title="GCE Preemptions"
          icon={<Zap className="h-4 w-4 text-red-400" />}
        >
          <div className="space-y-2 p-4">
            <div className="flex items-center justify-between text-xs text-zinc-500 mb-3">
              <span>Zone</span>
              <span>Current/hr</span>
            </div>
            {data.preemption.zones
              .sort((a, b) => b.current_rate_hr - a.current_rate_hr)
              .map((zone) => (
                <div
                  key={zone.zone}
                  className="flex items-center justify-between py-1.5 border-b border-zinc-800/50 last:border-0"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-zinc-300 font-mono">
                      {zone.zone}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    {/* Sparkline-like bar */}
                    <div className="flex items-end gap-px h-4">
                      {zone.hourly_counts.slice(-6).map((pt, i) => {
                        const max = Math.max(
                          ...zone.hourly_counts.map((p) => p.count),
                          1,
                        );
                        const h = Math.max(2, (pt.count / max) * 16);
                        return (
                          <div
                            key={i}
                            className="w-1.5 rounded-t bg-red-500/60"
                            style={{ height: `${h}px` }}
                            title={`${pt.count.toLocaleString()} at ${new Date(pt.time).toLocaleTimeString()}`}
                          />
                        );
                      })}
                    </div>
                    <span
                      className={`text-sm font-medium tabular-nums w-16 text-right ${
                        zone.current_rate_hr > 10000
                          ? "text-red-400"
                          : zone.current_rate_hr > 1000
                            ? "text-amber-400"
                            : "text-zinc-300"
                      }`}
                    >
                      {fmt(zone.current_rate_hr)}
                    </span>
                  </div>
                </div>
              ))}
            <div className="flex items-center justify-between pt-2 border-t border-zinc-700">
              <span className="text-xs font-semibold text-zinc-400">Total</span>
              <span className="text-sm font-bold text-red-400">
                {fmt(preemptionTotal)}/hr
              </span>
            </div>
          </div>
        </ScrollableCard>

        {/* G4 Clusters */}
        <ScrollableCard
          title="G4 Clusters"
          icon={<Database className="h-4 w-4 text-violet-400" />}
        >
          <div className="space-y-2 p-4">
            <div className="flex items-center justify-between text-xs text-zinc-500 mb-3">
              <span>Cluster</span>
              <span className="flex gap-6">
                <span className="w-14 text-right">Pool</span>
                <span className="w-16 text-right">Tasks/hr</span>
              </span>
            </div>
            {data.g4_scale.map((c) => (
              <div
                key={c.cluster}
                className="flex items-center justify-between py-1.5 border-b border-zinc-800/50 last:border-0"
              >
                <div className="flex items-center gap-2">
                  <StatusDot ok={c.failure_rate_hr < c.success_rate_hr * 0.05} />
                  <span className="text-sm text-zinc-300 font-mono">
                    {c.cluster.replace("g4c-", "")}
                  </span>
                </div>
                <div className="flex items-center gap-6">
                  <span className="text-sm text-zinc-400 tabular-nums w-14 text-right">
                    {fmt(c.pool_size)}
                  </span>
                  <span className="text-sm text-zinc-300 tabular-nums w-16 text-right">
                    {fmt(c.success_rate_hr)}
                  </span>
                </div>
              </div>
            ))}
            <div className="flex items-center justify-between pt-2 border-t border-zinc-700">
              <span className="text-xs font-semibold text-zinc-400">Total</span>
              <span className="text-sm font-bold text-violet-400">
                {fmt(data.g4_total_pool)} pods
              </span>
            </div>
          </div>
        </ScrollableCard>

        {/* K8s Clusters */}
        <ScrollableCard
          title="K8s Clusters"
          icon={<Layers className="h-4 w-4 text-blue-400" />}
        >
          <div className="space-y-2 p-4">
            <div className="flex items-center justify-between text-xs text-zinc-500 mb-3">
              <span>Cluster</span>
              <span className="flex gap-6">
                <span className="w-12 text-right">Nodes</span>
                <span className="w-14 text-right">Pods</span>
              </span>
            </div>
            {data.k8s_clusters.slice(0, 15).map((c) => (
              <div
                key={c.cluster}
                className="flex items-center justify-between py-1.5 border-b border-zinc-800/50 last:border-0"
              >
                <span className="text-sm text-zinc-300 font-mono truncate max-w-[180px]">
                  {c.cluster}
                </span>
                <div className="flex items-center gap-6">
                  <span className="text-sm text-zinc-400 tabular-nums w-12 text-right">
                    {c.nodes}
                  </span>
                  <span className="text-sm text-zinc-300 tabular-nums w-14 text-right">
                    {c.pods != null ? fmt(c.pods) : "-"}
                  </span>
                </div>
              </div>
            ))}
            {data.k8s_clusters.length > 15 && (
              <p className="text-[10px] text-zinc-600 text-center pt-1">
                +{data.k8s_clusters.length - 15} more clusters
              </p>
            )}
            <div className="flex items-center justify-between pt-2 border-t border-zinc-700">
              <span className="text-xs font-semibold text-zinc-400">Total</span>
              <span className="text-sm font-bold text-blue-400">
                {fmt(data.k8s_total_nodes)} nodes
              </span>
            </div>
          </div>
        </ScrollableCard>

        {/* Jobs Queue */}
        <ScrollableCard
          title="Jobs Queue"
          icon={<Activity className="h-4 w-4 text-emerald-400" />}
        >
          <div className="space-y-2 p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs text-zinc-500">Total Queued</span>
              <span className="text-lg font-bold text-zinc-200">
                {fmt(data.jobs_queue.total_queued)}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs text-zinc-500 mb-2">
              <span>Top Programs</span>
              <span>Queued</span>
            </div>
            {data.jobs_queue.top_programs.map((p) => (
              <div
                key={p.program}
                className="flex items-center justify-between py-1 border-b border-zinc-800/50 last:border-0"
              >
                <span className="text-sm text-zinc-300 font-mono truncate max-w-[200px]">
                  {p.program}
                </span>
                <div className="flex items-center gap-2">
                  <div
                    className="h-1.5 rounded bg-emerald-500/40"
                    style={{
                      width: `${Math.min(100, (p.queued / (data.jobs_queue.top_programs[0]?.queued || 1)) * 80)}px`,
                    }}
                  />
                  <span className="text-sm text-zinc-400 tabular-nums w-14 text-right">
                    {fmt(p.queued)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </ScrollableCard>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StatCard
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  icon: Icon,
  color,
  bgColor,
  detail,
}: {
  label: string;
  value: string;
  icon: typeof Server;
  color: string;
  bgColor: string;
  detail?: string;
}) {
  return (
    <div className={`rounded-lg border border-zinc-800 ${bgColor} p-4`}>
      <div className="flex items-center gap-2 mb-1">
        <Icon className={`h-4 w-4 ${color}`} />
        <span className="text-xs text-zinc-500">{label}</span>
      </div>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      {detail && <p className="text-[10px] text-zinc-600 mt-0.5">{detail}</p>}
    </div>
  );
}
