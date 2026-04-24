import { Badge } from "@/components/ui/badge";
import { ExternalLink, AlertTriangle, BookOpen, Calendar } from "lucide-react";
import type { GrafanaAlertDefinition } from "@/lib/api";

interface AlertDefinitionCardProps {
  alert: GrafanaAlertDefinition;
  showQuery?: boolean;
}

export function AlertDefinitionCard({ alert, showQuery = false }: AlertDefinitionCardProps) {
  const severityColor = {
    critical: "bg-red-500/20 text-red-400",
    warning: "bg-amber-500/20 text-amber-400",
    info: "bg-blue-500/20 text-blue-400",
  }[alert.severity || ""] || "bg-zinc-500/20 text-zinc-400";

  // Format last synced date
  const syncedDate = new Date(alert.last_synced_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="p-3 rounded border border-zinc-800 hover:border-zinc-700 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <AlertTriangle className="w-4 h-4 text-zinc-500 flex-shrink-0" />
          <h4 className="text-sm font-medium text-zinc-200 truncate">
            {alert.alert_name}
          </h4>
        </div>
        {alert.runbook_url && (
          <a
            href={alert.runbook_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-zinc-500 hover:text-zinc-400 flex-shrink-0"
            title="Open runbook"
          >
            <BookOpen className="w-4 h-4" />
          </a>
        )}
      </div>

      {/* Summary */}
      {alert.summary && (
        <p className="text-xs text-zinc-400 mt-1">{alert.summary}</p>
      )}

      {/* Badges */}
      <div className="flex items-center gap-2 mt-2 flex-wrap">
        {alert.severity && (
          <Badge className={severityColor}>{alert.severity}</Badge>
        )}
        {alert.team && (
          <Badge variant="outline" className="text-xs">{alert.team}</Badge>
        )}
        {alert.project && (
          <Badge variant="outline" className="text-xs">{alert.project}</Badge>
        )}
        {alert.alert_for && (
          <span className="text-xs text-zinc-500">for {alert.alert_for}</span>
        )}
        {!alert.is_active && (
          <Badge variant="outline" className="text-xs text-red-400">inactive</Badge>
        )}
      </div>

      {/* Metadata */}
      <div className="flex items-center gap-3 mt-2 text-xs text-zinc-500">
        <div className="flex items-center gap-1">
          <Calendar className="w-3 h-3" />
          <span>Synced {syncedDate}</span>
        </div>
        {alert.has_runbook && (
          <span className="text-emerald-400">Has runbook</span>
        )}
      </div>

      {/* Query (expandable) */}
      {showQuery && alert.alert_expr && (
        <div className="mt-2">
          <div className="text-xs text-zinc-500 mb-1">Query:</div>
          <pre className="text-xs bg-zinc-900 p-2 rounded overflow-x-auto">
            <code className="text-zinc-300">{alert.alert_expr}</code>
          </pre>
        </div>
      )}

      {/* Labels (if any non-standard) */}
      {alert.labels && Object.keys(alert.labels).length > 0 && (
        <div className="mt-2">
          <div className="flex items-center gap-1 flex-wrap">
            {Object.entries(alert.labels)
              .filter(([key]) => key !== "severity" && key !== "team") // Skip already displayed
              .slice(0, 3)
              .map(([key, value]) => (
                <span
                  key={key}
                  className="text-xs text-zinc-500 bg-zinc-800/50 px-1.5 py-0.5 rounded"
                >
                  {key}={value}
                </span>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
