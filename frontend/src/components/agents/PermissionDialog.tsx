"use client";

import { useState, useMemo } from "react";
import { ShieldAlert } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { PermissionDenialEvent } from "@/hooks/useAgentChat";

interface PermissionDialogProps {
  denial: PermissionDenialEvent | null;
  onClose: () => void;
  onGranted?: (tool: string) => void;
}

function generatePatternOptions(
  toolName: string,
  toolInput: Record<string, unknown>
): { label: string; value: string; description: string }[] {
  if (toolName === "Bash" && toolInput.command) {
    const cmd = String(toolInput.command);
    const parts = cmd.split(/\s+/);
    const firstWord = parts[0] || cmd;

    const options = [
      {
        label: `Bash(${cmd})`,
        value: `Bash(${cmd})`,
        description: "Exact command only",
      },
    ];

    if (parts.length > 1) {
      options.push({
        label: `Bash(${firstWord} *)`,
        value: `Bash(${firstWord} *)`,
        description: `Any ${firstWord} command`,
      });
    }

    options.push({
      label: "Bash",
      value: "Bash",
      description: "All shell commands (broad)",
    });

    return options;
  }

  if (toolName === "mcp__" || toolName.startsWith("mcp__")) {
    const parts = toolName.split("__");
    return [
      {
        label: toolName,
        value: toolName,
        description: "This specific MCP tool",
      },
      ...(parts.length > 2
        ? [
            {
              label: `${parts[0]}__${parts[1]}__*`,
              value: `${parts[0]}__${parts[1]}__*`,
              description: `All tools from ${parts[1]} server`,
            },
          ]
        : []),
    ];
  }

  return [
    {
      label: toolName,
      value: toolName,
      description: `Allow ${toolName} tool`,
    },
  ];
}

export function PermissionDialog({ denial, onClose, onGranted }: PermissionDialogProps) {
  const [selected, setSelected] = useState<string>("");
  const [saving, setSaving] = useState(false);

  const options = useMemo(() => {
    if (!denial) return [];
    const opts = generatePatternOptions(denial.tool_name, denial.tool_input);
    if (opts.length > 0 && !selected) {
      const defaultIdx = opts.length > 1 ? 1 : 0;
      setSelected(opts[defaultIdx].value);
    }
    return opts;
  }, [denial]);

  if (!denial) return null;

  const inputPreview =
    denial.tool_name === "Bash" && denial.tool_input.command
      ? String(denial.tool_input.command)
      : Object.keys(denial.tool_input).length > 0
        ? JSON.stringify(denial.tool_input, null, 2)
        : null;

  const handleAddRule = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      await api.addPermission(selected);
      onGranted?.(selected);
      onClose();
    } catch (err) {
      console.error("Failed to add permission:", err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={!!denial} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="bg-zinc-900 border-zinc-700 text-zinc-100 sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-amber-400">
            <ShieldAlert className="h-5 w-5" />
            Permission Request
          </DialogTitle>
          <DialogDescription className="text-zinc-400">
            An agent tried to use a tool that isn&apos;t in the allowed list.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="rounded-md border border-zinc-700 bg-zinc-800 p-3 space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-500">Tool:</span>
              <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
                {denial.tool_name}
              </Badge>
            </div>
            {inputPreview && (
              <div>
                <span className="text-xs text-zinc-500">Input:</span>
                <pre className="mt-1 text-xs text-zinc-300 bg-zinc-950 rounded p-2 overflow-x-auto max-h-32">
                  {inputPreview}
                </pre>
              </div>
            )}
          </div>

          <div className="space-y-2">
            <p className="text-sm text-zinc-400">Add to allowed tools as:</p>
            {options.map((opt) => (
              <label
                key={opt.value}
                className={`flex items-start gap-3 p-2 rounded-md border cursor-pointer transition-colors ${
                  selected === opt.value
                    ? "border-blue-500/50 bg-blue-500/10"
                    : "border-zinc-700 hover:border-zinc-600"
                }`}
              >
                <input
                  type="radio"
                  name="permission-pattern"
                  value={opt.value}
                  checked={selected === opt.value}
                  onChange={(e) => setSelected(e.target.value)}
                  className="mt-1 accent-blue-500"
                />
                <div>
                  <code className="text-sm text-zinc-200">{opt.label}</code>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    {opt.description}
                  </p>
                </div>
              </label>
            ))}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="border-zinc-700 text-zinc-300">
            Deny
          </Button>
          <Button
            onClick={handleAddRule}
            disabled={!selected || saving}
            className="bg-blue-600 hover:bg-blue-700 text-white"
          >
            {saving ? "Adding..." : "Add Rule"}
          </Button>
        </DialogFooter>

        <p className="text-xs text-zinc-600 text-center">
          Rule applies to all agents on next message. Re-send the message after
          adding.
        </p>
      </DialogContent>
    </Dialog>
  );
}
