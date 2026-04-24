"use client";

import { useState, useCallback } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { WorkspaceDetail, Agent } from "@/lib/api";
import { getLabelColor } from "@/lib/label-colors";
import { WorkspaceTabs } from "./WorkspaceTabs";

interface UnifiedWorkspaceViewProps {
  workspace: WorkspaceDetail;
  onClose: () => void;
  onUpdate?: (workspace: WorkspaceDetail) => void;
  onOpenAgent?: (agent: Agent) => void;
}

export function UnifiedWorkspaceView({
  workspace,
  onClose,
  onUpdate,
  onOpenAgent,
}: UnifiedWorkspaceViewProps) {
  const [activeTab, setActiveTab] = useState<"overview" | "jira" | "chats" | "code" | "deployments">("overview");

  const handleWorkspaceUpdate = useCallback((updated: WorkspaceDetail) => {
    onUpdate?.(updated);
  }, [onUpdate]);

  const primaryTicket = workspace.jira_tickets.find(t => t.is_primary);

  return (
    <div className="bg-zinc-900 rounded-lg border border-zinc-800 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 p-3 border-b border-zinc-800 shrink-0 bg-zinc-900/95">
        {/* Left: Project badge + Title */}
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {/* Project badge */}
          <Badge
            variant="outline"
            className={`${getLabelColor(workspace.project, "project")} border text-[10px] px-1.5 py-0 shrink-0`}
          >
            {workspace.project}
          </Badge>

          {/* Primary JIRA ticket badge (if exists) */}
          {primaryTicket && (
            <Badge className="text-cyan-400 border-cyan-600/50 bg-cyan-500/10 text-xs font-mono shrink-0">
              {primaryTicket.key}
            </Badge>
          )}

          {/* Title */}
          <span className="text-sm text-zinc-300 truncate">{workspace.title}</span>

          {/* Resource counts */}
          <div className="flex items-center gap-1.5 ml-2 shrink-0">
            {workspace.jira_tickets.length > 0 && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-cyan-600/30 text-cyan-400">
                {workspace.jira_tickets.length} ticket{workspace.jira_tickets.length !== 1 ? "s" : ""}
              </Badge>
            )}
            {workspace.agents.length > 0 && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-purple-600/30 text-purple-400">
                {workspace.agents.length} chat{workspace.agents.length !== 1 ? "s" : ""}
              </Badge>
            )}
            {workspace.branches.length > 0 && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-green-600/30 text-green-400">
                {workspace.branches.length} branch{workspace.branches.length !== 1 ? "es" : ""}
              </Badge>
            )}
          </div>
        </div>

        {/* Right: Close button */}
        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <WorkspaceTabs
        workspace={workspace}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onUpdate={handleWorkspaceUpdate}
        onOpenAgent={onOpenAgent}
      />
    </div>
  );
}
