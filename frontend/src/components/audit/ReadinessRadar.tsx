"use client";

import { Badge } from "@/components/ui/badge";
import { DimensionScoreBar } from "./DimensionScoreBar";
import { Radar } from "lucide-react";
import type { DimensionScores } from "@/lib/api";

/**
 * The 8 readiness dimensions in display order.
 */
const DIMENSION_ORDER: (keyof DimensionScores)[] = [
  "objective_clarity",
  "target_surface",
  "acceptance_criteria",
  "dependencies",
  "validation_path",
  "scope_boundaries",
  "missing_decisions",
  "execution_safety",
];

interface ReadinessRadarProps {
  /** Scores for each of the 8 readiness dimensions (0-2 each) */
  dimensionScores: Record<string, number>;
  /** Override computed total score */
  totalScore?: number;
  /** Override computed max score (default: dimensions * 2) */
  maxScore?: number;
}

/**
 * Get the overall color class based on total score ratio.
 *
 * - >= 75% -> emerald (healthy)
 * - >= 50% -> amber (partial)
 * - < 50%  -> red (needs work)
 */
function getOverallColorClasses(score: number, max: number): string {
  if (max === 0) return "bg-zinc-500/20 text-zinc-400";
  const ratio = score / max;
  if (ratio >= 0.75) return "bg-emerald-500/20 text-emerald-400";
  if (ratio >= 0.5) return "bg-amber-500/20 text-amber-400";
  return "bg-red-500/20 text-red-400";
}

/**
 * Readiness Radar displays all 8 readiness dimensions as score bars
 * with a summary header showing the total score.
 *
 * Used in the audit tab to visualize ticket/MR readiness before
 * development begins.
 */
export function ReadinessRadar({
  dimensionScores,
  totalScore,
  maxScore,
}: ReadinessRadarProps) {
  // Compute total from dimension scores if not provided
  const computedTotal =
    totalScore ??
    DIMENSION_ORDER.reduce(
      (sum, dim) => sum + (dimensionScores[dim] ?? 0),
      0,
    );

  const computedMax = maxScore ?? DIMENSION_ORDER.length * 2;
  const overallClasses = getOverallColorClasses(computedTotal, computedMax);

  return (
    <div className="space-y-3">
      {/* Summary header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Radar className="w-4 h-4 text-zinc-400" />
          <span className="text-sm font-medium text-zinc-200">
            Readiness Radar
          </span>
        </div>
        <Badge className={`text-xs border-0 ${overallClasses}`}>
          {computedTotal} / {computedMax}
        </Badge>
      </div>

      {/* Dimension bars */}
      <div className="space-y-2">
        {DIMENSION_ORDER.map((dim) => {
          const raw = dimensionScores[dim] ?? 0;
          // Clamp to valid score range
          const score = Math.max(0, Math.min(2, raw)) as 0 | 1 | 2;

          return (
            <DimensionScoreBar key={dim} name={dim} score={score} />
          );
        })}
      </div>
    </div>
  );
}
