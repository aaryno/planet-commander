import { Badge } from "@/components/ui/badge";
import { BookOpen, GitBranch, Hash, Calendar, AlertTriangle } from "lucide-react";
import type { ProjectDoc } from "@/lib/api";

interface ProjectDocCardProps {
  doc: ProjectDoc;
}

export function ProjectDocCard({ doc }: ProjectDocCardProps) {
  return (
    <div className="p-4 rounded-lg border border-zinc-800 hover:border-zinc-700 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-zinc-500 flex-shrink-0" />
          <h3 className="text-base font-semibold text-zinc-200">
            {doc.project_name}
          </h3>
        </div>
        {doc.is_stale && (
          <Badge variant="outline" className="text-xs text-amber-400 border-amber-500/30">
            <AlertTriangle className="w-3 h-3 mr-1" />
            Stale
          </Badge>
        )}
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 mt-3 text-xs text-zinc-500">
        <div className="flex items-center gap-1">
          <Hash className="w-3 h-3" />
          <span>{doc.word_count.toLocaleString()} words</span>
        </div>
        {doc.keywords.length > 0 && (
          <div className="flex items-center gap-1">
            <span>{doc.keywords.length} keywords</span>
          </div>
        )}
        {doc.file_modified_at && (
          <div className="flex items-center gap-1">
            <Calendar className="w-3 h-3" />
            <span>{doc.last_updated_days_ago}d ago</span>
          </div>
        )}
      </div>

      {/* Team Badge */}
      {doc.team && (
        <div className="mt-3">
          <Badge variant="outline" className="text-xs">
            {doc.team}
          </Badge>
        </div>
      )}

      {/* Repositories */}
      {doc.repositories.length > 0 && (
        <div className="mt-3">
          <div className="text-xs text-zinc-500 mb-1">Repositories</div>
          <div className="flex flex-wrap gap-1">
            {doc.repositories.slice(0, 3).map((repo) => (
              <div
                key={repo}
                className="text-xs bg-zinc-800/50 text-zinc-400 px-2 py-1 rounded flex items-center gap-1"
              >
                <GitBranch className="w-3 h-3" />
                {repo}
              </div>
            ))}
            {doc.repositories.length > 3 && (
              <div className="text-xs text-zinc-500 px-2 py-1">
                +{doc.repositories.length - 3} more
              </div>
            )}
          </div>
        </div>
      )}

      {/* Slack Channels */}
      {doc.slack_channels.length > 0 && (
        <div className="mt-3">
          <div className="text-xs text-zinc-500 mb-1">Slack Channels</div>
          <div className="flex flex-wrap gap-1">
            {doc.slack_channels.map((channel) => (
              <Badge key={channel} variant="outline" className="text-xs">
                {channel}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Keywords */}
      {doc.keywords.length > 0 && (
        <div className="mt-3">
          <div className="text-xs text-zinc-500 mb-1">Keywords</div>
          <div className="flex flex-wrap gap-1">
            {doc.keywords.slice(0, 8).map((keyword) => (
              <span
                key={keyword}
                className="text-xs bg-zinc-800/50 text-zinc-400 px-1.5 py-0.5 rounded"
              >
                {keyword}
              </span>
            ))}
            {doc.keywords.length > 8 && (
              <span className="text-xs text-zinc-500">
                +{doc.keywords.length - 8} more
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
