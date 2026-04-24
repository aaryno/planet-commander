"use client";

import { useEffect, useState } from "react";
import { FileText, AlertOctagon, TrendingUp } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Badge } from "@/components/ui/badge";
import { api, WarningEvent, StandbyContext } from "@/lib/api";

interface StandbyContextViewerProps {
  warning: WarningEvent;
}

export function StandbyContextViewer({ warning }: StandbyContextViewerProps) {
  const [standbyContext, setStandbyContext] = useState<StandbyContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (warning.has_standby_context && warning.id) {
      setLoading(true);
      setError(null);

      api
        .warningStandbyContext(warning.id)
        .then((context) => {
          setStandbyContext(context);
          setLoading(false);
        })
        .catch((err) => {
          setError(err.message);
          setLoading(false);
        });
    }
  }, [warning.id, warning.has_standby_context]);

  if (!warning.has_standby_context) {
    return (
      <ScrollableCard
        title="Standby Context"
        icon={<FileText className="w-4 h-4" />}
      >
        <div className="text-xs text-zinc-500 text-center py-8">
          <AlertOctagon className="w-8 h-8 mx-auto mb-2 text-zinc-600" />
          <p>No standby context available</p>
          <p className="mt-1 text-zinc-600">
            Escalation probability too low ({(warning.escalation_probability * 100).toFixed(0)}% &lt; 50%)
          </p>
        </div>
      </ScrollableCard>
    );
  }

  return (
    <ScrollableCard
      title={`Standby Context: ${warning.alert_name}`}
      icon={<FileText className="w-4 h-4" />}
    >
      {loading && (
        <p className="text-xs text-zinc-500 text-center py-8">
          Loading standby context...
        </p>
      )}

      {error && (
        <div className="text-xs text-red-400 text-center py-8">
          Error loading context: {error}
        </div>
      )}

      {standbyContext && (
        <div className="space-y-4">
          {/* Summary */}
          <div>
            <h3 className="text-sm font-semibold text-zinc-300 mb-2">Summary</h3>
            <div className="bg-zinc-800/50 rounded p-3 text-xs text-zinc-300 whitespace-pre-wrap">
              {standbyContext.summary_text || "No summary available"}
            </div>
          </div>

          {/* Pre-Assembled Components */}
          <div>
            <h3 className="text-sm font-semibold text-zinc-300 mb-2">
              Pre-Assembled Components
            </h3>
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-blue-500/10 rounded p-3 border border-blue-500/20">
                <div className="text-xs text-zinc-400 mb-1">Artifacts Linked</div>
                <div className="text-lg font-semibold text-blue-400">
                  {standbyContext.artifact_count}
                </div>
                <div className="text-xs text-zinc-500 mt-1">
                  Similar investigations
                </div>
              </div>

              <div className="bg-amber-500/10 rounded p-3 border border-amber-500/20">
                <div className="text-xs text-zinc-400 mb-1">Alert Definitions</div>
                <div className="text-lg font-semibold text-amber-400">
                  {standbyContext.alert_definition_count}
                </div>
                <div className="text-xs text-zinc-500 mt-1">
                  Runbooks & queries
                </div>
              </div>
            </div>
          </div>

          {/* Health Status */}
          <div>
            <h3 className="text-sm font-semibold text-zinc-300 mb-2">Health Status</h3>
            <Badge className={getHealthColor(standbyContext.health_status)}>
              {standbyContext.health_status.toUpperCase()}
            </Badge>
          </div>

          {/* Created At */}
          <div className="text-xs text-zinc-500">
            Created: {new Date(standbyContext.created_at).toLocaleString()}
          </div>

          {/* Action Buttons */}
          <div className="pt-4 border-t border-zinc-800 space-y-2">
            {warning.escalated ? (
              <div className="flex items-center gap-2 text-xs text-red-400">
                <TrendingUp className="w-4 h-4" />
                <span>Warning has escalated to critical</span>
              </div>
            ) : (
              <p className="text-xs text-zinc-500">
                This context is ready to activate if warning escalates to critical.
              </p>
            )}
          </div>

          {/* Future: Link to full work context */}
          {standbyContext.id && (
            <div className="pt-2">
              <a
                href={`/context/${standbyContext.id}`}
                className="text-xs text-blue-400 hover:text-blue-300"
              >
                View Full Work Context →
              </a>
            </div>
          )}
        </div>
      )}
    </ScrollableCard>
  );
}

function getHealthColor(health: string): string {
  switch (health.toLowerCase()) {
    case "green":
      return "text-emerald-400 bg-emerald-500/20";
    case "yellow":
      return "text-amber-400 bg-amber-500/20";
    case "red":
      return "text-red-400 bg-red-500/20";
    default:
      return "text-zinc-400 bg-zinc-500/20";
  }
}
