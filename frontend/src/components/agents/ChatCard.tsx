"use client";

import { useState } from "react";
import { X, ExternalLink } from "lucide-react";
import type { Agent } from "@/lib/api";
import { ChatView } from "./ChatView";
import { WorkspaceActions } from "@/components/workspace/WorkspaceActions";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { getLabelColor } from "@/lib/label-colors";

interface ChatCardProps {
  agent: Agent;
  onClose: () => void;
  onHide?: (id: string) => void;
}

export function ChatCard({ agent, onClose, onHide }: ChatCardProps) {
  const [localAgent, setLocalAgent] = useState(agent);

  const handleWorktreeCreated = async (path: string, branch: string) => {
    // Update the agent with the new worktree path
    try {
      const updated = await api.agentUpdate(agent.id, {
        worktree_path: path,
        git_branch: branch
      });
      setLocalAgent(updated);
    } catch (error) {
      console.error("Failed to update agent with worktree:", error);
    }
  };

  return (
    <div className="bg-zinc-900 rounded-lg border border-zinc-800 flex flex-col h-full overflow-hidden">
      {/* Standardized Header */}
      <div className="flex items-center justify-between gap-2 p-3 border-b border-zinc-800 shrink-0 bg-zinc-900/95">
        {/* Left: Project + JIRA */}
        <div className="flex items-center gap-2">
          {/* Project badge */}
          {localAgent.project && (
            <Badge
              variant="outline"
              className={`${getLabelColor(localAgent.project, "project")} border text-[10px] px-1.5 py-0`}
            >
              {localAgent.project}
            </Badge>
          )}

          {/* JIRA badge */}
          {localAgent.jira_key && (
            <>
              <Badge className="text-cyan-400 border-cyan-600/50 bg-cyan-500/10 text-xs font-mono">
                {localAgent.jira_key}
              </Badge>

              {/* External link */}
              <a
                href={`https://hello.planet.com/jira/browse/${localAgent.jira_key}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </>
          )}
        </div>

        {/* Right: Actions + Close */}
        <div className="flex items-center gap-2 shrink-0">
          <WorkspaceActions
            jiraKey={localAgent.jira_key || undefined}
            project={localAgent.project}
            worktreePath={localAgent.worktree_path || undefined}
            workingDirectory={localAgent.working_directory || undefined}
            onWorktreeCreated={handleWorktreeCreated}
          />
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

      {/* Chat content */}
      <div className="flex-1 overflow-hidden">
        <ChatView agent={localAgent} className="h-full" onHide={onHide} source="sidebar" />
      </div>
    </div>
  );
}
