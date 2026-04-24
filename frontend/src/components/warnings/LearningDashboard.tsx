"use client";

import { useCallback } from "react";
import { TrendingUp, Brain, Target, Award } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Badge } from "@/components/ui/badge";
import { usePoll } from "@/lib/polling";
import { api, AlertPerformance } from "@/lib/api";

interface LearningDashboardProps {
  days?: number;
}

export function LearningDashboard({ days = 30 }: LearningDashboardProps) {
  // Poll summary every 10 minutes
  const {
    data: summary,
    loading: summaryLoading,
    error: summaryError,
  } = usePoll(
    useCallback(() => api.learningSummary(), []),
    600_000
  );

  // Poll alerts every 10 minutes
  const {
    data: alerts,
    loading: alertsLoading,
    error: alertsError,
    refresh: refetchAlerts,
  } = usePoll(
    useCallback(() => api.learningAlerts(days), [days]),
    600_000
  );

  const getAccuracyColor = (accuracy: number | null) => {
    if (accuracy === null) return "text-zinc-500";
    if (accuracy >= 0.8) return "text-emerald-400";
    if (accuracy >= 0.6) return "text-amber-400";
    return "text-red-400";
  };

  const getAccuracyBadge = (accuracy: number | null) => {
    if (accuracy === null) return "bg-zinc-800 text-zinc-400";
    if (accuracy >= 0.8) return "bg-emerald-500/20 text-emerald-400";
    if (accuracy >= 0.6) return "bg-amber-500/20 text-amber-400";
    return "bg-red-500/20 text-red-400";
  };

  const menuItems = [
    {
      label: "Refresh Learning Data",
      onClick: refetchAlerts,
    },
  ];

  const stickyHeader = (
    <div className="space-y-3">
      {/* Summary Stats */}
      {summary && !summaryLoading && (
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-zinc-800/50 rounded p-2">
            <div className="text-zinc-400">Total Feedback</div>
            <div className="text-lg font-semibold">{summary.total_feedback}</div>
          </div>
          <div className="bg-emerald-500/10 rounded p-2">
            <div className="text-zinc-400">Well Tuned</div>
            <div className="text-lg font-semibold text-emerald-400">
              {summary.well_tuned_alerts}
            </div>
          </div>
          <div className="bg-amber-500/10 rounded p-2">
            <div className="text-zinc-400">Need Tuning</div>
            <div className="text-lg font-semibold text-amber-400">
              {summary.high_potential_alerts}
            </div>
          </div>
          <div className="bg-blue-500/10 rounded p-2">
            <div className="text-zinc-400">Current Accuracy</div>
            <div
              className={`text-lg font-semibold ${getAccuracyColor(
                summary.current_accuracy
              )}`}
            >
              {summary.current_accuracy
                ? `${(summary.current_accuracy * 100).toFixed(1)}%`
                : "N/A"}
            </div>
          </div>
        </div>
      )}

      {/* Improvement */}
      {summary && summary.accuracy_improvement !== null && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-zinc-400">30-day improvement:</span>
          <span
            className={
              summary.accuracy_improvement >= 0
                ? "text-emerald-400 flex items-center gap-1"
                : "text-red-400 flex items-center gap-1"
            }
          >
            {summary.accuracy_improvement >= 0 ? (
              <TrendingUp className="w-3 h-3" />
            ) : (
              <TrendingUp className="w-3 h-3 rotate-180" />
            )}
            {summary.accuracy_improvement >= 0 ? "+" : ""}
            {(summary.accuracy_improvement * 100).toFixed(1)}%
          </span>
        </div>
      )}

      <div className="flex justify-between items-center">
        <span className="text-xs text-zinc-400">
          {alerts?.length || 0} alerts analyzed
        </span>
      </div>
    </div>
  );

  return (
    <ScrollableCard
      title="Learning System"
      icon={<Brain className="w-4 h-4" />}
      stickyHeader={stickyHeader}
      menuItems={menuItems}
    >
      {alertsLoading && alerts === undefined && (
        <p className="text-xs text-zinc-500 text-center py-8">
          Loading learning data...
        </p>
      )}

      {alertsError && (
        <div className="text-xs text-red-400 text-center py-8">
          Error loading learning data: {alertsError.message}
        </div>
      )}

      {alerts && alerts.length === 0 && (
        <div className="text-xs text-zinc-500 text-center py-8">
          <Brain className="w-8 h-8 mx-auto mb-2 text-zinc-600" />
          No alerts with feedback yet
        </div>
      )}

      {alerts && alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((alert) => (
            <AlertPerformanceCard
              key={`${alert.alert_name}-${alert.system}`}
              alert={alert}
              getAccuracyBadge={getAccuracyBadge}
              getAccuracyColor={getAccuracyColor}
            />
          ))}
        </div>
      )}
    </ScrollableCard>
  );
}

interface AlertPerformanceCardProps {
  alert: AlertPerformance;
  getAccuracyBadge: (accuracy: number | null) => string;
  getAccuracyColor: (accuracy: number | null) => string;
}

function AlertPerformanceCard({
  alert,
  getAccuracyBadge,
  getAccuracyColor,
}: AlertPerformanceCardProps) {
  return (
    <div className="p-3 rounded-lg border border-zinc-800 bg-zinc-900 hover:border-zinc-700 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm truncate" title={alert.alert_name}>
            {alert.alert_name}
          </div>
          {alert.system && (
            <div className="text-xs text-zinc-400 mt-0.5">{alert.system}</div>
          )}
        </div>

        {/* Accuracy Badge */}
        <Badge className={getAccuracyBadge(alert.accuracy)}>
          {alert.accuracy !== null
            ? `${(alert.accuracy * 100).toFixed(0)}%`
            : "No feedback"}
        </Badge>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div>
          <div className="text-zinc-500">Feedback</div>
          <div className="font-semibold">{alert.feedback_count}</div>
        </div>
        <div>
          <div className="text-zinc-500">Correct</div>
          <div className="font-semibold text-emerald-400">
            {alert.correct_predictions}
          </div>
        </div>
        <div>
          <div className="text-zinc-500">Errors</div>
          <div className="font-semibold text-red-400">
            {alert.false_negatives + alert.false_positives}
          </div>
        </div>
      </div>

      {/* Error Breakdown */}
      {(alert.false_negatives > 0 || alert.false_positives > 0) && (
        <div className="mt-2 flex items-center gap-3 text-xs text-zinc-400">
          {alert.false_negatives > 0 && (
            <span>FN: {alert.false_negatives}</span>
          )}
          {alert.false_positives > 0 && (
            <span>FP: {alert.false_positives}</span>
          )}
        </div>
      )}

      {/* Improvement Potential */}
      {alert.improvement_potential > 0.5 && (
        <div className="mt-2 flex items-center gap-1 text-xs text-amber-400">
          <Target className="w-3 h-3" />
          <span>High improvement potential</span>
        </div>
      )}

      {/* Well Tuned */}
      {alert.accuracy !== null && alert.accuracy >= 0.8 && (
        <div className="mt-2 flex items-center gap-1 text-xs text-emerald-400">
          <Award className="w-3 h-3" />
          <span>Well tuned</span>
        </div>
      )}
    </div>
  );
}
