import { Badge } from "@/components/ui/badge";
import { AlertCircle, Clock, CheckCircle2, Users, ExternalLink, Zap } from "lucide-react";
import type { PagerDutyIncident } from "@/lib/api";
import { formatMinutesAgo, formatDuration } from "@/lib/time-utils";
import { PD_STATUS_COLORS, PD_URGENCY_COLORS, getStatusColor } from "@/lib/status-colors";

interface PagerDutyIncidentCardProps {
  incident: PagerDutyIncident;
}

export function PagerDutyIncidentCard({ incident }: PagerDutyIncidentCardProps) {
  const ageDisplay = formatMinutesAgo(incident.age_minutes);
  const duration = formatDuration(incident.duration_minutes);
  const timeToAck = formatDuration(incident.time_to_ack_minutes);

  return (
    <div className="p-4 rounded-lg border border-zinc-800 hover:border-zinc-700 transition-colors group">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2 flex-1 min-w-0">
          <AlertCircle className="w-5 h-5 text-zinc-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <a
              href={incident.html_url || "#"}
              target="_blank"
              rel="noopener noreferrer"
              className="text-base font-semibold text-zinc-200 hover:text-zinc-100 line-clamp-2 flex items-center gap-1 group"
            >
              #{incident.incident_number}: {incident.title}
              <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
            </a>
          </div>
        </div>
      </div>

      {/* Status badges */}
      <div className="flex items-center gap-2 mt-3 flex-wrap">
        {/* Status */}
        <Badge
          variant="outline"
          className={`text-xs ${getStatusColor(PD_STATUS_COLORS, incident.status) || "text-zinc-400 border-zinc-600/30"}`}
        >
          {incident.status}
        </Badge>

        {/* Urgency */}
        {incident.urgency && (
          <Badge
            variant="outline"
            className={`text-xs ${getStatusColor(PD_URGENCY_COLORS, incident.urgency) || "text-zinc-400"}`}
          >
            {incident.is_high_urgency && <Zap className="w-3 h-3 mr-1" />}
            {incident.urgency}
          </Badge>
        )}

        {/* Active indicator */}
        {incident.is_active && (
          <Badge variant="outline" className="text-xs text-red-400 border-red-500/30 animate-pulse">
            ACTIVE
          </Badge>
        )}
      </div>

      {/* Service */}
      {incident.service_name && (
        <div className="mt-3 text-xs text-zinc-500">
          <span className="text-zinc-600">Service:</span> {incident.service_name}
        </div>
      )}

      {/* Teams */}
      {incident.team_names.length > 0 && (
        <div className="flex items-center gap-1 mt-2 text-xs text-zinc-500">
          <Users className="w-3 h-3" />
          <span>{incident.team_names.join(", ")}</span>
        </div>
      )}

      {/* Assigned */}
      {incident.assigned_user_names.length > 0 && (
        <div className="flex items-center gap-1 mt-2 text-xs text-zinc-500">
          <span className="text-zinc-600">Assigned:</span>
          <span>{incident.assigned_user_names.join(", ")}</span>
        </div>
      )}

      {/* Timestamps */}
      <div className="flex items-center gap-4 mt-3 text-xs text-zinc-500">
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          <span>{ageDisplay}</span>
        </div>

        {timeToAck && (
          <div className="flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" />
            <span title="Time to acknowledge">Acked in {timeToAck}</span>
          </div>
        )}

        {duration && (
          <div className="flex items-center gap-1">
            <span title="Total duration">Duration: {duration}</span>
          </div>
        )}
      </div>
    </div>
  );
}
