/**
 * Centralized status/state color mappings.
 * Replaces 10+ duplicate color mapping objects across the codebase.
 *
 * Convention: "text-{color} border-{color}/30 bg-{color}/10"
 */

// -- JIRA --

export const JIRA_STATUS_COLORS: Record<string, string> = {
  "Selected for Development": "bg-blue-500/10 text-blue-300 border-blue-500/20",
  "In Progress": "bg-blue-500/15 text-blue-400 border-blue-500/30",
  "In Review": "bg-blue-500/20 text-blue-400 border-blue-500/40",
  "Code Review": "bg-blue-500/20 text-blue-400 border-blue-500/40",
  "Ready to Deploy": "bg-blue-500/25 text-blue-500 border-blue-500/50",
  "Released to Staging": "bg-blue-500/30 text-blue-500 border-blue-500/60",
  "Monitoring": "bg-blue-500/35 text-blue-600 border-blue-500/70",
  "Done": "bg-emerald-500/40 text-emerald-500 border-emerald-500/80",
  "Blocked": "bg-red-600/20 text-red-400 border-red-600/30",
  "Backlog": "bg-zinc-500/10 text-zinc-400 border-zinc-600/30",
};

export const JIRA_PRIORITY_COLORS: Record<string, string> = {
  "Highest": "text-red-400",
  "High": "text-orange-400",
  "Medium": "text-yellow-400",
  "Low": "text-zinc-500",
  "Lowest": "text-zinc-600",
};

// -- GitLab MRs --

export const MR_STATE_COLORS: Record<string, string> = {
  opened: "text-blue-400 border-blue-500/30",
  merged: "text-emerald-400 border-emerald-500/30",
  closed: "text-zinc-400 border-zinc-600/30",
};

export const MR_APPROVAL_COLORS: Record<string, string> = {
  approved: "text-emerald-400 border-emerald-500/30",
  pending: "text-amber-400 border-amber-500/30",
  changes_requested: "text-red-400 border-red-500/30",
};

export const CI_STATUS_COLORS: Record<string, string> = {
  passed: "text-emerald-400 border-emerald-500/30",
  running: "text-blue-400 border-blue-500/30",
  failed: "text-red-400 border-red-500/30",
  skipped: "text-zinc-400 border-zinc-600/30",
};

// -- PagerDuty --

export const PD_STATUS_COLORS: Record<string, string> = {
  triggered: "text-red-400 border-red-500/30 bg-red-500/10",
  acknowledged: "text-amber-400 border-amber-500/30 bg-amber-500/10",
  resolved: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
};

export const PD_URGENCY_COLORS: Record<string, string> = {
  high: "text-red-400 border-red-500/30",
  low: "text-blue-400 border-blue-500/30",
};

// -- Agents --

export const AGENT_STATUS_COLORS: Record<string, string> = {
  active: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
  idle: "text-blue-400 border-blue-500/30 bg-blue-500/10",
  dead: "text-zinc-400 border-zinc-600/30 bg-zinc-500/10",
  error: "text-red-400 border-red-500/30 bg-red-500/10",
};

// -- Projects --

export const PROJECT_COLORS: Record<string, string> = {
  wx: "text-blue-400",
  g4: "text-violet-400",
  jobs: "text-amber-400",
  temporal: "text-emerald-400",
};

export const PROJECT_BADGE_COLORS: Record<string, string> = {
  wx: "text-blue-400 border-blue-600/50 bg-blue-500/10",
  jobs: "text-purple-400 border-purple-600/50 bg-purple-500/10",
  g4: "text-orange-400 border-orange-600/50 bg-orange-500/10",
  temporal: "text-pink-400 border-pink-600/50 bg-pink-500/10",
};

// -- Deployments --

export const ENV_COLORS: Record<string, string> = {
  prod: "text-emerald-400 border-emerald-600/50 bg-emerald-500/10",
  staging: "text-amber-400 border-amber-600/50 bg-amber-500/10",
  dev: "text-blue-400 border-blue-600/50 bg-blue-500/10",
};

// -- Alerts --

export const ALERT_SEVERITY_COLORS: Record<string, string> = {
  critical: "text-red-400 border-red-500/30 bg-red-500/10",
  warning: "text-amber-400 border-amber-500/30 bg-amber-500/10",
  info: "text-blue-400 border-blue-500/30 bg-blue-500/10",
};

// -- Generic helpers --

/** Get a color class for any status, with fallback */
export function getStatusColor(
  colorMap: Record<string, string>,
  status: string,
  fallback = "text-zinc-400 border-zinc-600/30 bg-zinc-500/10"
): string {
  return colorMap[status] || fallback;
}
