"use client";

import { useState } from "react";
import { Terminal, FolderPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useSettings } from "@/hooks/useSettings";

function getDefaultTerminalCommand(app: string): string {
  const commands: Record<string, string> = {
    ghostty: "open -a Ghostty {path}",
    iterm2: "open -a iTerm {path}",
    terminal: "open -a Terminal {path}",
    warp: "open -a Warp {path}",
    kitty: "open -a Kitty {path}",
  };
  return commands[app] || "";
}

interface WorkspaceActionsProps {
  jiraKey?: string;
  project?: string;
  worktreePath?: string;
  workingDirectory?: string;
  onWorktreeCreated?: (path: string, branch: string) => void;
}

export function WorkspaceActions({
  jiraKey,
  project,
  worktreePath,
  workingDirectory,
  onWorktreeCreated,
}: WorkspaceActionsProps) {
  const { settings } = useSettings();
  const [terminalLaunching, setTerminalLaunching] = useState(false);
  const [worktreeCreating, setWorktreeCreating] = useState(false);

  const handleLaunchTerminal = async () => {
    const path = worktreePath || workingDirectory;
    if (!path) {
      alert("No working directory or worktree path available");
      return;
    }

    const command = settings.terminal.customCommand || getDefaultTerminalCommand(settings.terminal.app);
    if (!command) {
      alert("Terminal command not configured. Please go to Settings to configure your terminal.");
      return;
    }

    setTerminalLaunching(true);
    try {
      await api.launchTerminal(path, command);
    } catch (error) {
      alert(`Failed to launch terminal: ${error}`);
    } finally {
      setTerminalLaunching(false);
    }
  };

  const handleCreateWorktree = async () => {
    if (!jiraKey || !project) {
      alert("Need both JIRA key and project to create a worktree");
      return;
    }

    setWorktreeCreating(true);
    try {
      const result = await api.worktreeCreate(project, jiraKey);

      // Notify parent of new worktree
      onWorktreeCreated?.(result.path, result.branch);

      // Offer to open terminal in new worktree
      if (confirm(`Worktree created at ${result.path}\n\nOpen terminal in new worktree?`)) {
        const command = settings.terminal.customCommand || getDefaultTerminalCommand(settings.terminal.app);
        if (command) {
          await api.launchTerminal(result.path, command);
        }
      }
    } catch (error) {
      alert(`Failed to create worktree: ${error}`);
    } finally {
      setWorktreeCreating(false);
    }
  };

  return (
    <div className="flex items-center gap-2 shrink-0">
      {/* Show Create Worktree button if has JIRA key but no worktree */}
      {jiraKey && !worktreePath && project && (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-950/20"
          onClick={handleCreateWorktree}
          disabled={worktreeCreating}
          title="Create worktree for this JIRA ticket"
        >
          <FolderPlus className="h-3.5 w-3.5 mr-1" />
          <span className="text-xs">{worktreeCreating ? "Creating..." : "Create Worktree"}</span>
        </Button>
      )}
      {/* Show Terminal button if has worktree or working directory */}
      {(worktreePath || workingDirectory) && (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-zinc-400 hover:text-zinc-200"
          onClick={handleLaunchTerminal}
          disabled={terminalLaunching}
          title={`Open terminal in ${worktreePath || workingDirectory}`}
        >
          <Terminal className="h-3.5 w-3.5 mr-1" />
          <span className="text-xs">Terminal</span>
        </Button>
      )}
    </div>
  );
}
