"use client";

import { useState, useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ShieldAlert, ChevronDown, ChevronUp } from "lucide-react";
import type { RiskFactor } from "@/lib/api";

interface ChangeRiskGaugeProps {
  /** Risk score from 0.0 to 1.0 */
  score: number;
  /** Risk level: "low", "medium", or "high" */
  level: string;
  /** Risk factor breakdown */
  factors: RiskFactor[];
}

/**
 * Color configuration keyed by risk level.
 */
const LEVEL_CONFIG: Record<
  string,
  { bg: string; text: string; fill: string; border: string; label: string }
> = {
  low: {
    bg: "bg-emerald-500/20",
    text: "text-emerald-400",
    fill: "bg-emerald-500",
    border: "border-emerald-500/30",
    label: "Low Risk",
  },
  medium: {
    bg: "bg-amber-500/20",
    text: "text-amber-400",
    fill: "bg-amber-500",
    border: "border-amber-500/30",
    label: "Medium Risk",
  },
  high: {
    bg: "bg-red-500/20",
    text: "text-red-400",
    fill: "bg-red-500",
    border: "border-red-500/30",
    label: "High Risk",
  },
};

/**
 * Category badge color mapping.
 */
const CATEGORY_COLORS: Record<string, string> = {
  "api-contract": "bg-blue-500/20 text-blue-400",
  "crd-definition": "bg-purple-500/20 text-purple-400",
  "iam-terraform": "bg-red-500/20 text-red-400",
  "database-migration": "bg-amber-500/20 text-amber-400",
  "secrets-exposure": "bg-red-500/20 text-red-400",
  "no-test-changes": "bg-amber-500/20 text-amber-400",
};

const DEFAULT_CATEGORY_COLOR = "bg-zinc-500/20 text-zinc-400";

/**
 * Risk factor detail item displayed in the expandable section.
 */
function RiskFactorItem({ factor }: { factor: RiskFactor }) {
  const categoryColor =
    CATEGORY_COLORS[factor.id] || DEFAULT_CATEGORY_COLOR;

  return (
    <div className="flex items-start gap-2 py-2 px-3 rounded-md bg-zinc-800/30 hover:bg-zinc-800/50 transition-colors">
      {/* Category badge */}
      <Badge className={`text-xs border-0 flex-shrink-0 mt-0.5 ${categoryColor}`}>
        {factor.id}
      </Badge>

      {/* Detail text */}
      <span className="text-xs text-zinc-400 flex-1 min-w-0 leading-relaxed">
        {factor.detail}
      </span>

      {/* Weight */}
      <span className="text-xs font-mono text-zinc-500 flex-shrink-0">
        +{factor.score.toFixed(2)}
      </span>
    </div>
  );
}

/**
 * Visual gauge component for displaying MR change risk scores.
 *
 * Renders a horizontal progress bar with color gradient (green/amber/red),
 * a risk level badge, percentage text, and an expandable risk factors list
 * sorted by weight descending.
 */
export function ChangeRiskGauge({
  score,
  level,
  factors,
}: ChangeRiskGaugeProps) {
  const [factorsOpen, setFactorsOpen] = useState(false);

  const config = LEVEL_CONFIG[level] || LEVEL_CONFIG.low;
  const pct = Math.round(score * 100);

  // Sort factors by score descending
  const sortedFactors = useMemo(
    () => [...factors].sort((a, b) => b.score - a.score),
    [factors]
  );

  return (
    <div className="rounded-lg border border-zinc-800 p-4 space-y-3">
      {/* Header: icon + label badge + percentage */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert className={`w-4 h-4 ${config.text}`} />
          <span className="text-sm font-medium text-zinc-200">
            Change Risk
          </span>
          <Badge
            variant="outline"
            className={`text-xs ${config.text} ${config.border}`}
          >
            {config.label}
          </Badge>
        </div>
        <span className={`text-lg font-semibold tabular-nums ${config.text}`}>
          {pct}%
        </span>
      </div>

      {/* Gauge bar */}
      <div className="relative w-full h-2 rounded-full bg-zinc-800 overflow-hidden">
        <div
          className={`absolute inset-y-0 left-0 rounded-full transition-all duration-500 ease-out ${config.fill}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Scale labels */}
      <div className="flex items-center justify-between text-[10px] text-zinc-600">
        <span>0%</span>
        <span>50%</span>
        <span>100%</span>
      </div>

      {/* Expandable risk factors */}
      {sortedFactors.length > 0 && (
        <Collapsible open={factorsOpen} onOpenChange={setFactorsOpen}>
          <CollapsibleTrigger asChild>
            <Button
              variant="ghost"
              size="xs"
              className="w-full justify-between text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"
            >
              <span className="flex items-center gap-1">
                {sortedFactors.length} risk factor
                {sortedFactors.length !== 1 ? "s" : ""}
              </span>
              {factorsOpen ? (
                <ChevronUp className="w-3 h-3" />
              ) : (
                <ChevronDown className="w-3 h-3" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="mt-2 space-y-1">
              {sortedFactors.map((factor) => (
                <RiskFactorItem key={factor.id} factor={factor} />
              ))}
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
}
