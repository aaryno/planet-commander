"use client";

import { useCallback } from "react";
import { TrendingUp, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { usePoll } from "@/lib/polling";
import { api, PredictionAccuracy as AccuracyData } from "@/lib/api";

interface PredictionAccuracyProps {
  days?: number;
}

export function PredictionAccuracy({ days = 30 }: PredictionAccuracyProps) {
  const {
    data: accuracy,
    loading,
    error,
    refresh: refetch,
  } = usePoll(
    useCallback(() => api.predictionAccuracy(days), [days]),
    300_000 // 5 minutes
  );

  const getAccuracyColor = (acc: number) => {
    if (acc >= 0.8) return "text-emerald-400";
    if (acc >= 0.6) return "text-amber-400";
    return "text-red-400";
  };

  const getAccuracyBgColor = (acc: number) => {
    if (acc >= 0.8) return "bg-emerald-500/20";
    if (acc >= 0.6) return "bg-amber-500/20";
    return "bg-red-500/20";
  };

  const menuItems = [
    {
      label: "Refresh",
      onClick: refetch,
    },
  ];

  return (
    <ScrollableCard
      title="Prediction Accuracy"
      icon={<TrendingUp className="w-4 h-4" />}
      menuItems={menuItems}
    >
      {loading && !accuracy && (
        <p className="text-xs text-zinc-500 text-center py-8">
          Loading accuracy metrics...
        </p>
      )}

      {error && (
        <div className="text-xs text-red-400 text-center py-8">
          Error loading accuracy: {error.message}
        </div>
      )}

      {accuracy && accuracy.total_predictions === 0 && (
        <p className="text-xs text-zinc-500 text-center py-8">
          No predictions to analyze yet
        </p>
      )}

      {accuracy && accuracy.total_predictions > 0 && (
        <div className="space-y-6">
          {/* Main Accuracy Display */}
          <div className="text-center py-4">
            <div
              className={`inline-flex items-center justify-center w-32 h-32 rounded-full ${getAccuracyBgColor(
                accuracy.accuracy
              )} mb-2`}
            >
              <div className="text-center">
                <div
                  className={`text-4xl font-bold ${getAccuracyColor(
                    accuracy.accuracy
                  )}`}
                >
                  {Math.round(accuracy.accuracy * 100)}%
                </div>
                <div className="text-xs text-zinc-500 mt-1">Accuracy</div>
              </div>
            </div>
            <p className="text-xs text-zinc-400 mt-2">
              {accuracy.correct_predictions} of {accuracy.total_predictions}{" "}
              predictions correct
            </p>
          </div>

          {/* Breakdown */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-zinc-400 border-b border-zinc-800 pb-2">
              Prediction Breakdown
            </h3>

            {/* Correct Predictions */}
            <div className="flex items-center justify-between p-3 rounded bg-zinc-900/50">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-sm text-zinc-300">Correct</span>
              </div>
              <div className="text-right">
                <div className="text-sm font-semibold text-emerald-400">
                  {accuracy.correct_predictions}
                </div>
                <div className="text-xs text-zinc-500">
                  {accuracy.total_predictions > 0
                    ? Math.round(
                        (accuracy.correct_predictions /
                          accuracy.total_predictions) *
                          100
                      )
                    : 0}
                  %
                </div>
              </div>
            </div>

            {/* False Positives */}
            <div className="flex items-center justify-between p-3 rounded bg-zinc-900/50">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <div>
                  <div className="text-sm text-zinc-300">False Positives</div>
                  <div className="text-xs text-zinc-500">
                    Predicted high, but cleared
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-semibold text-amber-400">
                  {accuracy.false_positives}
                </div>
                <div className="text-xs text-zinc-500">
                  {accuracy.total_predictions > 0
                    ? Math.round(
                        (accuracy.false_positives /
                          accuracy.total_predictions) *
                          100
                      )
                    : 0}
                  %
                </div>
              </div>
            </div>

            {/* False Negatives */}
            <div className="flex items-center justify-between p-3 rounded bg-zinc-900/50">
              <div className="flex items-center gap-2">
                <XCircle className="w-4 h-4 text-red-400" />
                <div>
                  <div className="text-sm text-zinc-300">False Negatives</div>
                  <div className="text-xs text-zinc-500">
                    Predicted low, but escalated
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-semibold text-red-400">
                  {accuracy.false_negatives}
                </div>
                <div className="text-xs text-zinc-500">
                  {accuracy.total_predictions > 0
                    ? Math.round(
                        (accuracy.false_negatives /
                          accuracy.total_predictions) *
                          100
                      )
                    : 0}
                  %
                </div>
              </div>
            </div>
          </div>

          {/* Analysis Period */}
          <div className="pt-3 border-t border-zinc-800">
            <p className="text-xs text-zinc-500 text-center">
              Based on {accuracy.total_predictions} resolved warnings over {days}{" "}
              days
            </p>
          </div>
        </div>
      )}
    </ScrollableCard>
  );
}
