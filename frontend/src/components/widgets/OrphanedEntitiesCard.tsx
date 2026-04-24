"use client";

import { usePoll } from "@/lib/polling";
import { api, OrphanedEntities } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Badge } from "@/components/ui/badge";
import { GitBranch, FolderGit2, MessageSquare, FileText, AlertCircle } from "lucide-react";

export function OrphanedEntitiesCard() {
  const { data, loading, error, refresh } = usePoll<OrphanedEntities>(
    () => api.healthOrphanedEntities(),
    300_000 // 5 minutes
  );

  const menuItems = [{ label: "Refresh", onClick: refresh }];

  const totalOrphaned = data
    ? data.branches.length +
      data.worktrees.length +
      data.chats.length +
      data.jira_issues.length
    : 0;

  const entityTypes = [
    {
      key: "branches" as const,
      label: "Branches",
      icon: GitBranch,
      color: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    },
    {
      key: "worktrees" as const,
      label: "Worktrees",
      icon: FolderGit2,
      color: "bg-purple-500/20 text-purple-400 border-purple-500/30",
    },
    {
      key: "chats" as const,
      label: "Chats",
      icon: MessageSquare,
      color: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    },
    {
      key: "jira_issues" as const,
      label: "JIRA Issues",
      icon: FileText,
      color: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    },
  ];

  return (
    <ScrollableCard
      title="Orphaned Entities"
      icon={<AlertCircle className="w-4 h-4" />}
      menuItems={menuItems}
    >
      {loading && !data && (
        <div className="flex items-center justify-center py-8">
          <p className="text-xs text-zinc-500">Loading orphaned entities...</p>
        </div>
      )}

      {error && (
        <div className="p-4 rounded border border-red-800 bg-red-900/20">
          <p className="text-xs text-red-400">Failed to load orphaned entities</p>
        </div>
      )}

      {data && totalOrphaned === 0 && (
        <div className="text-center py-8">
          <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
          <p className="text-sm text-zinc-500">No orphaned entities</p>
          <p className="text-xs text-zinc-600 mt-1">
            All entities are linked to contexts
          </p>
        </div>
      )}

      {data && totalOrphaned > 0 && (
        <div className="space-y-3">
          {/* Summary */}
          <div className="p-3 rounded border border-zinc-800 bg-zinc-900/50">
            <div className="flex items-center justify-between">
              <span className="text-sm text-zinc-200">Total Orphaned</span>
              <Badge
                variant="outline"
                className="bg-red-500/20 text-red-400 border-red-500/30 text-[10px]"
              >
                <AlertCircle className="w-3 h-3 mr-1" />
                {totalOrphaned}
              </Badge>
            </div>
          </div>

          {/* Entity Type Breakdown */}
          {entityTypes.map((entityType) => {
            const entities = data[entityType.key];
            const Icon = entityType.icon;

            if (entities.length === 0) return null;

            return (
              <div key={entityType.key} className="space-y-2">
                <div className="flex items-center gap-2">
                  <Badge
                    variant="outline"
                    className={`${entityType.color} text-[10px] px-1.5 py-0 flex items-center gap-1`}
                  >
                    <Icon className="w-3 h-3" />
                    {entityType.label}
                  </Badge>
                  <span className="text-xs text-zinc-500">
                    {entities.length} orphaned
                  </span>
                </div>

                <div className="space-y-1">
                  {entities.slice(0, 5).map((entity: any) => (
                    <div
                      key={entity.id}
                      className="p-2 rounded border border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800/50 transition-colors"
                    >
                      <div className="flex items-start gap-2">
                        <Icon className="w-3 h-3 text-zinc-500 mt-0.5 shrink-0" />
                        <div className="flex-1 min-w-0">
                          {entityType.key === "branches" && (
                            <>
                              <p className="text-xs text-zinc-200 truncate">
                                {entity.name}
                              </p>
                              <p className="text-[10px] text-zinc-500 truncate">
                                {entity.repo}
                              </p>
                            </>
                          )}
                          {entityType.key === "worktrees" && (
                            <p className="text-xs text-zinc-200 truncate">
                              {entity.path}
                            </p>
                          )}
                          {entityType.key === "chats" && (
                            <>
                              <p className="text-xs text-zinc-200 truncate">
                                {entity.name}
                              </p>
                              {entity.jira_key && (
                                <p className="text-[10px] text-zinc-500">
                                  {entity.jira_key}
                                </p>
                              )}
                            </>
                          )}
                          {entityType.key === "jira_issues" && (
                            <>
                              <p className="text-xs text-zinc-200">
                                {entity.key}
                              </p>
                              <p className="text-[10px] text-zinc-500 truncate">
                                {entity.summary}
                              </p>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}

                  {entities.length > 5 && (
                    <p className="text-[10px] text-zinc-600 text-center pt-1">
                      +{entities.length - 5} more
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </ScrollableCard>
  );
}

// Add missing import
import { CheckCircle2 } from "lucide-react";
