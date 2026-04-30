"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { api, ServiceHealthResponse, ServiceDetailResponse, IncidentDetail, TeamGroup, ServiceStatus } from "@/lib/api";
import { usePoll } from "@/lib/polling";
import { cn } from "@/lib/utils";
import { RefreshCw, AlertTriangle, ExternalLink, ChevronDown, ChevronRight, ArrowUpDown, ArrowUp, ArrowDown, Search, X, Clock, User, Siren } from "lucide-react";
import { jiraUrl } from "@/lib/urls";

const COL = {
  service: "w-[40%]",
  green: "w-[10%]",
  yellow: "w-[10%]",
  orange: "w-[10%]",
  red: "w-[10%]",
  total: "w-[8%]",
  prodissue: "w-[12%]",
} as const;

const STATUS_COLORS = {
  green: {
    bg: "bg-emerald-500/15",
    text: "text-emerald-400",
    border: "border-emerald-500/30",
    dot: "bg-emerald-400",
    label: "Healthy",
  },
  yellow: {
    bg: "bg-yellow-500/15",
    text: "text-yellow-400",
    border: "border-yellow-500/30",
    dot: "bg-yellow-400",
    label: "Noisy",
  },
  orange: {
    bg: "bg-orange-500/15",
    text: "text-orange-400",
    border: "border-orange-500/30",
    dot: "bg-orange-400",
    label: "Actionable",
  },
  red: {
    bg: "bg-red-500/15",
    text: "text-red-400",
    border: "border-red-500/30",
    dot: "bg-red-400",
    label: "Critical",
  },
};

const STATUS_RANK: Record<string, number> = { green: 0, yellow: 1, orange: 2, red: 3 };

function StatusDot({ status }: { status: string }) {
  const colors = STATUS_COLORS[status as keyof typeof STATUS_COLORS] || STATUS_COLORS.green;
  return <span className={cn("inline-block w-2 h-2 rounded-full", colors.dot)} />;
}

function StatusBadge({ status }: { status: string }) {
  const colors = STATUS_COLORS[status as keyof typeof STATUS_COLORS] || STATUS_COLORS.green;
  return (
    <span className={cn("px-2 py-0.5 rounded text-xs font-medium", colors.bg, colors.text)}>
      {colors.label}
    </span>
  );
}

function CountCell({ count, status }: { count: number; status: string }) {
  if (count === 0) {
    return <span className="text-zinc-600 text-xs">0</span>;
  }
  const colors = STATUS_COLORS[status as keyof typeof STATUS_COLORS] || STATUS_COLORS.green;
  return <span className={cn("text-xs font-medium", colors.text)}>{count}</span>;
}

function SummaryCards({ data }: { data: ServiceHealthResponse }) {
  const { summary } = data;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 mb-6">
      <div className="bg-zinc-900 rounded-lg border border-zinc-800 p-3">
        <p className="text-xs text-zinc-500 mb-1">Services</p>
        <p className="text-xl font-bold text-zinc-100">{summary.total_services}</p>
      </div>
      <div className={cn("rounded-lg border p-3", STATUS_COLORS.green.bg, STATUS_COLORS.green.border)}>
        <p className="text-xs text-zinc-400 mb-1">Healthy</p>
        <p className={cn("text-xl font-bold", STATUS_COLORS.green.text)}>{summary.green}</p>
      </div>
      <div className={cn("rounded-lg border p-3", STATUS_COLORS.yellow.bg, STATUS_COLORS.yellow.border)}>
        <p className="text-xs text-zinc-400 mb-1">Noisy</p>
        <p className={cn("text-xl font-bold", STATUS_COLORS.yellow.text)}>{summary.yellow}</p>
      </div>
      <div className={cn("rounded-lg border p-3", STATUS_COLORS.orange.bg, STATUS_COLORS.orange.border)}>
        <p className="text-xs text-zinc-400 mb-1">Actionable</p>
        <p className={cn("text-xl font-bold", STATUS_COLORS.orange.text)}>{summary.orange}</p>
      </div>
      <div className={cn("rounded-lg border p-3", STATUS_COLORS.red.bg, STATUS_COLORS.red.border)}>
        <p className="text-xs text-zinc-400 mb-1">Critical</p>
        <p className={cn("text-xl font-bold", STATUS_COLORS.red.text)}>{summary.red}</p>
      </div>
      <div className="bg-zinc-900 rounded-lg border border-zinc-800 p-3">
        <p className="text-xs text-zinc-500 mb-1">PRODISSUEs</p>
        <p className={cn("text-xl font-bold", data.active_prodissues.length > 0 ? "text-red-400" : "text-zinc-100")}>
          {data.active_prodissues.length}
        </p>
      </div>
    </div>
  );
}

