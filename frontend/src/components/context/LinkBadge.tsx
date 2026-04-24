"use client";

import { Badge } from "@/components/ui/badge";
import { FileText, MessageSquare, GitBranch, FolderGit2, Link as LinkIcon } from "lucide-react";

interface LinkBadgeProps {
  type: string;
  id: string;
  onClick?: () => void;
}

const entityConfig: Record<string, { icon: React.ComponentType<{ className?: string }>; color: string; label: string }> = {
  context: {
    icon: LinkIcon,
    color: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    label: "Context",
  },
  jira_issue: {
    icon: FileText,
    color: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    label: "Issue",
  },
  chat: {
    icon: MessageSquare,
    color: "bg-purple-500/20 text-purple-400 border-purple-500/30",
    label: "Chat",
  },
  branch: {
    icon: GitBranch,
    color: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    label: "Branch",
  },
  worktree: {
    icon: FolderGit2,
    color: "bg-indigo-500/20 text-indigo-400 border-indigo-500/30",
    label: "Worktree",
  },
};

export function LinkBadge({ type, id, onClick }: LinkBadgeProps) {
  const config = entityConfig[type] || {
    icon: LinkIcon,
    color: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
    label: type,
  };

  const Icon = config.icon;

  // Shorten UUID for display
  const displayId = id.length > 8 ? `${id.slice(0, 8)}...` : id;

  return (
    <Badge
      variant="outline"
      className={`${config.color} flex items-center gap-1 font-mono text-xs ${
        onClick ? "cursor-pointer hover:opacity-80" : ""
      }`}
      onClick={onClick}
      title={`${config.label}: ${id}`}
    >
      <Icon className="w-3 h-3" />
      <span>{config.label}</span>
      <span className="text-[10px] opacity-70">{displayId}</span>
    </Badge>
  );
}
