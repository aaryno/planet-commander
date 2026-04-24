"use client";

import { ChatCard } from "@/components/agents/ChatCard";
import { JiraWorkspace } from "./JiraWorkspace";
import { UnifiedWorkspaceView } from "./UnifiedWorkspaceView";
import type { Agent, WorkspaceDetail } from "@/lib/api";

export type Workspace =
  | { type: "agent"; agent: Agent; id: string }
  | { type: "jira"; jiraKey: string; project?: string; id: string }
  | { type: "unified"; workspace: WorkspaceDetail; id: string };

interface WorkspaceCardProps {
  workspace: Workspace;
  onClose: () => void;
  onHide?: (id: string) => void;
  onOpenAgent?: (agent: Agent) => void;
}

export function WorkspaceCard({ workspace, onClose, onHide, onOpenAgent }: WorkspaceCardProps) {
  if (workspace.type === "agent") {
    return (
      <ChatCard
        agent={workspace.agent}
        onClose={onClose}
        onHide={onHide}
      />
    );
  }

  if (workspace.type === "jira") {
    return (
      <JiraWorkspace
        jiraKey={workspace.jiraKey}
        project={workspace.project}
        onClose={onClose}
        onOpenAgent={onOpenAgent}
        onBreakoutChat={(agent) => onOpenAgent?.(agent)}
      />
    );
  }

  if (workspace.type === "unified") {
    return (
      <UnifiedWorkspaceView
        workspace={workspace.workspace}
        onClose={onClose}
        onOpenAgent={onOpenAgent}
      />
    );
  }

  return null;
}
