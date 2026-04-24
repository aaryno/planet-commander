"use client";

import { AlertTriangle } from "lucide-react";
import { TemporalKeyHealth, TemporalUnanswered, TemporalMRsResponse } from "@/lib/api";

interface NeedsAttentionProps {
  keys: TemporalKeyHealth | null;
  slack: TemporalUnanswered | null;
  mrs: TemporalMRsResponse | null;
}

interface AlertItem {
  severity: "red" | "yellow";
  text: string;
}

export function NeedsAttentionBanner({ keys, slack, mrs }: NeedsAttentionProps) {
  const alerts: AlertItem[] = [];

  if (keys) {
    if (keys.expired_count > 0) {
      alerts.push({ severity: "red", text: `${keys.expired_count} API key${keys.expired_count > 1 ? "s" : ""} expired` });
    }
    if (keys.expiring_count > 0) {
      alerts.push({ severity: "yellow", text: `${keys.expiring_count} API key${keys.expiring_count > 1 ? "s" : ""} expiring within 14 days` });
    }
    if (keys.inventory_age_days > 7) {
      alerts.push({ severity: "yellow", text: `Key inventory is ${Math.round(keys.inventory_age_days)}d old (stale)` });
    }
  }

  if (slack && slack.total > 0) {
    const oldest = Math.max(...slack.unanswered.map(m => m.age_hours));
    const ageText = oldest < 24 ? `${Math.round(oldest)}h` : `${Math.round(oldest / 24)}d`;
    alerts.push({
      severity: oldest > 24 ? "red" : "yellow",
      text: `${slack.total} unanswered Slack question${slack.total > 1 ? "s" : ""} (oldest: ${ageText})`,
    });
  }

  if (mrs?.main_pipeline?.status === "failed") {
    alerts.push({ severity: "red", text: "Pipeline FAILED on main" });
  }

  if (alerts.length === 0) return null;

  return (
    <div className="rounded-lg border border-yellow-600/30 bg-yellow-600/5 p-3 space-y-1">
      <div className="flex items-center gap-2 text-xs font-medium text-yellow-400">
        <AlertTriangle className="h-3.5 w-3.5" />
        Needs Attention
      </div>
      {alerts.map((alert, i) => (
        <div key={i} className="flex items-center gap-2 text-xs ml-5">
          <span className={`inline-block w-1.5 h-1.5 rounded-full ${
            alert.severity === "red" ? "bg-red-400" : "bg-yellow-400"
          }`} />
          <span className="text-zinc-300">{alert.text}</span>
        </div>
      ))}
    </div>
  );
}
