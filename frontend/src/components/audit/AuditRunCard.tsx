"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FindingsList } from "./FindingsList";
import {
  ChevronDown,
  ChevronUp,
  Clock,
  AlertCircle,
  ShieldAlert,
  Wrench,
  CheckCircle2,
  XCircle,
  AlertTriangle,
} from "lucide-react";
import type { AuditRun } from "@/lib/api";

interface AuditRunCardProps {
  run: AuditRun;
  onResolveFinding?: (findingId: string) => void;
  onDeferFinding?: (findingId: string) => void;
  onRejectFinding?: (findingId: string) => void;
  defaultExpanded?: boolean;
}

const VERDICT_CONFIG: Record<string, { classes: string; icon: typeof CheckCircle2 }> = {
  pass: { classes: "bg-emerald-500/20 text-emerald-400", icon: CheckCircle2 },
  fail: { classes: "bg-red-500/20 text-red-400", icon: XCircle },
  warn: { classes: "bg-amber-500/20 text-amber-400", icon: AlertTriangle },
  skip: { classes: "bg-zinc-500/20 text-zinc-400", icon: Clock },
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms / 60_000)}m`;
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.round(diffMs / 60_000);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.round(diffHr / 24);
  return `${diffDays}d ago`;
}

export function AuditRunCard({
  run,
  onResolveFinding,
  onDeferFinding,
  onRejectFinding,
  defaultExpanded = false,
}: AuditRunCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const verdict = VERDICT_CONFIG[run.verdict] || VERDICT_CONFIG.skip;
  const VerdictIcon = verdict.icon;

  const errorCount = run.findings.filter((f) => f.severity === "error").length;
  const warningCount = run.findings.filter((f) => f.severity === "warning").length;

  return (
    <div className="rounded-lg border border-zinc-800 hover:border-zinc-700 transition-colors overflow-hidden">
      {/* Summary header */}
      <div
        className="flex items-center justify-between gap-3 p-4 cursor-pointer hover:bg-zinc-800/30 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {/* Verdict icon */}
          <VerdictIcon className={`w-5 h-5 flex-shrink-0 ${verdict.classes.split(" ").pop()}`} />

          {/* Family name + source */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-medium text-zinc-200 truncate">
                {run.audit_family}
              </h4>
              <Badge className={`text-xs border-0 ${verdict.classes}`}>
                {run.verdict}
              </Badge>
            </div>
            <div className="flex items-center gap-2 mt-0.5 text-xs text-zinc-500">
              <span>{run.source}</span>
              <span className="text-zinc-700">|</span>
              <span>tier {run.audit_tier}</span>
              <span className="text-zinc-700">|</span>
              <span>{run.target_type}</span>
            </div>
          </div>
        </div>

        {/* Finding count badges + meta */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Finding count summary */}
          {run.finding_count > 0 && (
            <div className="flex items-center gap-1.5">
              {errorCount > 0 && (
                <Badge className="text-xs border-0 bg-red-500/20 text-red-400">
                  <AlertCircle className="w-3 h-3 mr-0.5" />
                  {errorCount}
                </Badge>
              )}
              {warningCount > 0 && (
                <Badge className="text-xs border-0 bg-amber-500/20 text-amber-400">
                  <AlertTriangle className="w-3 h-3 mr-0.5" />
                  {warningCount}
                </Badge>
              )}
              {run.blocking_count > 0 && (
                <Badge variant="outline" className="text-xs text-red-400 border-red-500/30">
                  <ShieldAlert className="w-3 h-3 mr-0.5" />
                  {run.blocking_count}
                </Badge>
              )}
              {run.auto_fixable_count > 0 && (
                <Badge variant="outline" className="text-xs text-emerald-400 border-emerald-500/30">
                  <Wrench className="w-3 h-3 mr-0.5" />
                  {run.auto_fixable_count}
                </Badge>
              )}
            </div>
          )}

          {/* Duration + timestamp */}
          <div className="flex items-center gap-1 text-xs text-zinc-500">
            <Clock className="w-3 h-3" />
            <span>{formatDuration(run.duration_ms)}</span>
          </div>

          <span className="text-xs text-zinc-600" title={run.created_at}>
            {formatTimestamp(run.created_at)}
          </span>

          {/* Expand toggle */}
          <Button
            variant="ghost"
            size="icon-xs"
            className="text-zinc-500 hover:text-zinc-300"
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
          >
            {expanded ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </Button>
        </div>
      </div>

      {/* Risk & dimension scores (if present) */}
      {expanded && (run.risk_score != null || run.dimension_scores) && (
        <div className="px-4 pb-3 border-t border-zinc-800">
          <div className="flex items-center gap-3 pt-3 flex-wrap">
            {run.risk_score != null && run.risk_level && (
              <div className="flex items-center gap-1 text-xs">
                <span className="text-zinc-500">Risk:</span>
                <Badge
                  className={`text-xs border-0 ${
                    run.risk_level === "high"
                      ? "bg-red-500/20 text-red-400"
                      : run.risk_level === "medium"
                      ? "bg-amber-500/20 text-amber-400"
                      : "bg-emerald-500/20 text-emerald-400"
                  }`}
                >
                  {run.risk_level} ({run.risk_score.toFixed(1)})
                </Badge>
              </div>
            )}
            {run.dimension_scores &&
              Object.entries(run.dimension_scores).map(([dim, score]) => (
                <div key={dim} className="flex items-center gap-1 text-xs">
                  <span className="text-zinc-500">{dim}:</span>
                  <span className="text-zinc-300">{score.toFixed(1)}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Expanded findings */}
      {expanded && (
        <div className="border-t border-zinc-800 p-4">
          <FindingsList
            findings={run.findings}
            onResolve={onResolveFinding}
            onDefer={onDeferFinding}
            onReject={onRejectFinding}
            embedded
          />
        </div>
      )}
    </div>
  );
}
