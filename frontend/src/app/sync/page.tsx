"use client";

import { useCallback, useState } from "react";
import { RefreshCw, Database, FileText, Play, Loader2, CheckCircle, AlertTriangle, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { usePoll } from "@/lib/polling";

interface SyncSource {
  source_name: string;
  last_sync: string | null;
  last_sync_relative: string | null;
  record_count: number | null;
  status: string;
  staleness_seconds: number | null;
  sync_metadata: Record<string, unknown> | null;
  is_syncing: boolean;
}

interface SyncStatusResponse {
  sources: SyncSource[];
  timestamp: string;
}

interface SyncLogsResponse {
  source: string;
  logs: string[];
  log_file: string | null;
}

// Display configuration for sync sources
const SOURCE_DISPLAY: Record<string, { label: string; description: string; syncKey: string }> = {
  pagerduty_incidents: { label: "PagerDuty", description: "Incident data from PagerDuty", syncKey: "pagerduty" },
  slack_p1p2: { label: "Slack (fast)", description: "P1-P2 priority channels", syncKey: "slack_fast" },
  slack_channels: { label: "Slack (full)", description: "All Slack channels", syncKey: "slack_full" },
  jira_issues: { label: "JIRA (issues)", description: "Ticket data across projects", syncKey: "jira_issues" },
  jira_changes: { label: "JIRA (changes)", description: "JIRA changelog events", syncKey: "jira_changes" },
  jira_projects: { label: "JIRA (projects)", description: "JIRA project catalog", syncKey: "jira_projects" },
  grafana_alerts: { label: "Grafana Alerts", description: "Alert rule definitions", syncKey: "grafana_alerts" },
  google_drive: { label: "Google Drive", description: "Document catalog & metadata", syncKey: "google_drive" },
  wiki_pages: { label: "Wiki", description: "Confluence wiki pages", syncKey: "wiki" },
};

// Order for display
const SOURCE_ORDER = [
  "pagerduty_incidents",
  "slack_p1p2",
  "slack_channels",
  "jira_issues",
  "jira_changes",
  "jira_projects",
  "grafana_alerts",
  "google_drive",
  "wiki_pages",
];

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "green":
      return <CheckCircle className="w-4 h-4 text-emerald-400" />;
    case "yellow":
      return <AlertTriangle className="w-4 h-4 text-amber-400" />;
    case "red":
      return <XCircle className="w-4 h-4 text-red-400" />;
    default:
      return <Database className="w-4 h-4 text-zinc-500" />;
  }
}

