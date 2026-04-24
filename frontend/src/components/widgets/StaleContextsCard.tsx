"use client";

import { usePoll } from "@/lib/polling";
import { api, StaleContext } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Clock, AlertTriangle } from "lucide-react";
import { useCallback, useState } from "react";

export function StaleContextsCard() {
  const [daysThreshold, setDaysThreshold] = useState(30);

  const { data, loading, error, refresh } = usePoll<{
    stale_contexts: StaleContext[];
    days_threshold: number;
  }>(
    () => api.healthStaleContexts(daysThreshold),
    300_000 // 5 minutes
  );

  const handleMarkOrphaned = useCallback(async () => {
    try {
      await api.healthMarkOrphaned(60);
      refresh();
    } catch (err) {
      console.error("Failed to mark orphaned:", err);
    }
  }, [refresh]);

  const menuItems = [
    { label: "Refresh", onClick: refresh },
    { label: "Mark Orphaned (60d)", onClick: handleMarkOrphaned },
  ];

  const staleContexts = data?.stale_contexts || [];

  return (
    <ScrollableCard
      title="Stale Contexts"
      icon={<Clock className="w-4 h-4" />}
      menuItems={menuItems}
      stickyHeader={
        <div className="flex items-center justify-between">
          <span className="text-xs text-zinc-500">
            No updates in {daysThreshold}+ days
          </span>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant={daysThreshold === 7 ? "default" : "outline"}
              onClick={() => setDaysThreshold(7)}
              className="h-6 text-[10px] px-2"
            >
              7d
            </Button>
            <Button
              size="sm"
              variant={daysThreshold === 30 ? "default" : "outline"}
              onClick={() => setDaysThreshold(30)}
              className="h-6 text-[10px] px-2"
            >
              30d
            </Button>
            <Button
              size="sm"
              variant={daysThreshold === 60 ? "default" : "outline"}
              onClick={() => setDaysThreshold(60)}
              className="h-6 text-[10px] px-2"
            >
              60d
            </Button>
          </div>
        </div>
      }
    >
      {loading && !staleContexts.length && (
        <div className="flex items-center justify-center py-8">
          <p className="text-xs text-zinc-500">Loading stale contexts...</p>
        </div>
      )}

      {error && (
        <div className="p-4 rounded border border-red-800 bg-red-900/20">
          <p className="text-xs text-red-400">Failed to load stale contexts</p>
        </div>
      )}

      {staleContexts.length === 0 && !loading && (
        <div className="text-center py-8">
          <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
          <p className="text-sm text-zinc-500">No stale contexts</p>
          <p className="text-xs text-zinc-600 mt-1">
            All contexts updated recently
          </p>
        </div>
      )}

      {staleContexts.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs text-zinc-500">
              {staleContexts.length} stale context{staleContexts.length !== 1 ? "s" : ""}
            </p>
            <Badge
              variant="outline"
              className="bg-amber-500/20 text-amber-400 border-amber-500/30 text-[10px]"
            >
              <AlertTriangle className="w-3 h-3 mr-1" />
              Needs Review
            </Badge>
          </div>

          {staleContexts.map((ctx) => (
            <div
              key={ctx.id}
              className="p-3 rounded border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/15 transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm text-zinc-200 truncate">
                      {ctx.title}
                    </span>
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0 shrink-0">
                      {ctx.status}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-3 text-[10px] text-zinc-500">
                    <span>
                      <Clock className="w-3 h-3 inline mr-1" />
                      {ctx.days_since_update} days ago
                    </span>
                    <span className="text-zinc-600">
                      {new Date(ctx.last_updated).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </ScrollableCard>
  );
}

// Add missing import
import { CheckCircle2 } from "lucide-react";
