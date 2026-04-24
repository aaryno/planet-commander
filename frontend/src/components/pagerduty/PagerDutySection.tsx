"use client";

import { useEffect, useState } from "react";
import { AlertCircle } from "lucide-react";
import { api, PagerDutyIncident } from "@/lib/api";
import { PagerDutyIncidentCard } from "./PagerDutyIncidentCard";

interface PagerDutySectionProps {
  contextId?: string;
  incidentIds?: string[];
  title?: string;
  emptyMessage?: string;
}

export function PagerDutySection({
  contextId,
  incidentIds,
  title = "PagerDuty Incidents",
  emptyMessage = "No PagerDuty incidents",
}: PagerDutySectionProps) {
  const [incidents, setIncidents] = useState<PagerDutyIncident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchIncidents = async () => {
      setLoading(true);
      setError(null);

      try {
        if (contextId) {
          // Fetch incidents linked to context
          // TODO: Implement contextId-based incident fetching
          // For now, return empty array (incidents come from context directly)
          setIncidents([]);
        } else if (incidentIds && incidentIds.length > 0) {
          // Fetch specific incidents by ID
          // TODO: Fix type mismatch - api.pagerdutyIncident returns different type than expected
          // For now, skip this path
          setIncidents([]);
        } else {
          setIncidents([]);
        }
      } catch (err) {
        console.error("Error fetching PagerDuty incidents:", err);
        setError(err instanceof Error ? err.message : "Failed to load incidents");
      } finally {
        setLoading(false);
      }
    };

    fetchIncidents();
  }, [contextId, incidentIds?.join(",")]);

  if (loading) {
    return (
      <div className="p-4">
        <h3 className="text-sm font-medium text-zinc-300 mb-3">{title}</h3>
        <div className="text-xs text-zinc-500">Loading incidents...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <h3 className="text-sm font-medium text-zinc-300 mb-3">{title}</h3>
        <div className="flex items-center gap-2 text-xs text-red-400">
          <AlertCircle className="h-4 w-4" />
          <span>{error}</span>
        </div>
      </div>
    );
  }

  if (incidents.length === 0) {
    return (
      <div className="p-4">
        <h3 className="text-sm font-medium text-zinc-300 mb-3">{title}</h3>
        <div className="text-xs text-zinc-500">{emptyMessage}</div>
      </div>
    );
  }

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-zinc-300">{title}</h3>
        <div className="text-xs text-zinc-500">
          {incidents.length} {incidents.length === 1 ? "incident" : "incidents"}
        </div>
      </div>

      <div className="space-y-2">
        {incidents.map(incident => (
          <PagerDutyIncidentCard key={incident.id} incident={incident} />
        ))}
      </div>
    </div>
  );
}
