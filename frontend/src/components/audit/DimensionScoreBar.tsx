"use client";

import { Badge } from "@/components/ui/badge";

interface DimensionScoreBarProps {
  /** Dimension name (e.g., "objective_clarity") */
  name: string;
  /** Score: 0 = Missing, 1 = Partial, 2 = Complete */
  score: 0 | 1 | 2;
  /** Maximum possible score (default 2) */
  maxScore?: number;
}

const SCORE_CONFIG: Record<
  number,
  { classes: string; barColor: string; label: string }
> = {
  0: {
    classes: "bg-red-500/20 text-red-400",
    barColor: "bg-red-500/60",
    label: "Missing",
  },
  1: {
    classes: "bg-amber-500/20 text-amber-400",
    barColor: "bg-amber-500/60",
    label: "Partial",
  },
  2: {
    classes: "bg-emerald-500/20 text-emerald-400",
    barColor: "bg-emerald-500/60",
    label: "Complete",
  },
};

/**
 * Format a snake_case dimension name to Title Case.
 *
 * Example: "objective_clarity" -> "Objective Clarity"
 */
function formatDimensionName(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * Single dimension score bar for the readiness radar.
 *
 * Displays a dimension name on the left, a proportionally-filled bar,
 * and a score badge on the right. Colors follow the audit system palette:
 * red (0/Missing), amber (1/Partial), emerald (2/Complete).
 */
export function DimensionScoreBar({
  name,
  score,
  maxScore = 2,
}: DimensionScoreBarProps) {
  const config = SCORE_CONFIG[score] ?? SCORE_CONFIG[0];
  const fillPercent = maxScore > 0 ? (score / maxScore) * 100 : 0;

  return (
    <div className="flex items-center gap-3">
      {/* Dimension name */}
      <span className="text-xs text-zinc-300 w-36 flex-shrink-0 truncate">
        {formatDimensionName(name)}
      </span>

      {/* Score bar */}
      <div className="flex-1 h-2 rounded-full bg-zinc-800 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${config.barColor}`}
          style={{ width: `${fillPercent}%` }}
        />
      </div>

      {/* Score badge */}
      <Badge className={`text-xs border-0 w-20 justify-center ${config.classes}`}>
        {config.label}
      </Badge>
    </div>
  );
}
