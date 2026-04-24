"use client";

import { useCallback, useState } from "react";
import { AlertTriangle, TrendingUp, CheckCircle2, XCircle, Clock, AlertCircle } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { formatDuration } from "@/lib/time-utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { usePoll } from "@/lib/polling";
import { api, WarningEvent, WarningsSummary } from "@/lib/api";
import { FeedbackButtons } from "./FeedbackButtons";

interface WarningMonitorProps {
  activeOnly?: boolean;
  onSelectWarning?: (warning: WarningEvent) => void;
}

export function WarningMonitor({ activeOnly = true, onSelectWarning }: WarningMonitorProps) {
  const [selectedWarning, setSelectedWarning] = useState<WarningEvent | null>(null);

  const handleSelectWarning = (warning: WarningEvent) => {
    setSelectedWarning(warning);
    onSelectWarning?.(warning);
  };

  // Poll warnings every 30 seconds
  const {
    data: warnings,
    loading: warningsLoading,
    error: warningsError,
    refresh: refetchWarnings,
  } = usePoll(
    useCallback(() => api.warnings(activeOnly), [activeOnly]),
    30_000
  );

  // Poll summary every 30 seconds
  const {
    data: summary,
    loading: summaryLoading,
    error: summaryError,
  } = usePoll(
    useCallback(() => api.warningsSummary(), []),
    30_000
  );

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case "critical":
        return "text-red-400 bg-red-500/20";
      case "warning":
        return "text-amber-400 bg-amber-500/20";
      case "info":
        return "text-blue-400 bg-blue-500/20";
      default:
        return "text-zinc-400 bg-zinc-500/20";
    }
  };

  const getProbabilityColor = (probability: number) => {
    if (probability >= 0.75) return "text-red-400";
    if (probability >= 0.5) return "text-amber-400";
    if (probability >= 0.25) return "text-yellow-400";
    return "text-zinc-400";
  };

  const getProbabilityLabel = (probability: number) => {
    if (probability >= 0.75) return "HIGH";
    if (probability >= 0.5) return "MEDIUM";
    if (probability >= 0.25) return "LOW";
    return "VERY LOW";
  };

  const formatAge = (minutes: number) => formatDuration(minutes) || "0m";

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const stickyHeader = (
    <div className="space-y-3">
      {/* Summary Stats */}
      {summary && !summaryLoading && (
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-zinc-800/50 rounded p-2">
            <div className="text-zinc-400">Active</div>
            <div className="text-lg font-semibold">{summary.active_warnings}</div>
          </div>
          <div className="bg-red-500/10 rounded p-2">
            <div className="text-zinc-400">High Risk</div>
            <div className="text-lg font-semibold text-red-400">{summary.high_risk_warnings}</div>
          </div>
          <div className="bg-zinc-800/50 rounded p-2">
            <div className="text-zinc-400">Escalated Today</div>
            <div className="text-lg font-semibold">{summary.escalated_today}</div>
          </div>
          <div className="bg-emerald-500/10 rounded p-2">
            <div className="text-zinc-400">Cleared Today</div>
            <div className="text-lg font-semibold text-emerald-400">{summary.auto_cleared_today}</div>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="flex justify-between items-center">
        <span className="text-xs text-zinc-400">
          {warnings?.length || 0} warnings
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => refetchWarnings()}
          disabled={warningsLoading}
        >
          Refresh
        </Button>
      </div>
    </div>
  );

  const menuItems = [
    {
      label: "Refresh Warnings",
      onClick: refetchWarnings,
    },
  ];

  return (
    <ScrollableCard
      title="Warning Monitor"
      icon={<AlertTriangle className="w-4 h-4" />}
      stickyHeader={stickyHeader}
      menuItems={menuItems}
    >
      {warningsLoading && warnings === undefined && (
        <p className="text-xs text-zinc-500 text-center py-8">Loading warnings...</p>
      )}

      {warningsError && (
        <div className="text-xs text-red-400 text-center py-8">
          Error loading warnings: {warningsError.message}
        </div>
      )}

      {warnings && warnings.length === 0 && (
        <div className="text-xs text-zinc-500 text-center py-8">
          <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-emerald-500" />
          No active warnings
        </div>
      )}

      {warnings && warnings.length > 0 && (
        <div className="space-y-2">
          {warnings.map((warning) => (
            <WarningCard
              key={warning.id}
              warning={warning}
              onClick={() => handleSelectWarning(warning)}
              isSelected={selectedWarning?.id === warning.id}
              getSeverityColor={getSeverityColor}
              getProbabilityColor={getProbabilityColor}
              getProbabilityLabel={getProbabilityLabel}
              formatAge={formatAge}
              formatTimestamp={formatTimestamp}
            />
          ))}
        </div>
      )}
    </ScrollableCard>
  );
}