function StatusBadge({ status }: { status: string }) {
  const variants: Record<string, string> = {
    green: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    yellow: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    red: "bg-red-500/20 text-red-400 border-red-500/30",
    unknown: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
  };
  const labels: Record<string, string> = {
    green: "Fresh",
    yellow: "Stale",
    red: "Outdated",
    unknown: "Unknown",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${variants[status] || variants.unknown}`}>
      {labels[status] || labels.unknown}
    </span>
  );
}

export default function SyncPage() {
  const [triggeringSource, setTriggeringSource] = useState<string | null>(null);
  const [triggerMessage, setTriggerMessage] = useState<string | null>(null);
  const [logModalSource, setLogModalSource] = useState<string | null>(null);
  const [logData, setLogData] = useState<SyncLogsResponse | null>(null);
  const [logLoading, setLogLoading] = useState(false);

  const fetcher = useCallback(async () => {
    const res = await fetch("/api/sync/status");
    if (!res.ok) return null;
    return (await res.json()) as SyncStatusResponse;
  }, []);

  const { data, loading, refresh } = usePoll(fetcher, 30_000);

  // Build a map for quick lookup
  const sourceMap = new Map<string, SyncSource>();
  if (data?.sources) {
    for (const s of data.sources) {
      sourceMap.set(s.source_name, s);
    }
  }

  const handleSync = async (syncKey: string, sourceName: string) => {
    setTriggeringSource(sourceName);
    setTriggerMessage(null);
    try {
      const res = await fetch(`/api/sync/trigger/${syncKey}`, { method: "POST" });
      const result = await res.json();
      setTriggerMessage(result.message);
      // Refresh status after a short delay
      setTimeout(() => refresh(), 2000);
    } catch (e) {
      setTriggerMessage(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setTimeout(() => {
        setTriggeringSource(null);
        setTriggerMessage(null);
      }, 5000);
    }
  };

  const handleShowLogs = async (syncKey: string) => {
    setLogModalSource(syncKey);
    setLogLoading(true);
    setLogData(null);
    try {
      const res = await fetch(`/api/sync/logs/${syncKey}?lines=200`);
      const result = await res.json();
      setLogData(result);
    } catch {
      setLogData({ source: syncKey, logs: ["Failed to load logs."], log_file: null });
    } finally {
      setLogLoading(false);
    }
  };

  // Count statuses for summary
  const statusCounts = { green: 0, yellow: 0, red: 0, unknown: 0 };
  for (const name of SOURCE_ORDER) {
    const src = sourceMap.get(name);
    const status = src?.status || "unknown";
    statusCounts[status as keyof typeof statusCounts] =
      (statusCounts[status as keyof typeof statusCounts] || 0) + 1;
  }

  const handleFullSync = async () => {
    setTriggeringSource("full_sync");
    setTriggerMessage(null);
    try {
      const res = await fetch("/api/sync/trigger/full_sync", { method: "POST" });
      const result = await res.json();
      setTriggerMessage(result.message);
      setTimeout(() => refresh(), 5000);
    } catch (e) {
      setTriggerMessage(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setTimeout(() => {
        setTriggeringSource(null);
        setTriggerMessage(null);
      }, 8000);
    }
  };

  const stickyHeader = (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          {statusCounts.green > 0 && (
            <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30 text-xs">
              {statusCounts.green} fresh
            </Badge>
          )}
          {statusCounts.yellow > 0 && (
            <Badge variant="outline" className="bg-amber-500/10 text-amber-400 border-amber-500/30 text-xs">
              {statusCounts.yellow} stale
            </Badge>
          )}
          {statusCounts.red > 0 && (
            <Badge variant="outline" className="bg-red-500/10 text-red-400 border-red-500/30 text-xs">
              {statusCounts.red} outdated
            </Badge>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={handleFullSync}
          disabled={triggeringSource === "full_sync"}
          className="text-xs h-7"
        >
          {triggeringSource === "full_sync" ? (
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
          ) : (
            <RefreshCw className="w-3 h-3 mr-1" />
          )}
          Full Sync
        </Button>
      </div>
    </div>
  );

  return (
    <div className="space-y-4 h-full flex flex-col">
      {/* Header */}
      <div className="px-2 flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Sync</h1>
          <p className="text-sm text-zinc-500">
            Data source sync status and controls
          </p>
        </div>
        {data && (
          <span className="text-xs text-zinc-600">
            Updated {new Date(data.timestamp).toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Trigger feedback */}
      {triggerMessage && (
        <div className="mx-2 px-3 py-2 rounded bg-blue-500/10 border border-blue-500/30 text-blue-400 text-xs">
          {triggerMessage}
        </div>
      )}

      {/* Sync Status Table */}
      <div className="flex-1 min-h-0 px-2">
        <ScrollableCard
          title="Data Sources"
          icon={<Database className="w-4 h-4" />}
          stickyHeader={stickyHeader}
        >
          {loading && !data ? (
            <div className="flex items-center justify-center py-12 text-zinc-500 text-sm">
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Loading sync status...
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 text-zinc-500 text-xs">
                    <th className="text-left py-2 px-3 font-medium">Source</th>
                    <th className="text-left py-2 px-3 font-medium">Status</th>
                    <th className="text-left py-2 px-3 font-medium">Last Sync</th>
                    <th className="text-right py-2 px-3 font-medium">Records</th>
                    <th className="text-right py-2 px-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {SOURCE_ORDER.map((name) => {
                    const src = sourceMap.get(name);
                    const display = SOURCE_DISPLAY[name] || {
                      label: name,
                      description: "",
                      syncKey: name,
                    };
                    const isSyncing = src?.is_syncing || triggeringSource === display.syncKey;

                    return (
                      <tr
                        key={name}
                        className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors"
                      >
                        {/* Source Name */}
                        <td className="py-3 px-3">
                          <div className="flex items-center gap-2">
                            <StatusIcon status={src?.status || "unknown"} />
                            <div>
                              <div className="font-medium text-zinc-200">
                                {display.label}
                              </div>
                              <div className="text-xs text-zinc-500">
                                {display.description}
                              </div>
                            </div>
                          </div>
                        </td>

                        {/* Status Badge */}
                        <td className="py-3 px-3">
                          <StatusBadge status={src?.status || "unknown"} />
                        </td>

                        {/* Last Sync */}
                        <td className="py-3 px-3">
                          {src?.last_sync ? (
                            <div>
                              <div className="text-zinc-300">
                                {src.last_sync_relative}
                              </div>
                              <div className="text-xs text-zinc-600">
                                {new Date(src.last_sync).toLocaleString()}
                              </div>
                            </div>
                          ) : (
                            <span className="text-zinc-600">Never</span>
                          )}
                        </td>

                        {/* Records */}
                        <td className="py-3 px-3 text-right">
                          {src?.record_count != null ? (
                            <span className="text-zinc-300 font-mono text-xs">
                              {src.record_count.toLocaleString()}
                            </span>
                          ) : (
                            <span className="text-zinc-600">-</span>
                          )}
                        </td>

                        {/* Actions */}
                        <td className="py-3 px-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleSync(display.syncKey, name)}
                              disabled={isSyncing}
                              className="h-7 px-2 text-xs"
                              title={`Sync ${display.label}`}
                            >
                              {isSyncing ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <Play className="w-3 h-3" />
                              )}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleShowLogs(display.syncKey)}
                              className="h-7 px-2 text-xs"
                              title={`Show logs for ${display.label}`}
                            >
                              <FileText className="w-3 h-3" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </ScrollableCard>
      </div>

      {/* Sync Log Modal */}
      <Dialog open={logModalSource !== null} onOpenChange={() => setLogModalSource(null)}>
        <DialogContent className="max-w-3xl max-h-[80vh] bg-zinc-900 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-200">
              Sync Logs: {logModalSource}
              {logData?.log_file && (
                <span className="text-xs font-normal text-zinc-500 ml-2">
                  ({logData.log_file})
                </span>
              )}
            </DialogTitle>
          </DialogHeader>
          <div className="overflow-auto max-h-[60vh] bg-zinc-950 rounded border border-zinc-800 p-3">
            {logLoading ? (
              <div className="flex items-center justify-center py-8 text-zinc-500 text-sm">
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Loading logs...
              </div>
            ) : logData ? (
              <pre className="text-xs text-zinc-400 font-mono whitespace-pre-wrap leading-relaxed">
                {logData.logs.join("\n")}
              </pre>
            ) : (
              <p className="text-sm text-zinc-500">No logs available.</p>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
