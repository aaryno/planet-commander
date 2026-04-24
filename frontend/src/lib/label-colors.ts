const CATEGORY_COLORS: Record<string, string> = {
  project: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  "task-type": "bg-purple-500/20 text-purple-400 border-purple-500/30",
  priority: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  scope: "bg-slate-500/20 text-slate-400 border-slate-500/30",
  status: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  custom: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
};

const LABEL_COLORS: Record<string, string> = {
  wx: "bg-blue-500/20 text-blue-300 border-blue-500/40",
  g4: "bg-violet-500/20 text-violet-300 border-violet-500/40",
  jobs: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  temporal: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  investigation: "bg-red-500/20 text-red-300 border-red-500/40",
  "code-review": "bg-indigo-500/20 text-indigo-300 border-indigo-500/40",
  incident: "bg-red-600/20 text-red-400 border-red-600/40",
  feature: "bg-green-500/20 text-green-300 border-green-500/40",
  "bug-fix": "bg-orange-500/20 text-orange-300 border-orange-500/40",
  critical: "bg-red-600/20 text-red-400 border-red-600/40",
  high: "bg-orange-500/20 text-orange-300 border-orange-500/40",
  medium: "bg-yellow-500/20 text-yellow-300 border-yellow-500/40",
  low: "bg-gray-500/20 text-gray-300 border-gray-500/40",
};

export function getLabelColor(name: string, category?: string): string {
  return LABEL_COLORS[name] || CATEGORY_COLORS[category || "custom"] || CATEGORY_COLORS.custom;
}
