"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertTriangle,
  AlertCircle,
  Info,
  ShieldAlert,
  FileCode,
  CheckCircle2,
  Clock,
  XCircle,
  Wrench,
} from "lucide-react";
import type { AuditFinding } from "@/lib/api";

interface FindingCardProps {
  finding: AuditFinding;
  onResolve?: (findingId: string) => void;
  onDefer?: (findingId: string) => void;
  onReject?: (findingId: string) => void;
}

const SEVERITY_CONFIG: Record<string, { classes: string; icon: typeof AlertCircle }> = {
  error: { classes: "bg-red-500/20 text-red-400", icon: AlertCircle },
  warning: { classes: "bg-amber-500/20 text-amber-400", icon: AlertTriangle },
  info: { classes: "bg-blue-500/20 text-blue-400", icon: Info },
};

const STATUS_CONFIG: Record<string, { classes: string; icon: typeof CheckCircle2 }> = {
  open: { classes: "text-zinc-400 border-zinc-600/30", icon: Clock },
  resolved: { classes: "text-emerald-400 border-emerald-500/30", icon: CheckCircle2 },
  deferred: { classes: "text-amber-400 border-amber-500/30", icon: Clock },
  rejected: { classes: "text-zinc-500 border-zinc-600/30", icon: XCircle },
};

export function FindingCard({ finding, onResolve, onDefer, onReject }: FindingCardProps) {
  const severity = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.info;
  const status = STATUS_CONFIG[finding.status] || STATUS_CONFIG.open;
  const SeverityIcon = severity.icon;
  const StatusIcon = status.icon;

  return (
    <div
      className={`p-4 rounded-lg border transition-colors ${
        finding.blocking
          ? "border-red-500/40 hover:border-red-500/60"
          : "border-zinc-800 hover:border-zinc-700"
      }`}
    >
      {/* Header: severity icon + title + status */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2 flex-1 min-w-0">
          <SeverityIcon className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: "inherit" }} />
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-medium text-zinc-200 leading-snug">
              {finding.title}
            </h4>
          </div>
        </div>

        {/* Status badge */}
        <Badge variant="outline" className={`text-xs flex-shrink-0 ${status.classes}`}>
          <StatusIcon className="w-3 h-3 mr-1" />
          {finding.status}
        </Badge>
      </div>

      {/* Badges row: severity, category, blocking, auto-fixable */}
      <div className="flex items-center gap-1.5 mt-2 flex-wrap">
        <Badge className={`text-xs border-0 ${severity.classes}`}>
          {finding.severity}
        </Badge>

        <Badge variant="outline" className="text-xs text-zinc-400 border-zinc-600/30">
          {finding.category}
        </Badge>

        {finding.blocking && (
          <Badge variant="outline" className="text-xs text-red-400 border-red-500/30">
            <ShieldAlert className="w-3 h-3 mr-1" />
            blocking
          </Badge>
        )}

        {finding.auto_fixable && (
          <Badge variant="outline" className="text-xs text-emerald-400 border-emerald-500/30">
            <Wrench className="w-3 h-3 mr-1" />
            auto-fixable
          </Badge>
        )}
      </div>

      {/* Description */}
      <p className="mt-2 text-xs text-zinc-400 leading-relaxed">
        {finding.description}
      </p>

      {/* Code */}
      <div className="mt-2">
        <code className="text-xs font-mono text-zinc-500 bg-zinc-800/50 px-1.5 py-0.5 rounded">
          {finding.code}
        </code>
      </div>

      {/* Source file + line */}
      {finding.source_file && (
        <div className="flex items-center gap-1 mt-2 text-xs text-zinc-500">
          <FileCode className="w-3 h-3" />
          <span className="font-mono">
            {finding.source_file}
            {finding.source_line != null && `:${finding.source_line}`}
          </span>
        </div>
      )}

      {/* Resolution note */}
      {finding.resolution && (
        <div className="mt-2 text-xs text-zinc-500 italic">
          Resolution: {finding.resolution}
        </div>
      )}

      {/* Action buttons (only for open findings) */}
      {finding.status === "open" && (onResolve || onDefer || onReject) && (
        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-zinc-800">
          {onResolve && (
            <Button
              variant="ghost"
              size="xs"
              className="text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
              onClick={() => onResolve(finding.id)}
            >
              <CheckCircle2 className="w-3 h-3 mr-1" />
              Resolve
            </Button>
          )}
          {onDefer && (
            <Button
              variant="ghost"
              size="xs"
              className="text-amber-400 hover:text-amber-300 hover:bg-amber-500/10"
              onClick={() => onDefer(finding.id)}
            >
              <Clock className="w-3 h-3 mr-1" />
              Defer
            </Button>
          )}
          {onReject && (
            <Button
              variant="ghost"
              size="xs"
              className="text-zinc-500 hover:text-zinc-400 hover:bg-zinc-500/10"
              onClick={() => onReject(finding.id)}
            >
              <XCircle className="w-3 h-3 mr-1" />
              Reject
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
