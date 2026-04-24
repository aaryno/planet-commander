"use client";

import { useCallback } from "react";
import { Key, AlertTriangle, CheckCircle, Clock } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { usePoll } from "@/lib/polling";
import { api, TemporalKeyHealth, TemporalKeyInfo } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

function StatusBadge({ status }: { status: string }) {
  if (status === "expired") {
    return <Badge variant="destructive" className="text-[10px] px-1.5 py-0">EXPIRED</Badge>;
  }
  if (status === "expiring") {
    return <Badge className="bg-yellow-600/20 text-yellow-400 border-yellow-600/30 text-[10px] px-1.5 py-0">EXPIRING</Badge>;
  }
  return <Badge className="bg-emerald-600/20 text-emerald-400 border-emerald-600/30 text-[10px] px-1.5 py-0">OK</Badge>;
}

function KeyRow({ k }: { k: TemporalKeyInfo }) {
  const daysText = k.days_until < 0
    ? `${Math.abs(Math.round(k.days_until))}d ago`
    : `${Math.round(k.days_until)}d`;

  return (
    <div className="flex items-center justify-between py-1 text-xs">
      <div className="flex items-center gap-2 min-w-0">
        <StatusBadge status={k.status} />
        <span className="text-zinc-300 truncate" title={k.key_name}>
          {k.tenant}
          <span className="text-zinc-500">-{k.color}</span>
          {k.is_current && <span className="text-zinc-500 ml-1">(active)</span>}
        </span>
      </div>
      <span className={`font-mono text-xs ml-2 whitespace-nowrap ${
        k.status === "expired" ? "text-red-400" :
        k.status === "expiring" ? "text-yellow-400" :
        "text-zinc-500"
      }`}>
        {daysText}
      </span>
    </div>
  );
}

export function KeyHealth() {
  const fetcher = useCallback(() => api.temporalKeys(), []);
  const { data, loading, error } = usePoll<TemporalKeyHealth>(fetcher, 3600_000);

  const alertCount = (data?.expired_count ?? 0) + (data?.expiring_count ?? 0);

  return (
    <ScrollableCard
      title={`Key Health${alertCount > 0 ? ` (${alertCount})` : ""}`}
      icon={<Key className="h-4 w-4" />}
    >
      {loading && <p className="text-xs text-zinc-500">Loading...</p>}
      {error && <p className="text-xs text-red-400">Failed to load key data</p>}
      {data && (
        <div className="space-y-2">
          {/* Summary badges */}
          <div className="flex gap-2 text-xs">
            {data.expired_count > 0 && (
              <span className="flex items-center gap-1 text-red-400">
                <AlertTriangle className="h-3 w-3" />
                {data.expired_count} expired
              </span>
            )}
            {data.expiring_count > 0 && (
              <span className="flex items-center gap-1 text-yellow-400">
                <Clock className="h-3 w-3" />
                {data.expiring_count} expiring
              </span>
            )}
            {data.expired_count === 0 && data.expiring_count === 0 && (
              <span className="flex items-center gap-1 text-emerald-400">
                <CheckCircle className="h-3 w-3" />
                All keys healthy
              </span>
            )}
          </div>

          {/* Key list - show expired and expiring first, then collapsed ok */}
          <div className="space-y-0.5">
            {data.keys
              .filter(k => k.status !== "ok")
              .map((k) => <KeyRow key={k.key_name} k={k} />)
            }
            {data.keys.filter(k => k.status === "ok").length > 0 && (
              <details className="mt-2">
                <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-400">
                  {data.ok_count} healthy keys
                </summary>
                <div className="mt-1 space-y-0.5">
                  {data.keys
                    .filter(k => k.status === "ok")
                    .map((k) => <KeyRow key={k.key_name} k={k} />)
                  }
                </div>
              </details>
            )}
          </div>

          {/* Inventory freshness */}
          <div className="text-[10px] pt-1 border-t border-zinc-800">
            {data.inventory_age_days > 7 ? (
              <span className="text-yellow-500">
                inventory.eap.json is {Math.round(data.inventory_age_days)}d old — git pull temporalio-cloud to refresh
              </span>
            ) : (
              <span className="text-zinc-600">
                Inventory updated {data.inventory_age_days < 1
                  ? "today"
                  : `${Math.round(data.inventory_age_days)}d ago`}
              </span>
            )}
          </div>
        </div>
      )}
    </ScrollableCard>
  );
}
