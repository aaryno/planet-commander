"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft, BarChart2, Bell, Check, GitBranch, Loader2, MessageCircle,
  Palette, Plus, Rocket, Settings, Tag, Trash2, X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { ProjectConfig } from "@/lib/api";

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4 space-y-3">
      <div className="flex items-center gap-2">
        {icon}
        <h2 className="text-sm font-medium text-zinc-200">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function ListEditor({
  items,
  onAdd,
  onRemove,
  renderItem,
  addPlaceholder,
  addFields,
  dedupKey,
}: {
  items: Record<string, unknown>[];
  onAdd: (item: Record<string, unknown>) => void;
  onRemove: (index: number) => void;
  renderItem: (item: Record<string, unknown>, index: number) => React.ReactNode;
  addPlaceholder: string;
  addFields: { key: string; placeholder: string; required?: boolean }[];
  dedupKey?: string;
}) {
  const [adding, setAdding] = useState(false);
  const [newValues, setNewValues] = useState<Record<string, string>>({});
  const [dupError, setDupError] = useState(false);

  const handleAdd = () => {
    const missing = addFields.filter(f => f.required && !newValues[f.key]?.trim());
    if (missing.length > 0) return;

    const newItem = Object.fromEntries(
      addFields.map(f => [f.key, newValues[f.key]?.trim() || ""])
    );

    const key = dedupKey || addFields.find(f => f.required)?.key || addFields[0]?.key;
    if (key && items.some(existing => String(existing[key]) === String(newItem[key]))) {
      setDupError(true);
      setTimeout(() => setDupError(false), 2000);
      return;
    }

    onAdd(newItem);
    setNewValues({});
    setAdding(false);
  };

  return (
    <div className="space-y-1">
      {items.map((item, i) => (
        <div key={i} className="flex items-center justify-between group px-2 py-1 rounded hover:bg-zinc-800">
          <div className="flex-1 min-w-0">{renderItem(item, i)}</div>
          <button
            onClick={() => onRemove(i)}
            className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-300 transition-opacity ml-2"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
      {adding ? (
        <div className="flex items-center gap-2 px-2 py-1">
          {addFields.map(f => (
            <Input
              key={f.key}
              value={newValues[f.key] || ""}
              onChange={e => setNewValues(prev => ({ ...prev, [f.key]: e.target.value }))}
              onKeyDown={e => e.key === "Enter" && handleAdd()}
              placeholder={f.placeholder}
              className="bg-zinc-800 border-zinc-700 text-zinc-200 text-xs h-7 flex-1"
              autoFocus={f === addFields[0]}
            />
          ))}
          <Button size="sm" onClick={handleAdd} className="bg-blue-600 hover:bg-blue-700 h-7 text-xs px-2">Add</Button>
          <Button size="sm" variant="ghost" onClick={() => { setAdding(false); setNewValues({}); setDupError(false); }} className="text-zinc-500 h-7 text-xs px-2">Cancel</Button>
        </div>
        {dupError && <p className="text-xs text-amber-400 px-2">Already exists</p>}
      ) : (
        <button
          onClick={() => setAdding(true)}
          className="flex items-center gap-1 px-2 py-1 text-xs text-zinc-500 hover:text-zinc-300"
        >
          <Plus className="h-3 w-3" /> {addPlaceholder}
        </button>
      )}
    </div>
  );
}

const PRESET_COLORS = [
  "#3B82F6", "#8B5CF6", "#F59E0B", "#10B981", "#EC4899",
  "#14B8A6", "#F97316", "#6366F1", "#EF4444", "#84CC16",
];

export default function ProjectSettingsPage({
  params,
}: {
  params: Promise<{ key: string }>;
}) {
  const { key } = use(params);
  const router = useRouter();
  const [project, setProject] = useState<ProjectConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    api.getProject(key)
      .then(setProject)
      .catch(e => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [key]);

  const save = useCallback(
    (updates: Partial<ProjectConfig>) => {
      if (!project) return;
      const merged = { ...project, ...updates };
      setProject(merged);

      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(async () => {
        setSaving(true);
        try {
          const saved = await api.updateProject(key, updates);
          setProject(saved);
          setLastSaved(new Date());
          setError(null);
        } catch (e) {
          setError(e instanceof Error ? e.message : "Save failed");
        } finally {
          setSaving(false);
        }
      }, 600);
    },
    [project, key]
  );

  if (loading) return <div className="flex items-center justify-center h-64 text-zinc-500">Loading...</div>;
  if (!project) return <div className="flex items-center justify-center h-64 text-red-400">{error || "Not found"}</div>;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="max-w-3xl mx-auto p-8">
        {/* Header */}
        <div className="flex items-center gap-3 mb-2">
          <Link href={`/projects/${key}`}>
            <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-zinc-200">
              <ArrowLeft className="h-4 w-4 mr-1" />
              {project.name}
            </Button>
          </Link>
        </div>
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Settings className="h-6 w-6 text-zinc-400" />
            <h1 className="text-xl font-bold">Project Settings</h1>
          </div>
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            {saving && <><Loader2 className="h-3 w-3 animate-spin" /> Saving...</>}
            {lastSaved && !saving && <><Check className="h-3 w-3 text-emerald-400" /> Saved {lastSaved.toLocaleTimeString()}</>}
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-md border border-red-500/30 bg-red-500/10 text-red-400 text-sm flex items-center justify-between">
            {error}
            <button onClick={() => setError(null)}><X className="h-4 w-4" /></button>
          </div>
        )}

        <div className="space-y-4">
          {/* General */}
          <Section title="General" icon={<Palette className="h-4 w-4 text-zinc-400" />}>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-zinc-500 mb-1 block">Name</label>
                <Input
                  value={project.name}
                  onChange={e => save({ name: e.target.value })}
                  className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-zinc-500 mb-1 block">Key (read-only)</label>
                <Input value={project.key} disabled className="bg-zinc-800/50 border-zinc-700 text-zinc-500 text-sm" />
              </div>
            </div>
            <div>
              <label className="text-xs text-zinc-500 mb-1 block">Description</label>
              <Input
                value={project.description || ""}
                onChange={e => save({ description: e.target.value || null })}
                placeholder="One-sentence description"
                className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-zinc-500 mb-1 block">Color</label>
              <div className="flex items-center gap-2">
                {PRESET_COLORS.map(c => (
                  <button
                    key={c}
                    onClick={() => save({ color: c })}
                    className={`w-6 h-6 rounded-full border-2 transition-all ${project.color === c ? "border-white scale-110" : "border-transparent hover:border-zinc-500"}`}
                    style={{ backgroundColor: c }}
                  />
                ))}
                <Input
                  value={project.color}
                  onChange={e => save({ color: e.target.value })}
                  className="bg-zinc-800 border-zinc-700 text-zinc-200 text-xs w-24 ml-2"
                  placeholder="#hex"
                />
              </div>
            </div>
          </Section>

          {/* Repositories */}
          <Section title="Repositories" icon={<GitBranch className="h-4 w-4 text-zinc-400" />}>
            <ListEditor
              items={project.repositories as Record<string, unknown>[]}
              onAdd={item => save({ repositories: [...project.repositories, item as ProjectConfig["repositories"][0]] })}
              onRemove={i => save({ repositories: project.repositories.filter((_, j) => j !== i) })}
              dedupKey="path"
              renderItem={item => (
                <div className="flex items-center gap-2">
                  <GitBranch className="h-3 w-3 text-zinc-500 shrink-0" />
                  <code className="text-xs text-zinc-300">{String(item.path)}</code>
                  {item.name && <span className="text-xs text-zinc-500">({String(item.name)})</span>}
                </div>
              )}
              addPlaceholder="Add repository"
              addFields={[
                { key: "path", placeholder: "group/repo (e.g. wx/wx)", required: true },
                { key: "name", placeholder: "Display name" },
              ]}
            />
          </Section>

          {/* JIRA */}
          <Section title="JIRA Configuration" icon={<Tag className="h-4 w-4 text-zinc-400" />}>
            <div>
              <label className="text-xs text-zinc-500 mb-1 block">Project Keys</label>
              <div className="flex items-center gap-2 flex-wrap">
                {project.jira_project_keys.map((k, i) => (
                  <Badge key={i} className="bg-blue-500/20 text-blue-400 border-blue-500/30 gap-1">
                    {k}
                    <button onClick={() => save({ jira_project_keys: project.jira_project_keys.filter((_, j) => j !== i) })}>
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
                <Input
                  placeholder="Add key (e.g. COMPUTE)"
                  className="bg-zinc-800 border-zinc-700 text-zinc-200 text-xs w-40 h-7"
                  onKeyDown={e => {
                    if (e.key === "Enter" && (e.target as HTMLInputElement).value.trim()) {
                      const val = (e.target as HTMLInputElement).value.trim().toUpperCase();
                      if (!project.jira_project_keys.includes(val)) {
                        save({ jira_project_keys: [...project.jira_project_keys, val] });
                      }
                      (e.target as HTMLInputElement).value = "";
                    }
                  }}
                />
              </div>
            </div>
            <div>
              <label className="text-xs text-zinc-500 mb-1 block">Label Filters</label>
              <div className="flex items-center gap-2 flex-wrap">
                {(project.jira_default_filters.label_filters || []).map((l, i) => (
                  <Badge key={i} className="bg-zinc-700/50 text-zinc-300 gap-1">
                    {l}
                    <button onClick={() => {
                      const labels = [...(project.jira_default_filters.label_filters || [])];
                      labels.splice(i, 1);
                      save({ jira_default_filters: { ...project.jira_default_filters, label_filters: labels } });
                    }}><X className="h-3 w-3" /></button>
                  </Badge>
                ))}
                <Input
                  placeholder="Add label"
                  className="bg-zinc-800 border-zinc-700 text-zinc-200 text-xs w-32 h-7"
                  onKeyDown={e => {
                    if (e.key === "Enter" && (e.target as HTMLInputElement).value.trim()) {
                      const val = (e.target as HTMLInputElement).value.trim();
                      const labels = [...(project.jira_default_filters.label_filters || [])];
                      if (!labels.includes(val)) labels.push(val);
                      save({ jira_default_filters: { ...project.jira_default_filters, label_filters: labels } });
                      (e.target as HTMLInputElement).value = "";
                    }
                  }}
                />
              </div>
            </div>
          </Section>

          {/* Monitoring */}
          <Section title="Monitoring" icon={<BarChart2 className="h-4 w-4 text-zinc-400" />}>
            <ListEditor
              items={project.grafana_dashboards as Record<string, unknown>[]}
              onAdd={item => save({ grafana_dashboards: [...project.grafana_dashboards, item as ProjectConfig["grafana_dashboards"][0]] })}
              onRemove={i => save({ grafana_dashboards: project.grafana_dashboards.filter((_, j) => j !== i) })}
              dedupKey="url"
              renderItem={item => (
                <div className="flex items-center gap-2">
                  <BarChart2 className="h-3 w-3 text-zinc-500 shrink-0" />
                  <span className="text-xs text-zinc-300">{String(item.name)}</span>
                  <a href={String(item.url)} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-400 hover:text-blue-300 truncate">{String(item.url)}</a>
                </div>
              )}
              addPlaceholder="Add dashboard"
              addFields={[
                { key: "name", placeholder: "Dashboard name", required: true },
                { key: "url", placeholder: "https://grafana.../d/...", required: true },
              ]}
            />
          </Section>

          {/* Slack */}
          <Section title="Slack Channels" icon={<MessageCircle className="h-4 w-4 text-zinc-400" />}>
            <ListEditor
              items={project.slack_channels as Record<string, unknown>[]}
              onAdd={item => save({ slack_channels: [...project.slack_channels, item as ProjectConfig["slack_channels"][0]] })}
              onRemove={i => save({ slack_channels: project.slack_channels.filter((_, j) => j !== i) })}
              dedupKey="name"
              renderItem={item => (
                <div className="flex items-center gap-2">
                  <MessageCircle className="h-3 w-3 text-zinc-500 shrink-0" />
                  <span className="text-xs text-zinc-300">{String(item.name)}</span>
                  <span className="text-xs text-zinc-600">{String(item.purpose || "")}</span>
                </div>
              )}
              addPlaceholder="Add channel"
              addFields={[
                { key: "name", placeholder: "#channel-name", required: true },
                { key: "purpose", placeholder: "general / alerts / oncall" },
              ]}
            />
          </Section>

          {/* PagerDuty */}
          <Section title="PagerDuty" icon={<Bell className="h-4 w-4 text-zinc-400" />}>
            <div className="flex items-center gap-2 flex-wrap">
              {project.pagerduty_service_ids.map((id, i) => (
                <Badge key={i} className="bg-amber-500/20 text-amber-400 border-amber-500/30 gap-1">
                  {id}
                  <button onClick={() => save({ pagerduty_service_ids: project.pagerduty_service_ids.filter((_, j) => j !== i) })}>
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
              <Input
                placeholder="Service ID (e.g. PXXXXXX)"
                className="bg-zinc-800 border-zinc-700 text-zinc-200 text-xs w-40 h-7"
                onKeyDown={e => {
                  if (e.key === "Enter" && (e.target as HTMLInputElement).value.trim()) {
                    const val = (e.target as HTMLInputElement).value.trim();
                    if (!project.pagerduty_service_ids.includes(val)) {
                      save({ pagerduty_service_ids: [...project.pagerduty_service_ids, val] });
                    }
                    (e.target as HTMLInputElement).value = "";
                  }
                }}
              />
            </div>
          </Section>

          {/* Deployments */}
          <Section title="Deployments" icon={<Rocket className="h-4 w-4 text-zinc-400" />}>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-zinc-500 mb-1 block">Type</label>
                <Input
                  value={project.deployment_config?.type as string || ""}
                  onChange={e => save({ deployment_config: { ...project.deployment_config, type: e.target.value || undefined } })}
                  placeholder="argocd / k8s / terraform / none"
                  className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-zinc-500 mb-1 block">Cluster</label>
                <Input
                  value={project.deployment_config?.cluster as string || ""}
                  onChange={e => save({ deployment_config: { ...project.deployment_config, cluster: e.target.value || undefined } })}
                  placeholder="e.g. compute-03"
                  className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm"
                />
              </div>
            </div>
          </Section>

          {/* Danger zone */}
          <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-4">
            <h2 className="text-sm font-medium text-red-400 mb-2">Danger Zone</h2>
            <Button
              variant="outline"
              size="sm"
              className="border-red-800 text-red-400 hover:bg-red-900/30"
              onClick={async () => {
                if (!confirm(`Archive project "${project.name}"? It will be hidden but not deleted.`)) return;
                await api.deleteProject(key);
                router.push("/");
              }}
            >
              Archive Project
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
