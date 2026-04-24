"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, Code, Eye, Plus, ShieldCheck, Trash2, X } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

const KNOWN_TOOLS = [
  "Read", "Edit", "Write", "Glob", "Grep",
  "Bash", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet",
  "NotebookEdit", "Agent", "WebFetch", "WebSearch",
];

function categorize(tools: string[]): Record<string, string[]> {
  const categories: Record<string, string[]> = {
    "File Operations": [],
    "Shell Commands": [],
    "Task Management": [],
    "Other": [],
  };

  for (const tool of tools) {
    if (["Read", "Edit", "Write", "Glob", "Grep"].includes(tool)) {
      categories["File Operations"].push(tool);
    } else if (tool.startsWith("Bash")) {
      categories["Shell Commands"].push(tool);
    } else if (tool.startsWith("Task")) {
      categories["Task Management"].push(tool);
    } else {
      categories["Other"].push(tool);
    }
  }

  return Object.fromEntries(
    Object.entries(categories).filter(([, v]) => v.length > 0)
  );
}

export default function PermissionsPage() {
  const [tools, setTools] = useState<string[]>([]);
  const [rawContent, setRawContent] = useState("");
  const [mode, setMode] = useState<"visual" | "text">("visual");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [newTool, setNewTool] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchPermissions = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getPermissions();
      setTools(data.tools);
      setRawContent(data.raw);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load permissions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPermissions();
  }, [fetchPermissions]);

  const handleRemove = async (tool: string) => {
    try {
      const data = await api.removePermission(tool);
      setTools(data.tools);
      setRawContent(data.raw);
      setLastSaved(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove");
    }
  };

  const handleAdd = async () => {
    const trimmed = newTool.trim();
    if (!trimmed) return;
    try {
      const data = await api.addPermission(trimmed);
      setTools(data.tools);
      setRawContent(data.raw);
      setNewTool("");
      setShowAddForm(false);
      setLastSaved(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add");
    }
  };

  const handleRawChange = (value: string) => {
    setRawContent(value);

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      const lines = value.split("\n").map(l => l.trim()).filter(l => l && !l.startsWith("#"));
      if (lines.length === 0 && value.trim().length > 0) return;

      try {
        setSaving(true);
        const data = await api.updatePermissions(value);
        setTools(data.tools);
        setRawContent(data.raw);
        setLastSaved(new Date());
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to save");
      } finally {
        setSaving(false);
      }
    }, 1000);
  };

  const categories = categorize(tools);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="max-w-3xl mx-auto p-8">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <Link href="/settings">
            <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-zinc-200">
              <ArrowLeft className="h-4 w-4 mr-1" />
              Settings
            </Button>
          </Link>
        </div>

        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <ShieldCheck className="h-6 w-6 text-blue-400" />
            <div>
              <h1 className="text-xl font-bold">Agent Permissions</h1>
              <p className="text-sm text-zinc-500">
                Tools auto-approved for Commander-spawned agents
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setMode("visual")}
              className={mode === "visual" ? "bg-zinc-800 text-zinc-200" : "text-zinc-500"}
            >
              <Eye className="h-4 w-4 mr-1" />
              Visual
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setMode("text")}
              className={mode === "text" ? "bg-zinc-800 text-zinc-200" : "text-zinc-500"}
            >
              <Code className="h-4 w-4 mr-1" />
              Text
            </Button>
          </div>
        </div>

        {/* Status bar */}
        <div className="flex items-center justify-between mb-4 text-xs text-zinc-500">
          <span>{tools.length} tool patterns configured</span>
          <div className="flex items-center gap-2">
            {saving && <span className="text-amber-400">Saving...</span>}
            {lastSaved && !saving && (
              <span className="text-emerald-400">
                Saved {lastSaved.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-md border border-red-500/30 bg-red-500/10 text-red-400 text-sm flex items-center justify-between">
            {error}
            <button onClick={() => setError(null)}>
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        <div className="rounded-md border border-zinc-800 bg-zinc-900 p-1 mb-4">
          <p className="text-xs text-zinc-500 px-3 py-2">
            Changes apply to all agent sessions on their next message.
          </p>
        </div>

        {loading ? (
          <div className="text-center text-zinc-500 py-12">Loading...</div>
        ) : mode === "visual" ? (
          /* Visual mode */
          <div className="space-y-6">
            {Object.entries(categories).map(([category, catTools]) => (
              <div key={category}>
                <h3 className="text-sm font-semibold text-zinc-400 mb-2">{category}</h3>
                <div className="space-y-1">
                  {catTools.map((tool) => (
                    <div
                      key={tool}
                      className="flex items-center justify-between p-2 rounded-md hover:bg-zinc-800 group"
                    >
                      <code className="text-sm text-zinc-200">{tool}</code>
                      <button
                        onClick={() => handleRemove(tool)}
                        className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-300 transition-opacity"
                        title="Remove"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ))}

            {/* Add tool */}
            {showAddForm ? (
              <div className="flex items-center gap-2">
                <Input
                  value={newTool}
                  onChange={(e) => setNewTool(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAdd()}
                  placeholder='e.g. Bash(docker *) or Write'
                  className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm flex-1"
                  autoFocus
                  list="known-tools"
                />
                <datalist id="known-tools">
                  {KNOWN_TOOLS.filter(t => !tools.includes(t)).map(t => (
                    <option key={t} value={t} />
                  ))}
                </datalist>
                <Button size="sm" onClick={handleAdd} className="bg-blue-600 hover:bg-blue-700">
                  Add
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => { setShowAddForm(false); setNewTool(""); }}
                  className="text-zinc-500"
                >
                  Cancel
                </Button>
              </div>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAddForm(true)}
                className="border-zinc-700 text-zinc-400 hover:text-zinc-200"
              >
                <Plus className="h-4 w-4 mr-1" />
                Add Tool
              </Button>
            )}
          </div>
        ) : (
          /* Text mode */
          <div>
            <textarea
              value={rawContent}
              onChange={(e) => handleRawChange(e.target.value)}
              className="w-full h-[500px] bg-zinc-950 border border-zinc-700 rounded-md p-4 font-mono text-sm text-zinc-200 resize-y focus:outline-none focus:border-blue-500"
              spellCheck={false}
            />
            <p className="text-xs text-zinc-600 mt-2">
              One tool per line. Lines starting with # are comments. Auto-saves after 1 second.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
