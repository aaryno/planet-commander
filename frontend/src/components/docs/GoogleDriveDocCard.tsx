import { Badge } from "@/components/ui/badge";
import { FileText, Calendar, AlertTriangle, Folder, User, ExternalLink } from "lucide-react";
import type { GoogleDriveDocument } from "@/lib/api";

interface GoogleDriveDocCardProps {
  doc: GoogleDriveDocument;
}

export function GoogleDriveDocCard({ doc }: GoogleDriveDocCardProps) {
  // Format age display
  const ageDisplay =
    doc.age_days < 30
      ? `${doc.age_days}d ago`
      : doc.age_days < 365
      ? `${Math.floor(doc.age_days / 30)}mo ago`
      : `${Math.floor(doc.age_days / 365)}y ago`;

  // Document kind badge color
  const kindColors: Record<string, string> = {
    postmortem: "text-red-400 border-red-500/30",
    rfd: "text-blue-400 border-blue-500/30",
    rfc: "text-blue-400 border-blue-500/30",
    "meeting-notes": "text-purple-400 border-purple-500/30",
    "on-call-log": "text-amber-400 border-amber-500/30",
  };

  return (
    <div className="p-4 rounded-lg border border-zinc-800 hover:border-zinc-700 transition-colors group">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2 flex-1 min-w-0">
          <FileText className="w-5 h-5 text-zinc-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            {doc.url ? (
              <a
                href={doc.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-base font-semibold text-zinc-200 hover:text-zinc-100 line-clamp-2 flex items-center gap-1 group"
              >
                {doc.title}
                <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
              </a>
            ) : (
              <h3 className="text-base font-semibold text-zinc-200 line-clamp-2">
                {doc.title}
              </h3>
            )}
          </div>
        </div>
        {doc.is_stale && (
          <Badge variant="outline" className="text-xs text-amber-400 border-amber-500/30 flex-shrink-0">
            <AlertTriangle className="w-3 h-3 mr-1" />
            Stale
          </Badge>
        )}
      </div>

      {/* Document Kind & Project */}
      <div className="flex items-center gap-2 mt-3">
        {doc.document_kind && (
          <Badge
            variant="outline"
            className={`text-xs ${kindColors[doc.document_kind] || "text-zinc-400 border-zinc-600/30"}`}
          >
            {doc.document_kind}
          </Badge>
        )}
        {doc.project && (
          <Badge variant="outline" className="text-xs">
            {doc.project}
          </Badge>
        )}
        {doc.doc_type !== "document" && (
          <Badge variant="outline" className="text-xs text-zinc-500">
            {doc.doc_type}
          </Badge>
        )}
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 mt-3 text-xs text-zinc-500">
        {doc.last_modified_at && (
          <div className="flex items-center gap-1">
            <Calendar className="w-3 h-3" />
            <span>{ageDisplay}</span>
          </div>
        )}
        {doc.owner && (
          <div className="flex items-center gap-1">
            <User className="w-3 h-3" />
            <span>{doc.owner.split("@")[0]}</span>
          </div>
        )}
      </div>

      {/* Folder Path */}
      {doc.folder_path && (
        <div className="mt-3 flex items-center gap-1.5 text-xs text-zinc-500">
          <Folder className="w-3 h-3 flex-shrink-0" />
          <span className="truncate">{doc.folder_path}</span>
        </div>
      )}

      {/* JIRA Keys */}
      {doc.jira_keys && doc.jira_keys.length > 0 && (
        <div className="mt-3">
          <div className="text-xs text-zinc-500 mb-1">JIRA</div>
          <div className="flex flex-wrap gap-1">
            {doc.jira_keys.map((key) => (
              <Badge key={key} variant="outline" className="text-xs font-mono">
                {key}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Keywords */}
      {doc.keywords && doc.keywords.length > 0 && (
        <div className="mt-3">
          <div className="text-xs text-zinc-500 mb-1">Keywords</div>
          <div className="flex flex-wrap gap-1">
            {doc.keywords.slice(0, 6).map((keyword) => (
              <span
                key={keyword}
                className="text-xs bg-zinc-800/50 text-zinc-400 px-1.5 py-0.5 rounded"
              >
                {keyword}
              </span>
            ))}
            {doc.keywords.length > 6 && (
              <span className="text-xs text-zinc-500">
                +{doc.keywords.length - 6} more
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
