"use client";

import { useState } from "react";
import { ArrowLeft, ArrowRight, Check, Loader2, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { ProjectConfig } from "@/lib/api";

const PRESET_COLORS = [
  "#3B82F6", "#8B5CF6", "#F59E0B", "#10B981", "#EC4899",
  "#14B8A6", "#F97316", "#6366F1", "#EF4444", "#84CC16",
];

export default function NewProjectPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState(PRESET_COLORS[4]);

  const [jiraKeys, setJiraKeys] = useState<string[]>([]);
  const [jiraKeyInput, setJiraKeyInput] = useState("");

  const [repos, setRepos] = useState<{ path: string; name: string }[]>([]);
  const [repoPath, setRepoPath] = useState("");
  const [repoName, setRepoName] = useState("");

  const handleCreate = async () => {
    setCreating(true);
    setError(null);
    try {
      await api.createProject({
        key,
        name,
        description: description || null,
        color,
        jira_project_keys: jiraKeys,
        repositories: repos,
      } as Partial<ProjectConfig>);
      router.push(`/projects/${key}/settings`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setCreating(false);
    }
  };

  const canAdvance = step === 0 ? key.trim() && name.trim() : true;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="max-w-lg mx-auto p-8">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/">
            <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-zinc-200">
              <ArrowLeft className="h-4 w-4 mr-1" /> Dashboard
            </Button>
          </Link>
        </div>

        <div className="flex items-center gap-3 mb-8">
          <Plus className="h-6 w-6 text-blue-400" />
          <h1 className="text-xl font-bold">New Project</h1>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-2 mb-8">
          {["Identity", "JIRA", "Repos"].map((label, i) => (
            <div key={i} className="flex items-center gap-2">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                i < step ? "bg-emerald-600 text-white" :
                i === step ? "bg-blue-600 text-white" :
                "bg-zinc-800 text-zinc-500"
              }`}>
                {i < step ? <Check className="h-3 w-3" /> : i + 1}
              </div>
              <span className={`text-xs ${i === step ? "text-zinc-200" : "text-zinc-600"}`}>{label}</span>
              {i < 2 && <div className="w-8 h-px bg-zinc-800" />}
            </div>
          ))}
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-md border border-red-500/30 bg-red-500/10 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Step 0: Identity */}
        {step === 0 && (
          <div className="space-y-4">
            <div>
              <label className="text-sm text-zinc-400 mb-1 block">Project Key</label>
              <Input
                value={key}
                onChange={e => setKey(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                placeholder="my-project"
                className="bg-zinc-800 border-zinc-700 text-zinc-200"
                autoFocus
              />
              <p className="text-xs text-zinc-600 mt-1">Lowercase, no spaces. Used in URLs and API.</p>
            </div>
            <div>
              <label className="text-sm text-zinc-400 mb-1 block">Display Name</label>
              <Input
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="My Project"
                className="bg-zinc-800 border-zinc-700 text-zinc-200"
              />
            </div>
            <div>
              <label className="text-sm text-zinc-400 mb-1 block">Description (optional)</label>
              <Input
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="One sentence about what this project does"
                className="bg-zinc-800 border-zinc-700 text-zinc-200"
              />
            </div>
            <div>
              <label className="text-sm text-zinc-400 mb-1 block">Color</label>
              <div className="flex items-center gap-2">
                {PRESET_COLORS.map(c => (
                  <button
                    key={c}
                    onClick={() => setColor(c)}
                    className={`w-7 h-7 rounded-full border-2 transition-all ${
                      color === c ? "border-white scale-110" : "border-transparent hover:border-zinc-500"
                    }`}
                    style={{ backgroundColor: c }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Step 1: JIRA */}
        {step === 1 && (
          <div className="space-y-4">
            <p className="text-sm text-zinc-400">
              What JIRA project keys does this project use? You can add more later in settings.
            </p>
            <div className="flex items-center gap-2 flex-wrap">
              {jiraKeys.map((k, i) => (
                <Badge key={i} className="bg-blue-500/20 text-blue-400 border-blue-500/30 gap-1">
                  {k}
                  <button onClick={() => setJiraKeys(prev => prev.filter((_, j) => j !== i))}>
                    <span className="text-blue-300">×</span>
                  </button>
                </Badge>
              ))}
              <Input
                value={jiraKeyInput}
                onChange={e => setJiraKeyInput(e.target.value.toUpperCase())}
                onKeyDown={e => {
                  if (e.key === "Enter" && jiraKeyInput.trim()) {
                    if (!jiraKeys.includes(jiraKeyInput.trim())) {
                      setJiraKeys(prev => [...prev, jiraKeyInput.trim()]);
                    }
                    setJiraKeyInput("");
                  }
                }}
                placeholder="COMPUTE (press Enter)"
                className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm w-48"
              />
            </div>
            <p className="text-xs text-zinc-600">Skip this step if you don&apos;t use JIRA.</p>
          </div>
        )}

        {/* Step 2: Repos */}
        {step === 2 && (
          <div className="space-y-4">
            <p className="text-sm text-zinc-400">
              What GitLab repos belong to this project? You can add more later.
            </p>
            {repos.map((r, i) => (
              <div key={i} className="flex items-center gap-2 px-2 py-1 rounded bg-zinc-800/50">
                <code className="text-xs text-zinc-300 flex-1">{r.path}</code>
                <span className="text-xs text-zinc-500">{r.name}</span>
                <button onClick={() => setRepos(prev => prev.filter((_, j) => j !== i))} className="text-red-400">
                  <span>×</span>
                </button>
              </div>
            ))}
            <div className="flex items-center gap-2">
              <Input
                value={repoPath}
                onChange={e => setRepoPath(e.target.value)}
                placeholder="group/repo"
                className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm flex-1"
              />
              <Input
                value={repoName}
                onChange={e => setRepoName(e.target.value)}
                placeholder="Display name"
                className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm w-40"
              />
              <Button
                size="sm"
                disabled={!repoPath.trim()}
                onClick={() => {
                  if (repoPath.trim()) {
                    setRepos(prev => [...prev, { path: repoPath.trim(), name: repoName.trim() || repoPath.trim().split("/").pop() || "" }]);
                    setRepoPath("");
                    setRepoName("");
                  }
                }}
                className="bg-blue-600 hover:bg-blue-700"
              >
                Add
              </Button>
            </div>
            <p className="text-xs text-zinc-600">Skip this step to add repos later.</p>
          </div>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between mt-8">
          <Button
            variant="ghost"
            onClick={() => setStep(s => s - 1)}
            disabled={step === 0}
            className="text-zinc-400"
          >
            <ArrowLeft className="h-4 w-4 mr-1" /> Back
          </Button>

          {step < 2 ? (
            <Button
              onClick={() => setStep(s => s + 1)}
              disabled={!canAdvance}
              className="bg-blue-600 hover:bg-blue-700"
            >
              Next <ArrowRight className="h-4 w-4 ml-1" />
            </Button>
          ) : (
            <Button
              onClick={handleCreate}
              disabled={creating || !key.trim() || !name.trim()}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {creating ? <><Loader2 className="h-4 w-4 mr-1 animate-spin" /> Creating...</> : <>Create Project <Check className="h-4 w-4 ml-1" /></>}
            </Button>
          )}
        </div>

        <p className="text-xs text-zinc-600 text-center mt-4">
          You can configure everything else (monitoring, Slack, deployments) in project settings after creation.
        </p>
      </div>
    </div>
  );
}
