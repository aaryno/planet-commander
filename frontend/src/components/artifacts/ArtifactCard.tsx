import { Badge } from "@/components/ui/badge";
import { ExternalLink, FileText, Calendar, Tag } from "lucide-react";
import type { InvestigationArtifact } from "@/lib/api";

interface ArtifactCardProps {
  artifact: InvestigationArtifact;
}

export function ArtifactCard({ artifact }: ArtifactCardProps) {
  // Format date: "Jan 15, 2026"
  const createdDate = new Date(artifact.created_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  // Type badge color
  const typeColors: Record<string, string> = {
    investigation: "bg-blue-500/20 text-blue-400",
    plan: "bg-purple-500/20 text-purple-400",
    handoff: "bg-amber-500/20 text-amber-400",
    analysis: "bg-emerald-500/20 text-emerald-400",
    complete: "bg-green-500/20 text-green-400",
    summary: "bg-cyan-500/20 text-cyan-400",
  };

  const typeColor = artifact.artifact_type
    ? typeColors[artifact.artifact_type] || "bg-zinc-500/20 text-zinc-400"
    : "bg-zinc-500/20 text-zinc-400";

  return (
    <div className="p-3 rounded border border-zinc-800 hover:border-zinc-700 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <FileText className="w-4 h-4 text-zinc-500 flex-shrink-0" />
          <h4 className="text-sm font-medium text-zinc-200 truncate">
            {artifact.title || artifact.filename}
          </h4>
        </div>
        <a
          href={`file://${artifact.file_path}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-zinc-500 hover:text-zinc-400 flex-shrink-0"
          title="Open file"
        >
          <ExternalLink className="w-4 h-4" />
        </a>
      </div>

      {/* Description */}
      {artifact.description && (
        <p className="text-xs text-zinc-400 mt-1">{artifact.description}</p>
      )}

      {/* Badges */}
      <div className="flex items-center gap-2 mt-2 flex-wrap">
        {artifact.artifact_type && (
          <Badge className={typeColor}>{artifact.artifact_type}</Badge>
        )}
        {artifact.project && (
          <Badge variant="outline" className="text-xs">
            {artifact.project}
          </Badge>
        )}
        <div className="flex items-center gap-1 text-xs text-zinc-500">
          <Calendar className="w-3 h-3" />
          <span>{createdDate}</span>
        </div>
        {artifact.is_recent && (
          <Badge className="bg-blue-600/20 text-blue-400 text-xs">recent</Badge>
        )}
      </div>

      {/* JIRA Keys */}
      {artifact.jira_keys && artifact.jira_keys.length > 0 && (
        <div className="flex items-center gap-1 mt-2 flex-wrap">
          <Tag className="w-3 h-3 text-zinc-500" />
          {artifact.jira_keys.map((key) => (
            <Badge key={key} variant="outline" className="text-xs">
              {key}
            </Badge>
          ))}
        </div>
      )}

      {/* Keywords */}
      {artifact.keywords && artifact.keywords.length > 0 && (
        <div className="flex items-center gap-1 mt-2 flex-wrap">
          {artifact.keywords.slice(0, 5).map((keyword) => (
            <span
              key={keyword}
              className="text-xs text-zinc-500 bg-zinc-800/50 px-1.5 py-0.5 rounded"
            >
              {keyword}
            </span>
          ))}
          {artifact.keywords.length > 5 && (
            <span className="text-xs text-zinc-500">
              +{artifact.keywords.length - 5} more
            </span>
          )}
        </div>
      )}

      {/* Content Preview */}
      {artifact.content_preview && (
        <p className="text-xs text-zinc-500 mt-2 line-clamp-2">
          {artifact.content_preview}
        </p>
      )}

      {/* Systems/Alerts */}
      {((artifact.entities?.systems && artifact.entities.systems.length > 0) ||
        (artifact.entities?.alerts && artifact.entities.alerts.length > 0)) && (
        <div className="mt-2 text-xs text-zinc-500">
          {artifact.entities?.systems && artifact.entities.systems.length > 0 && (
            <span className="mr-3">
              Systems: {artifact.entities.systems.slice(0, 3).join(", ")}
              {artifact.entities.systems.length > 3 && ` +${artifact.entities.systems.length - 3}`}
            </span>
          )}
          {artifact.entities?.alerts && artifact.entities.alerts.length > 0 && (
            <span>
              Alerts: {artifact.entities.alerts.slice(0, 2).join(", ")}
              {artifact.entities.alerts.length > 2 && ` +${artifact.entities.alerts.length - 2}`}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