// --- Sort types for both tables ---
type SortDir = "asc" | "desc";
type HealthSortKey = "service" | "green" | "yellow" | "orange" | "red" | "total";
type ProdissueSortKey = "key" | "title" | "status";

function SortArrow({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <ArrowUpDown className="w-3 h-3 text-zinc-600" />;
  return dir === "asc"
    ? <ArrowUp className="w-3 h-3 text-zinc-300" />
    : <ArrowDown className="w-3 h-3 text-zinc-300" />;
}

// --- Team aggregate helper ---
function teamSums(team: TeamGroup) {
  let green = 0, yellow = 0, orange = 0, red = 0, total = 0;
  for (const s of team.services) {
    green += s.green_count;
    yellow += s.yellow_count;
    orange += s.orange_count;
    red += s.red_count;
    total += s.total_alerts;
  }
  return { green, yellow, orange, red, total };
}

function teamSortValue(team: TeamGroup, key: HealthSortKey): number | string {
  const sums = teamSums(team);
  switch (key) {
    case "service": return team.team.toLowerCase();
    case "green": return sums.green;
    case "yellow": return sums.yellow;
    case "orange": return sums.orange;
    case "red": return sums.red;
    case "total": return sums.total;
  }
}

function serviceSortValue(svc: ServiceStatus, key: HealthSortKey): number | string {
  switch (key) {
    case "service": return svc.display_name.toLowerCase();
    case "green": return svc.green_count;
    case "yellow": return svc.yellow_count;
    case "orange": return svc.orange_count;
    case "red": return svc.red_count;
    case "total": return svc.total_alerts;
  }
}

function ServiceHealthTable({
  teams,
  search,
  sortKey,
  sortDir,
  onSelectService,
}: {
  teams: TeamGroup[];
  search: string;
  sortKey: HealthSortKey;
  sortDir: SortDir;
  onSelectService: (serviceName: string) => void;
}) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const toggleTeam = (team: string) =>
    setCollapsed((prev) => ({ ...prev, [team]: !prev[team] }));

  const lowerSearch = search.toLowerCase();

  const filtered = useMemo(() => {
    let result = teams;

    // Filter by search
    if (lowerSearch) {
      result = teams
        .map((team) => {
          const teamMatch = team.team.toLowerCase().includes(lowerSearch);
          if (teamMatch) return team;
          const matchingServices = team.services.filter(
            (s) =>
              s.display_name.toLowerCase().includes(lowerSearch) ||
              s.service_name.toLowerCase().includes(lowerSearch),
          );
          if (matchingServices.length === 0) return null;
          return { ...team, services: matchingServices };
        })
        .filter(Boolean) as TeamGroup[];
    }

    // Sort teams
    const sorted = [...result].sort((a, b) => {
      const va = teamSortValue(a, sortKey);
      const vb = teamSortValue(b, sortKey);
      let cmp: number;
      if (typeof va === "string" && typeof vb === "string") {
        cmp = va.localeCompare(vb);
      } else {
        cmp = (va as number) - (vb as number);
      }
      return sortDir === "asc" ? cmp : -cmp;
    });

    // Sort services within each team
    return sorted.map((team) => {
      const sortedServices = [...team.services].sort((a, b) => {
        const va = serviceSortValue(a, sortKey);
        const vb = serviceSortValue(b, sortKey);
        let cmp: number;
        if (typeof va === "string" && typeof vb === "string") {
          cmp = va.localeCompare(vb);
        } else {
          cmp = (va as number) - (vb as number);
        }
        return sortDir === "asc" ? cmp : -cmp;
      });
      return { ...team, services: sortedServices };
    });
  }, [teams, lowerSearch, sortKey, sortDir]);

  return (
    <table className="w-full table-fixed">
      <colgroup>
        <col className={COL.service} />
        <col className={COL.green} />
        <col className={COL.yellow} />
        <col className={COL.orange} />
        <col className={COL.red} />
        <col className={COL.total} />
        <col className={COL.prodissue} />
      </colgroup>
      <tbody>
        {filtered.map((team) => {
          const colors = STATUS_COLORS[team.status] || STATUS_COLORS.green;
          const isCollapsed = collapsed[team.team] ?? false;
          const sums = teamSums(team);
          return (
            <Fragment key={team.team}>
              {/* Team header row with aggregate sums */}
              <tr
                className={cn("cursor-pointer select-none", colors.bg)}
                onClick={() => toggleTeam(team.team)}
              >
                <td className="py-2 px-3">
                  <div className="flex items-center gap-2">
                    {isCollapsed
                      ? <ChevronRight className="w-3.5 h-3.5 text-zinc-400" />
                      : <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />}
                    <StatusDot status={team.status} />
                    <span className="text-sm font-semibold text-zinc-100">{team.team}</span>
                    <StatusBadge status={team.status} />
                    <span className="text-xs text-zinc-500 ml-auto">{team.services.length} svc</span>
                  </div>
                </td>
                <td className="py-2 px-3 text-center">
                  <CountCell count={sums.green} status="green" />
                </td>
                <td className="py-2 px-3 text-center">
                  <CountCell count={sums.yellow} status="yellow" />
                </td>
                <td className="py-2 px-3 text-center">
                  <CountCell count={sums.orange} status="orange" />
                </td>
                <td className="py-2 px-3 text-center">
                  <CountCell count={sums.red} status="red" />
                </td>
                <td className="py-2 px-3 text-center">
                  <span className="text-xs text-zinc-400 font-medium">{sums.total}</span>
                </td>
                <td className="py-2 px-3" />
              </tr>
              {/* Service rows */}
              {!isCollapsed &&
                team.services.map((svc) => (
                  <tr
                    key={svc.service_name}
                    className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors cursor-pointer"
                    onClick={(e) => { e.stopPropagation(); e.preventDefault(); onSelectService(svc.service_name); }}
                  >
                    <td className="py-1.5 px-3 pl-9">
                      <div className="flex items-center gap-2">
                        <StatusDot status={svc.status} />
                        <span className="text-sm text-zinc-200 truncate hover:text-blue-400 hover:underline transition-colors">{svc.display_name}</span>
                        {(svc as any).assigned_to && (
                          <span className="inline-flex items-center gap-0.5 text-[10px] text-zinc-500 bg-zinc-800 rounded px-1.5 py-0.5 shrink-0">
                            <User className="w-2.5 h-2.5" />
                            {(svc as any).assigned_to}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-1.5 px-3 text-center">
                      <CountCell count={svc.green_count} status="green" />
                    </td>
                    <td className="py-1.5 px-3 text-center">
                      <CountCell count={svc.yellow_count} status="yellow" />
                    </td>
                    <td className="py-1.5 px-3 text-center">
                      <CountCell count={svc.orange_count} status="orange" />
                    </td>
                    <td className="py-1.5 px-3 text-center">
                      <CountCell count={svc.red_count} status="red" />
                    </td>
                    <td className="py-1.5 px-3 text-center">
                      <span className="text-xs text-zinc-500">{svc.total_alerts}</span>
                    </td>
                    <td className="py-1.5 px-3">
                      {svc.prodissue ? (
                        <a
                          href={jiraUrl(svc.prodissue)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300"
                        >
                          <AlertTriangle className="w-3 h-3" />
                          {svc.prodissue}
                          <ExternalLink className="w-2.5 h-2.5" />
                        </a>
                      ) : (
                        <span className="text-zinc-700 text-xs">-</span>
                      )}
                    </td>
                  </tr>
                ))}
            </Fragment>
          );
        })}
        {filtered.length === 0 && (
          <tr>
            <td colSpan={7} className="py-8 text-center text-sm text-zinc-500">
              No teams or services match &ldquo;{search}&rdquo;
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

// --- Lazy-loaded Slack Thread Detail ---

function SlackThreadDetail({ urls }: { urls: string[] }) {
  const [analyses, setAnalyses] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  useEffect(() => {
    for (const url of urls) {
      if (analyses[url] || loading[url]) continue;
      setLoading(prev => ({ ...prev, [url]: true }));
      fetch(`http://localhost:9000/api/service-health/slack-thread-analysis?url=${encodeURIComponent(url)}`)
        .then(r => r.json())
        .then(data => setAnalyses(prev => ({ ...prev, [url]: data })))
        .catch(() => setAnalyses(prev => ({ ...prev, [url]: { error: "Failed to load" } })))
        .finally(() => setLoading(prev => ({ ...prev, [url]: false })));
    }
  }, [urls]);

  return (
    <>
      {urls.map((url, i) => {
        const a = analyses[url];
        const isLoading = loading[url];

        if (isLoading) {
          return <div key={i} className="mt-2 p-2 rounded bg-zinc-800/30 text-[10px] text-zinc-500 animate-pulse">Loading Slack thread analysis...</div>;
        }
        if (!a || a.error) {
          return null;
        }

        return (
          <div key={i} className="mt-2 p-2.5 rounded bg-zinc-800/40 border border-zinc-700/30 text-[11px] space-y-1.5">
            {/* Participants */}
            {a.participants?.length > 0 && (
              <div className="text-zinc-300">
                <span className="text-zinc-500 font-medium">Involved ({a.participant_count}):</span>{" "}
                {a.participants.slice(0, 8).join(", ")}
                {a.participants.length > 8 && <span className="text-zinc-600"> +{a.participants.length - 8}</span>}
              </div>
            )}

            {/* Signals */}
            <div className="flex flex-wrap gap-2">
              {a.has_working_plan ? <span className="text-emerald-400">✅ Has plan</span> : <span className="text-zinc-600">❌ No plan</span>}
              {a.has_impact_assessment ? <span className="text-amber-400">📊 Impact assessed</span> : <span className="text-zinc-600">❌ No impact</span>}
              {a.has_resolution_eta ? <span className="text-blue-400">⏱ Has ETA</span> : <span className="text-zinc-600">❌ No ETA</span>}
            </div>

            {/* Plan snippets */}
            {a.plan_snippets?.length > 0 && (
              <div className="text-zinc-400 bg-emerald-500/5 rounded p-1.5 border-l-2 border-emerald-500/30">
                <span className="text-zinc-500 text-[10px]">Plan:</span> {a.plan_snippets[0]}
              </div>
            )}
            {a.impact_snippets?.length > 0 && (
              <div className="text-zinc-400 bg-amber-500/5 rounded p-1.5 border-l-2 border-amber-500/30">
                <span className="text-zinc-500 text-[10px]">Impact:</span> {a.impact_snippets[0]}
              </div>
            )}
            {a.eta_snippets?.length > 0 && (
              <div className="text-zinc-400 bg-blue-500/5 rounded p-1.5 border-l-2 border-blue-500/30">
                <span className="text-zinc-500 text-[10px]">ETA:</span> {a.eta_snippets[0]}
              </div>
            )}

            {/* Additional JIRA keys found in thread */}
            {a.jira_keys?.length > 0 && (
              <div className="flex flex-wrap gap-1">
                <span className="text-zinc-500 text-[10px]">In thread:</span>
                {a.jira_keys.map((k: string) => (
                  <a key={k} href={jiraUrl(k)} target="_blank" rel="noopener noreferrer"
                    className="text-blue-400 hover:text-blue-300 text-[10px]">{k}</a>
                ))}
              </div>
            )}

            {/* Message count */}
            <div className="text-[10px] text-zinc-600">
              {a.message_count} messages in #{a.channel}
            </div>
          </div>
        );
      })}
    </>
  );
}

// --- Service Detail Modal ---

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h < 24) return m > 0 ? `${h}h ${m}m` : `${h}h`;
  const d = Math.floor(h / 24);
  const rh = h % 24;
  return rh > 0 ? `${d}d ${rh}h` : `${d}d`;
}

function IncidentStatusBadge({ status, urgency }: { status: string; urgency: string }) {
  if (status === "triggered" && urgency === "high") {
    return <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-red-500/20 text-red-400">TRIGGERED</span>;
  }
  if (status === "triggered") {
    return <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-yellow-500/20 text-yellow-400">TRIGGERED</span>;
  }
  if (status === "acknowledged") {
    return <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-orange-500/20 text-orange-400">ACKED</span>;
  }
  return <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-zinc-500/20 text-zinc-400">RESOLVED</span>;
}

function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return null;
  const colors: Record<string, string> = {
    P1: "bg-red-500/20 text-red-400",
    P2: "bg-orange-500/20 text-orange-400",
    P3: "bg-yellow-500/20 text-yellow-400",
    P4: "bg-zinc-500/20 text-zinc-400",
    P5: "bg-zinc-500/20 text-zinc-500",
  };
  const label = priority.substring(0, 2).toUpperCase();
  return (
    <span className={cn("px-1.5 py-0.5 rounded text-[10px] font-semibold", colors[label] || colors.P4)}>
      {label}
    </span>
  );
}

function ServiceDetailModal({
  serviceName,
  hours,
  onClose,
}: {
  serviceName: string;
  hours: number;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<ServiceDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.serviceDetail(serviceName, hours)
      .then(setDetail)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [serviceName, hours]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const colors = detail ? (STATUS_COLORS[detail.status as keyof typeof STATUS_COLORS] || STATUS_COLORS.green) : STATUS_COLORS.green;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <div className="flex items-center gap-3 min-w-0">
            {detail && <StatusDot status={detail.status} />}
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-zinc-100 truncate">
                {detail?.display_name || serviceName}
              </h2>
              {detail && (
                <p className="text-xs text-zinc-500">{detail.team}</p>
              )}
            </div>
            {detail && <StatusBadge status={detail.status} />}
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {loading && (
            <div className="p-8 text-center text-sm text-zinc-500">Loading incidents...</div>
          )}
          {error && (
            <div className="p-4 text-sm text-red-400">Failed to load: {error}</div>
          )}
          {detail && !loading && (
            <>
              {/* Summary stats */}
              <div className="px-4 py-3 border-b border-zinc-800">
                <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                  <div className="text-center">
                    <p className="text-lg font-bold text-zinc-100">{detail.summary.active}</p>
                    <p className="text-[10px] text-zinc-500">Active</p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-bold text-zinc-400">{detail.summary.resolved}</p>
                    <p className="text-[10px] text-zinc-500">Resolved</p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-bold text-red-400">{detail.summary.high_urgency}</p>
                    <p className="text-[10px] text-zinc-500">High</p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-bold text-yellow-400">{detail.summary.low_urgency}</p>
                    <p className="text-[10px] text-zinc-500">Low</p>
                  </div>
                  {(detail.summary.p1 > 0 || detail.summary.p2 > 0 || detail.summary.p3 > 0) && (
                    <>
                      <div className="text-center col-span-2 flex items-center justify-center gap-3">
                        {detail.summary.p1 > 0 && (
                          <span className="text-xs"><span className="font-bold text-red-400">{detail.summary.p1}</span> <span className="text-zinc-500">P1</span></span>
                        )}
                        {detail.summary.p2 > 0 && (
                          <span className="text-xs"><span className="font-bold text-orange-400">{detail.summary.p2}</span> <span className="text-zinc-500">P2</span></span>
                        )}
                        {detail.summary.p3 > 0 && (
                          <span className="text-xs"><span className="font-bold text-yellow-400">{detail.summary.p3}</span> <span className="text-zinc-500">P3</span></span>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* Incident list */}
              <div className="divide-y divide-zinc-800/50">
                {detail.incidents.length === 0 ? (
                  <div className="p-8 text-center text-sm text-zinc-500">
                    No incidents in the last {hours}h
                  </div>
                ) : (
                  detail.incidents.map((inc) => (
                    <div
                      key={inc.incident_id}
                      className={cn(
                        "px-4 py-2.5 hover:bg-zinc-800/30 transition-colors",
                        inc.status === "triggered" && inc.urgency === "high" && "bg-red-500/5",
                      )}
                    >
                      <div className="flex items-start gap-2">
                        {/* Status + Priority badges */}
                        <div className="flex items-center gap-1.5 pt-0.5 shrink-0">
                          <IncidentStatusBadge status={inc.status} urgency={inc.urgency} />
                          <PriorityBadge priority={inc.priority} />
                        </div>
                        {/* Title + metadata */}
                        <div className="min-w-0 flex-1">
                          <p className="text-sm text-zinc-200 leading-snug break-words">{inc.title}</p>
                          <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-1">
                            {/* Duration */}
                            <span className="inline-flex items-center gap-1 text-[11px] text-zinc-500">
                              <Clock className="w-3 h-3" />
                              {formatDuration(inc.duration_seconds)}
                              {inc.status === "resolved" ? " total" : " ongoing"}
                            </span>
                            {/* Acked by */}
                            {inc.acknowledged_by && (
                              <span className="inline-flex items-center gap-1 text-[11px] text-emerald-500/70">
                                <User className="w-3 h-3" />
                                Acked: {inc.acknowledged_by}
                              </span>
                            )}
                            {/* Assigned to */}
                            {inc.assigned_to && (
                              <span className="inline-flex items-center gap-1 text-[11px] text-zinc-500">
                                <User className="w-3 h-3" />
                                {inc.assigned_to}
                              </span>
                            )}
                            {/* Triggered time */}
                            <span className="text-[11px] text-zinc-600">
                              {new Date(inc.triggered_at).toLocaleString(undefined, {
                                month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                              })}
                            </span>
                          </div>
                          {/* PRODISSUE + JIRA links */}
                          {((inc as any).prodissue_key || (inc as any).jira_keys?.length || (inc as any).slack_refs?.length || (inc as any).gitlab_refs?.length || (inc as any).grafana_refs?.length) && (
                            <div className="flex flex-wrap items-center gap-2 mt-1.5">
                              {(inc as any).prodissue_key && (
                                <a
                                  href={jiraUrl((inc as any).prodissue_key)}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 text-[11px] text-red-400 hover:text-red-300 bg-red-500/10 rounded px-1.5 py-0.5"
                                >
                                  <Siren className="w-3 h-3" />
                                  {(inc as any).prodissue_key}
                                  <ExternalLink className="w-2.5 h-2.5" />
                                </a>
                              )}
                              {((inc as any).jira_keys || []).map((key: string) => (
                                <a
                                  key={key}
                                  href={jiraUrl(key)}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 bg-blue-500/10 rounded px-1.5 py-0.5"
                                >
                                  {key}
                                  <ExternalLink className="w-2.5 h-2.5" />
                                </a>
                              ))}
                              {((inc as any).slack_contexts || (inc as any).slack_refs?.map((u: string) => ({ url: u })) || []).map((ctx: any, i: number) => (
                                <a
                                  key={`slack-${i}`}
                                  href={ctx.url || (inc as any).slack_refs?.[i] || "#"}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 text-[11px] text-purple-400 hover:text-purple-300 bg-purple-500/10 rounded px-1.5 py-0.5"
                                  title={ctx.summary || ctx.title || ""}
                                >
                                  💬 {ctx.channel ? `#${ctx.channel}` : "Slack thread"}
                                  {ctx.participant_count > 0 && ` (${ctx.participant_count}👤)`}
                                  <ExternalLink className="w-2.5 h-2.5" />
                                </a>
                              ))}
                              {((inc as any).gitlab_refs || []).map((url: string, i: number) => (
                                <a
                                  key={`gl-${i}`}
                                  href={url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 text-[11px] text-orange-400 hover:text-orange-300 bg-orange-500/10 rounded px-1.5 py-0.5"
                                >
                                  🦊 GitLab
                                  <ExternalLink className="w-2.5 h-2.5" />
                                </a>
                              ))}
                              {((inc as any).grafana_refs || []).map((url: string, i: number) => (
                                <a
                                  key={`graf-${i}`}
                                  href={url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 text-[11px] text-amber-400 hover:text-amber-300 bg-amber-500/10 rounded px-1.5 py-0.5"
                                >
                                  📊 Grafana
                                  <ExternalLink className="w-2.5 h-2.5" />
                                </a>
                              ))}
                            </div>
                          )}
                          {/* Lazy-loaded Slack thread analysis */}
                          {((inc as any).slack_refs?.length > 0) && (
                            <SlackThreadDetail urls={(inc as any).slack_refs} />
                          )}
                        </div>
                        {/* PD link */}
                        {inc.pd_url && (
                          <a
                            href={inc.pd_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="shrink-0 p-1 rounded hover:bg-zinc-700 text-zinc-500 hover:text-zinc-300"
                            title="Open in PagerDuty"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// --- PRODISSUE table ---

function ProdissueSortIcon({ column, sortKey, sortDir }: { column: ProdissueSortKey; sortKey: ProdissueSortKey; sortDir: SortDir }) {
  return <SortArrow active={column === sortKey} dir={sortDir} />;
}

function ProdissueList({ prodissues }: { prodissues: Array<{ key: string; title: string; status: string }> }) {
  const [open, setOpen] = useState(false);
  const [sortKey, setSortKey] = useState<ProdissueSortKey>("key");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const toggleSort = (col: ProdissueSortKey) => {
    if (sortKey === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(col);
      setSortDir("asc");
    }
  };

  const sorted = useMemo(() => {
    const copy = [...prodissues];
    copy.sort((a, b) => {
      let cmp: number;
      if (sortKey === "key") {
        const numA = parseInt(a.key.replace(/\D+/g, ""), 10) || 0;
        const numB = parseInt(b.key.replace(/\D+/g, ""), 10) || 0;
        cmp = numA - numB;
      } else {
        cmp = (a[sortKey] || "").localeCompare(b[sortKey] || "");
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [prodissues, sortKey, sortDir]);

  if (prodissues.length === 0) return null;

  return (
    <div className="mb-6 bg-zinc-900 rounded-lg border border-zinc-800 overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-zinc-800/50 transition-colors"
      >
        {open ? <ChevronDown className="w-4 h-4 text-zinc-400" /> : <ChevronRight className="w-4 h-4 text-zinc-400" />}
        <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
        <span className="text-sm font-semibold text-red-400">
          Active PRODISSUEs ({prodissues.length})
        </span>
      </button>

      {open && (
        <div className="max-h-64 overflow-y-auto border-t border-zinc-800">
          <table className="w-full">
            <thead className="sticky top-0 bg-zinc-900 z-10">
              <tr className="border-b border-zinc-700">
                <th
                  className="text-left py-1.5 px-3 text-xs font-medium text-zinc-400 cursor-pointer select-none hover:text-zinc-200"
                  onClick={() => toggleSort("key")}
                >
                  <span className="inline-flex items-center gap-1">
                    Key <ProdissueSortIcon column="key" sortKey={sortKey} sortDir={sortDir} />
                  </span>
                </th>
                <th
                  className="text-left py-1.5 px-3 text-xs font-medium text-zinc-400 cursor-pointer select-none hover:text-zinc-200"
                  onClick={() => toggleSort("title")}
                >
                  <span className="inline-flex items-center gap-1">
                    Title <ProdissueSortIcon column="title" sortKey={sortKey} sortDir={sortDir} />
                  </span>
                </th>
                <th
                  className="text-left py-1.5 px-3 text-xs font-medium text-zinc-400 cursor-pointer select-none hover:text-zinc-200 w-28"
                  onClick={() => toggleSort("status")}
                >
                  <span className="inline-flex items-center gap-1">
                    Status <ProdissueSortIcon column="status" sortKey={sortKey} sortDir={sortDir} />
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((p) => (
                <tr key={p.key} className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors">
                  <td className="py-1.5 px-3 whitespace-nowrap">
                    <a
                      href={jiraUrl(p.key)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs font-mono text-red-400 hover:text-red-300 inline-flex items-center gap-1"
                    >
                      {p.key}
                      <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  </td>
                  <td className="py-1.5 px-3">
                    <span className="text-xs text-zinc-300 line-clamp-1">{p.title}</span>
                  </td>
                  <td className="py-1.5 px-3">
                    <span className="text-xs text-zinc-500">{p.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// --- Sortable column header ---

function SortableHeader({
  label,
  column,
  sortKey,
  sortDir,
  onSort,
  align = "center",
  colorClass = "text-zinc-400",
}: {
  label: string;
  column: HealthSortKey;
  sortKey: HealthSortKey;
  sortDir: SortDir;
  onSort: (col: HealthSortKey) => void;
  align?: "left" | "center";
  colorClass?: string;
}) {
  return (
    <th
      className={cn(
        "py-2 px-3 text-xs font-medium cursor-pointer select-none hover:text-zinc-200 transition-colors",
        align === "center" ? "text-center" : "text-left",
        colorClass,
      )}
      onClick={() => onSort(column)}
    >
      <span className={cn("inline-flex items-center gap-1", align === "center" && "justify-center")}>
        {label}
        <SortArrow active={sortKey === column} dir={sortDir} />
      </span>
    </th>
  );
}

// --- Main page ---

export default function HealthPage() {
  const [hours, setHours] = useState(24);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<HealthSortKey>("service");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [selectedService, setSelectedService] = useState<string | null>(null);

  const toggleSort = (col: HealthSortKey) => {
    if (sortKey === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(col);
      // Default to desc for numeric columns (show highest first), asc for name
      setSortDir(col === "service" ? "asc" : "desc");
    }
  };

  const fetcher = useCallback(() => api.serviceHealth(hours), [hours]);
  const { data, loading, error, refresh } = usePoll(fetcher, 120_000);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Service Health</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Alert status by service, grouped by team. Based on PagerDuty incidents.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
            className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-300"
          >
            <option value={1}>Last 1h</option>
            <option value={4}>Last 4h</option>
            <option value={12}>Last 12h</option>
            <option value={24}>Last 24h</option>
            <option value={72}>Last 3d</option>
            <option value={168}>Last 7d</option>
          </select>
          {data && <StatusBadge status={data.overall_status} />}
          <button
            onClick={() => refresh()}
            className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 mb-6">
          <p className="text-sm text-red-400">Failed to load service health: {error.message}</p>
        </div>
      )}

      {loading && !data && (
        <div className="text-zinc-500 text-sm p-8 text-center">Loading service health data...</div>
      )}

      {data && (
        <>
          <SummaryCards data={data} />
          <ProdissueList prodissues={data.active_prodissues} />

          <div className="bg-zinc-900 rounded-lg border border-zinc-800 overflow-hidden">
            {/* Sticky header: search + sortable column headers */}
            <div className="sticky top-0 z-20 bg-zinc-900 border-b border-zinc-700">
              <div className="px-3 py-2 border-b border-zinc-800">
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-500" />
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Filter teams or services..."
                    className="w-full bg-zinc-800 border border-zinc-700 rounded pl-8 pr-3 py-1 text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-zinc-600"
                  />
                </div>
              </div>
              <table className="w-full table-fixed">
                <colgroup>
                  <col className={COL.service} />
                  <col className={COL.green} />
                  <col className={COL.yellow} />
                  <col className={COL.orange} />
                  <col className={COL.red} />
                  <col className={COL.total} />
                  <col className={COL.prodissue} />
                </colgroup>
                <thead>
                  <tr>
                    <SortableHeader label="Service" column="service" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="left" />
                    <SortableHeader label="Green" column="green" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} colorClass="text-emerald-400" />
                    <SortableHeader label="Yellow" column="yellow" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} colorClass="text-yellow-400" />
                    <SortableHeader label="Orange" column="orange" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} colorClass="text-orange-400" />
                    <SortableHeader label="Red" column="red" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} colorClass="text-red-400" />
                    <SortableHeader label="Total" column="total" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} colorClass="text-zinc-500" />
                    <th className="text-left py-2 px-3 text-xs font-medium text-zinc-500">PRODISSUE</th>
                  </tr>
                </thead>
              </table>
            </div>

            {/* Scrollable body */}
            <div className="max-h-[calc(100vh-420px)] overflow-y-auto">
              <ServiceHealthTable teams={data.teams} search={search} sortKey={sortKey} sortDir={sortDir} onSelectService={setSelectedService} />
            </div>
          </div>

          <div className="mt-3 text-xs text-zinc-600">
            Last updated: {new Date(data.timestamp).toLocaleString()} | Lookback: {hours}h |{" "}
            {data.summary.grafana_alert_definitions} Grafana alert definitions
          </div>
        </>
      )}

      {selectedService && (
        <ServiceDetailModal
          serviceName={selectedService}
          hours={hours}
          onClose={() => setSelectedService(null)}
        />
      )}
    </div>
  );
}