interface WarningCardProps {
  warning: WarningEvent;
  onClick: () => void;
  isSelected: boolean;
  getSeverityColor: (severity: string) => string;
  getProbabilityColor: (probability: number) => string;
  getProbabilityLabel: (probability: number) => string;
  formatAge: (minutes: number) => string;
  formatTimestamp: (timestamp: string) => string;
}

function WarningCard({
  warning,
  onClick,
  isSelected,
  getSeverityColor,
  getProbabilityColor,
  getProbabilityLabel,
  formatAge,
  formatTimestamp,
}: WarningCardProps) {
  return (
    <div
      onClick={onClick}
      className={`
        p-3 rounded-lg border cursor-pointer transition-all
        ${
          isSelected
            ? "border-blue-500 bg-blue-500/10"
            : "border-zinc-800 bg-zinc-900 hover:border-zinc-700"
        }
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Badge className={getSeverityColor(warning.severity)}>
              {warning.severity}
            </Badge>
            {warning.system && (
              <span className="text-xs text-zinc-400">{warning.system}</span>
            )}
          </div>
          <div className="font-medium text-sm truncate" title={warning.alert_name}>
            {warning.alert_name}
          </div>
        </div>

        {/* Escalation Probability */}
        <div className="flex flex-col items-end gap-1">
          <div
            className={`text-xs font-semibold ${getProbabilityColor(
              warning.escalation_probability
            )}`}
          >
            {getProbabilityLabel(warning.escalation_probability)}
          </div>
          <div className="text-xs text-zinc-500">
            {(warning.escalation_probability * 100).toFixed(0)}%
          </div>
        </div>
      </div>

      {/* Status Indicators */}
      <div className="flex items-center gap-3 text-xs text-zinc-400">
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {formatAge(warning.age_minutes)}
        </div>

        {warning.has_standby_context && (
          <div className="flex items-center gap-1 text-blue-400">
            <AlertCircle className="w-3 h-3" />
            Standby Ready
          </div>
        )}

        {warning.escalated && (
          <div className="flex items-center gap-1 text-red-400">
            <TrendingUp className="w-3 h-3" />
            Escalated
          </div>
        )}

        {warning.auto_cleared && (
          <div className="flex items-center gap-1 text-emerald-400">
            <CheckCircle2 className="w-3 h-3" />
            Cleared
          </div>
        )}
      </div>

      {/* Timestamps */}
      <div className="mt-2 text-xs text-zinc-500">
        First: {formatTimestamp(warning.first_seen)}
        {warning.escalated_at && (
          <span className="ml-2">
            • Escalated: {formatTimestamp(warning.escalated_at)}
          </span>
        )}
        {warning.cleared_at && (
          <span className="ml-2">
            • Cleared: {formatTimestamp(warning.cleared_at)}
          </span>
        )}
      </div>

      {/* Escalation Reason */}
      {warning.escalation_reason && (
        <div className="mt-2 text-xs text-zinc-400 italic">
          {warning.escalation_reason}
        </div>
      )}

      {/* Feedback Buttons - Only show for resolved warnings */}
      {(warning.escalated || warning.auto_cleared) && (
        <div className="mt-3 pt-3 border-t border-zinc-800">
          <FeedbackButtons warning={warning} />
        </div>
      )}
    </div>
  );
}
