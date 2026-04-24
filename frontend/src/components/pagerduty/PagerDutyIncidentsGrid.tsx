import { useState, useCallback } from "react";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { PagerDutyIncidentCard } from "./PagerDutyIncidentCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AlertCircle, RefreshCw, Download } from "lucide-react";

export function PagerDutyIncidentsGrid() {
  const [statusFilter, setStatusFilter] = useState("triggered");
  const [urgencyFilter, setUrgencyFilter] = useState("");
  const [daysFilter, setDaysFilter] = useState(7);

  const fetcher = useCallback(() => {
    return api.pagerdutyComputeTeamIncidents(
      statusFilter || undefined,
      daysFilter,
      100
    );
  }, [statusFilter, daysFilter]);

  const { data, loading, error, refresh } = usePoll(fetcher, 300_000); // 5 min

  const filteredIncidents = data?.incidents.filter(i =>
    !urgencyFilter || i.urgency === urgencyFilter
  ) || [];

  const stickyHeader = (
    <div className="space-y-3">
      {/* Stats */}
      <div className="flex justify-between items-center text-xs">
        <span className="text-zinc-500">
          {filteredIncidents.length} incident{filteredIncidents.length !== 1 ? "s" : ""}
        </span>
        <div className="flex items-center gap-2">
          {data && data.incidents.filter(i => i.is_active).length > 0 && (
            <Badge variant="outline" className="text-xs text-red-400 border-red-500/30 animate-pulse">
              {data.incidents.filter(i => i.is_active).length} active
            </Badge>
          )}
          {data && data.incidents.filter(i => i.is_high_urgency).length > 0 && (
            <Badge variant="outline" className="text-xs text-red-400 border-red-500/30">
              {data.incidents.filter(i => i.is_high_urgency).length} high urgency
            </Badge>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-3 gap-2">
        <div>
          <label className="text-xs text-zinc-500 mb-1 block">Status</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-200"
          >
            <option value="">All</option>
            <option value="triggered">Triggered</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>

        <div>
          <label className="text-xs text-zinc-500 mb-1 block">Urgency</label>
          <select
            value={urgencyFilter}
            onChange={(e) => setUrgencyFilter(e.target.value)}
            className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-200"
          >
            <option value="">All</option>
            <option value="high">High</option>
            <option value="low">Low</option>
          </select>
        </div>

        <div>
          <label className="text-xs text-zinc-500 mb-1 block">Time Range</label>
          <select
            value={daysFilter}
            onChange={(e) => setDaysFilter(Number(e.target.value))}
            className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-200"
          >
            <option value="1">Last 24 hours</option>
            <option value="7">Last 7 days</option>
            <option value="30">Last 30 days</option>
            <option value="90">Last 90 days</option>
          </select>
        </div>
      </div>

      {/* Active filters indicator */}
      {(statusFilter || urgencyFilter) && (
        <div className="flex items-center gap-2 pt-1">
          <span className="text-xs text-zinc-600">Filters:</span>
          {statusFilter && (
            <Badge variant="outline" className="text-xs" onClick={() => setStatusFilter("")}>
              Status: {statusFilter} ×
            </Badge>
          )}
          {urgencyFilter && (
            <Badge variant="outline" className="text-xs" onClick={() => setUrgencyFilter("")}>
              Urgency: {urgencyFilter} ×
            </Badge>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setStatusFilter("");
              setUrgencyFilter("");
            }}
            className="h-5 text-xs"
          >
            Clear
          </Button>
        </div>
      )}
    </div>
  );

  const menuItems = [
    {
      label: "Refresh",
      onClick: refresh,
      icon: <RefreshCw className="w-3 h-3" />,
    },
    {
      label: "Scan Recent",
      onClick: async () => {
        await api.pagerdutyScanRecent(1);
        refresh();
      },
      icon: <Download className="w-3 h-3" />,
    },
  ];

  return (
    <ScrollableCard
      title="PagerDuty Incidents (Compute Team)"
      icon={<AlertCircle className="w-5 h-5" />}
      menuItems={menuItems}
      stickyHeader={stickyHeader}
    >
      {loading && <p className="text-xs text-zinc-500">Loading incidents...</p>}
      {error && <p className="text-xs text-red-400">Error loading incidents</p>}
      {!loading && filteredIncidents.length === 0 && (
        <p className="text-xs text-zinc-500">No incidents found</p>
      )}
      {filteredIncidents.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          {filteredIncidents.map((incident) => (
            <PagerDutyIncidentCard key={incident.id} incident={incident} />
          ))}
        </div>
      )}
    </ScrollableCard>
  );
}
