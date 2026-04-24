"use client";

import { usePoll } from "@/lib/polling";
import { api, HealthAuditSummary } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Activity, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { useCallback } from "react";

export function HealthAuditCard() {
  const { data, loading, error, refresh } = usePoll<HealthAuditSummary>(
    () => api.healthAuditAll(),
    300_000 // 5 minutes
  );

  const handleRunAudit = useCallback(async () => {
    try {
      await api.healthAuditAll();
      refresh();
    } catch (err) {
      console.error("Failed to run health audit:", err);
    }
  }, [refresh]);

  const menuItems = [
    { label: "Refresh", onClick: refresh },
    { label: "Run Audit", onClick: handleRunAudit }
  ];

  const healthColors = {
    green: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    yellow: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    red: "bg-red-500/20 text-red-400 border-red-500/30",
    unknown: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
  };

  const healthIcons = {
    green: CheckCircle2,
    yellow: AlertTriangle,
    red: XCircle,
    unknown: Activity,
  };

  return (
    <ScrollableCard
      title="Context Health Audit"
      icon={<Activity className="w-4 h-4" />}
      menuItems={menuItems}
    >
      {loading && !data && (
        <div className="flex items-center justify-center py-8">
          <p className="text-xs text-zinc-500">Loading health audit...</p>
        </div>
      )}

      {error && (
        <div className="p-4 rounded border border-red-800 bg-red-900/20">
          <p className="text-xs text-red-400">Failed to load health audit</p>
        </div>
      )}

      {data && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="p-3 rounded border border-zinc-800 bg-zinc-900/50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-zinc-200">Total Contexts</span>
              <Badge variant="outline" className="text-[10px]">
                {data.total_contexts}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-zinc-500">Audited</span>
              <span className="text-xs text-emerald-400">{data.audited}</span>
            </div>
          </div>

          {/* Health Distribution */}
          <div className="space-y-2">
            <h3 className="text-xs font-medium text-zinc-400 uppercase tracking-wide">
              Health Distribution
            </h3>

            {(["green", "yellow", "red", "unknown"] as const).map((status) => {
              const Icon = healthIcons[status];
              const count = data.health_distribution[status];
              const percentage =
                data.total_contexts > 0
                  ? ((count / data.total_contexts) * 100).toFixed(1)
                  : "0.0";

              return (
                <div
                  key={status}
                  className="p-3 rounded border border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800/50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className={`${healthColors[status]} text-[10px] px-1.5 py-0 flex items-center gap-1`}
                      >
                        <Icon className="w-3 h-3" />
                        {status}
                      </Badge>
                      <span className="text-xs text-zinc-500">
                        {count} contexts
                      </span>
                    </div>
                    <span className="text-xs text-zinc-400">{percentage}%</span>
                  </div>

                  {/* Progress bar */}
                  <div className="mt-2 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${
                        status === "green"
                          ? "bg-emerald-500"
                          : status === "yellow"
                          ? "bg-amber-500"
                          : status === "red"
                          ? "bg-red-500"
                          : "bg-zinc-500"
                      }`}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Actions */}
          <div className="pt-2 border-t border-zinc-800">
            <Button
              size="sm"
              variant="outline"
              onClick={handleRunAudit}
              className="w-full text-xs"
            >
              <Activity className="w-3 h-3 mr-2" />
              Run Full Audit
            </Button>
          </div>
        </div>
      )}
    </ScrollableCard>
  );
}
