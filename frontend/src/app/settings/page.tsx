"use client";

import { useState } from "react";
import { Tags, Layout, Terminal as TerminalIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getLabelColor } from "@/lib/label-colors";
import { useSettings } from "@/hooks/useSettings";

const LABEL_GROUPS = {
  project: [
    { name: "wx", color: "#3B82F6" },
    { name: "g4", color: "#8B5CF6" },
    { name: "jobs", color: "#F59E0B" },
    { name: "temporal", color: "#10B981" },
  ],
  "task-type": [
    { name: "investigation" },
    { name: "code-review" },
    { name: "incident" },
    { name: "feature" },
    { name: "bug-fix" },
    { name: "analysis" },
    { name: "documentation" },
    { name: "deployment" },
    { name: "refactor" },
    { name: "planning" },
    { name: "review" },
  ],
  priority: [
    { name: "critical" },
    { name: "high" },
    { name: "medium" },
    { name: "low" },
  ],
  scope: [
    { name: "single-file" },
    { name: "multi-file" },
    { name: "cross-repo" },
    { name: "cross-project" },
  ],
  status: [
    { name: "blocked" },
    { name: "needs-review" },
    { name: "follow-up" },
  ],
};

const TERMINAL_APPS = [
  { id: "ghostty", name: "Ghostty", command: "open -a Ghostty {path}" },
  { id: "iterm2", name: "iTerm2", command: "open -a iTerm {path}" },
  { id: "terminal", name: "Terminal.app", command: "open -a Terminal {path}" },
  { id: "warp", name: "Warp", command: "open -a Warp {path}" },
  { id: "kitty", name: "Kitty", command: "open -a Kitty {path}" },
  { id: "custom", name: "Custom", command: "" },
];

export default function SettingsPage() {
  const { settings, updateTerminalApp } = useSettings();
  const [customCommand, setCustomCommand] = useState(settings.terminal.customCommand || "");

  const handleTerminalChange = (appId: string) => {
    const app = TERMINAL_APPS.find(a => a.id === appId);
    if (app) {
      if (appId === "custom") {
        updateTerminalApp(appId, customCommand);
      } else {
        updateTerminalApp(appId, app.command);
      }
    }
  };

  const handleCustomCommandChange = (cmd: string) => {
    setCustomCommand(cmd);
    if (settings.terminal.app === "custom") {
      updateTerminalApp("custom", cmd);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Settings</h1>
        <p className="text-sm text-zinc-500">Dashboard configuration and preferences</p>
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
        <div className="flex items-center gap-2 mb-4">
          <TerminalIcon className="h-4 w-4 text-zinc-400" />
          <h2 className="text-sm font-medium text-zinc-200">Terminal Application</h2>
        </div>

        <div className="space-y-4">
          <p className="text-sm text-zinc-500">
            Choose which terminal application to open when clicking the Terminal button on agent cards.
          </p>

          <div className="grid grid-cols-2 gap-2">
            {TERMINAL_APPS.map((app) => (
              <button
                key={app.id}
                onClick={() => handleTerminalChange(app.id)}
                className={`p-3 rounded-md border text-left transition-colors ${
                  settings.terminal.app === app.id
                    ? "border-emerald-600 bg-emerald-600/10 text-emerald-400"
                    : "border-zinc-700 bg-zinc-800/50 text-zinc-400 hover:border-zinc-600 hover:text-zinc-300"
                }`}
              >
                <div className="font-medium text-sm">{app.name}</div>
                {app.id !== "custom" && (
                  <div className="text-xs text-zinc-500 mt-1 font-mono truncate">
                    {app.command}
                  </div>
                )}
              </button>
            ))}
          </div>

          {settings.terminal.app === "custom" && (
            <div className="space-y-2">
              <label className="text-xs text-zinc-500">
                Custom Command (use {"{path}"} as placeholder for directory)
              </label>
              <Input
                value={customCommand}
                onChange={(e) => handleCustomCommandChange(e.target.value)}
                placeholder="open -a MyTerminal {path}"
                className="bg-zinc-800/50 border-zinc-700 text-zinc-300 font-mono text-xs"
              />
              <p className="text-xs text-zinc-600">
                Example: <code className="text-zinc-500">open -a Ghostty --args --working-directory {"{path}"}</code>
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
        <div className="flex items-center gap-2 mb-4">
          <Layout className="h-4 w-4 text-zinc-400" />
          <h2 className="text-sm font-medium text-zinc-200">Dashboard Layout</h2>
        </div>
        <p className="text-sm text-zinc-500">
          Drag-and-drop layout configuration coming in Phase 1 enhancement.
          Currently using default grid layout.
        </p>
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
        <div className="flex items-center gap-2 mb-4">
          <Tags className="h-4 w-4 text-zinc-400" />
          <h2 className="text-sm font-medium text-zinc-200">Label Taxonomy</h2>
        </div>

        <div className="space-y-4">
          {Object.entries(LABEL_GROUPS).map(([category, labels]) => (
            <div key={category}>
              <h3 className="text-xs font-medium uppercase text-zinc-500 mb-2">
                {category}
              </h3>
              <div className="flex flex-wrap gap-2">
                {labels.map((label) => (
                  <Badge
                    key={label.name}
                    variant="outline"
                    className={`${getLabelColor(label.name, category)} border text-xs`}
                  >
                    {label.name}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
