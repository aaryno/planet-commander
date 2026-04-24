"use client";

import { ContextHealth } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { FileText, GitBranch, FolderGit2, MessageSquare, CheckCircle2, AlertCircle, XCircle } from "lucide-react";

interface HealthStripProps {
  health: ContextHealth;
}

export function HealthStrip({ health }: HealthStripProps) {
  const indicators = [
    {
      key: "ticket",
      icon: FileText,
      label: "Ticket",
      healthy: health.has_ticket,
    },
    {
      key: "branch",
      icon: GitBranch,
      label: "Branch",
      healthy: health.has_branch,
    },
    {
      key: "worktree",
      icon: FolderGit2,
      label: "Worktree",
      healthy: health.has_active_worktree,
    },
    {
      key: "chat",
      icon: MessageSquare,
      label: "Chat",
      healthy: health.has_chat,
    },
  ];

  const overallColor = {
    green: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    yellow: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    red: "bg-red-500/20 text-red-400 border-red-500/30",
  }[health.overall];

  const OverallIcon = {
    green: CheckCircle2,
    yellow: AlertCircle,
    red: XCircle,
  }[health.overall];

  return (
    <div className="flex items-center gap-2">
      {/* Overall Health Badge */}
      <Badge
        variant="outline"
        className={`${overallColor} font-semibold capitalize flex items-center gap-1`}
      >
        <OverallIcon className="w-3 h-3" />
        {health.overall}
      </Badge>

      {/* Individual Health Indicators */}
      <div className="flex items-center gap-1 ml-2">
        {indicators.map(({ key, icon: Icon, label, healthy }) => (
          <div
            key={key}
            className={`flex items-center gap-1 px-2 py-1 rounded border text-xs ${
              healthy
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                : "bg-zinc-800/50 text-zinc-600 border-zinc-700/50"
            }`}
            title={`${label}: ${healthy ? "Present" : "Missing"}`}
          >
            <Icon className="w-3 h-3" />
            <span>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
