import { Badge } from "@/components/ui/badge";
import { GitMerge, Calendar, User, GitBranch, ExternalLink, CheckCircle2, XCircle, Clock } from "lucide-react";
import type { GitLabMR } from "@/lib/api";
import { formatDaysAgo } from "@/lib/time-utils";
import { MR_STATE_COLORS, MR_APPROVAL_COLORS, CI_STATUS_COLORS, getStatusColor } from "@/lib/status-colors";

interface GitLabMRCardProps {
  mr: GitLabMR;
}

export function GitLabMRCard({ mr }: GitLabMRCardProps) {
  const ageDisplay = formatDaysAgo(mr.age_days);

  return (
    <div className="p-4 rounded-lg border border-zinc-800 hover:border-zinc-700 transition-colors group">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2 flex-1 min-w-0">
          <GitMerge className="w-5 h-5 text-zinc-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <a
              href={mr.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-base font-semibold text-zinc-200 hover:text-zinc-100 line-clamp-2 flex items-center gap-1 group"
            >
              !{mr.external_mr_id}: {mr.title}
              <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
            </a>
          </div>
        </div>
      </div>

      {/* Branch flow */}
      <div className="flex items-center gap-2 mt-2 text-xs text-zinc-400">
        <GitBranch className="w-3 h-3" />
        <span className="truncate">{mr.source_branch}</span>
        <span>→</span>
        <span className="truncate">{mr.target_branch}</span>
      </div>

      {/* Status badges */}
      <div className="flex items-center gap-2 mt-3 flex-wrap">
        {/* State */}
        <Badge
          variant="outline"
          className={`text-xs ${getStatusColor(MR_STATE_COLORS, mr.state) || "text-zinc-400 border-zinc-600/30"}`}
        >
          {mr.state}
        </Badge>

        {/* Approval status */}
        {mr.approval_status && (
          <Badge
            variant="outline"
            className={`text-xs ${getStatusColor(MR_APPROVAL_COLORS, mr.approval_status) || "text-zinc-400 border-zinc-600/30"}`}
          >
            {mr.is_approved ? (
              <>
                <CheckCircle2 className="w-3 h-3 mr-1" />
                Approved
              </>
            ) : (
              <>
                <Clock className="w-3 h-3 mr-1" />
                {mr.approval_status}
              </>
            )}
          </Badge>
        )}

        {/* CI status */}
        {mr.ci_status && (
          <Badge
            variant="outline"
            className={`text-xs ${getStatusColor(CI_STATUS_COLORS, mr.ci_status) || "text-zinc-400 border-zinc-600/30"}`}
          >
            {mr.is_ci_passing ? (
              <>
                <CheckCircle2 className="w-3 h-3 mr-1" />
                CI Passed
              </>
            ) : mr.ci_status === "running" ? (
              <>
                <Clock className="w-3 h-3 mr-1" />
                CI Running
              </>
            ) : (
              <>
                <XCircle className="w-3 h-3 mr-1" />
                CI {mr.ci_status}
              </>
            )}
          </Badge>
        )}

        {/* Project */}
        {mr.project_name && mr.project_name !== "unknown" && (
          <Badge variant="outline" className="text-xs">
            {mr.project_name}
          </Badge>
        )}
      </div>

      {/* Metadata */}
      <div className="flex items-center gap-4 mt-3 text-xs text-zinc-500">
        {/* Author */}
        <div className="flex items-center gap-1">
          <User className="w-3 h-3" />
          <span>{mr.author}</span>
        </div>

        {/* Age */}
        <div className="flex items-center gap-1">
          <Calendar className="w-3 h-3" />
          <span>{ageDisplay}</span>
        </div>

        {/* Reviewers count */}
        {mr.reviewers && mr.reviewers.length > 0 && (
          <div className="flex items-center gap-1">
            <span>{mr.reviewers.length} reviewer{mr.reviewers.length !== 1 ? "s" : ""}</span>
          </div>
        )}
      </div>

      {/* JIRA Keys */}
      {mr.jira_keys && mr.jira_keys.length > 0 && (
        <div className="mt-3">
          <div className="flex flex-wrap gap-1">
            {mr.jira_keys.map((key) => (
              <Badge key={key} variant="outline" className="text-xs font-mono">
                {key}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Repository (if not obvious from project) */}
      {mr.short_repository !== mr.project_name && (
        <div className="mt-2 text-xs text-zinc-600 truncate">
          {mr.repository}
        </div>
      )}
    </div>
  );
}
