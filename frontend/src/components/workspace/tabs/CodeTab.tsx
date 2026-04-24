"use client";

import { GitBranch, ExternalLink, Folder } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { WorkspaceDetail } from "@/lib/api";

interface CodeTabProps {
  workspace: WorkspaceDetail;
  onUpdate?: (workspace: WorkspaceDetail) => void;
}

export function CodeTab({ workspace }: CodeTabProps) {
  const activeBranch = workspace.branches.find(b => b.is_active);
  const inactiveBranches = workspace.branches.filter(b => !b.is_active);

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="space-y-4">
        {/* Active Branch */}
        {activeBranch && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <GitBranch className="h-4 w-4 text-green-400" />
              <h3 className="text-sm font-medium text-zinc-300">Active Branch</h3>
            </div>
            <div className="bg-green-500/5 border border-green-700/50 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <code className="text-sm text-green-400 font-mono">{activeBranch.name}</code>
                <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-green-400 border-green-600/50">
                  active
                </Badge>
              </div>
              {activeBranch.worktree_path && (
                <div className="flex items-center gap-2 text-xs text-zinc-400">
                  <Folder className="h-3.5 w-3.5" />
                  <code className="flex-1 truncate">{activeBranch.worktree_path}</code>
                </div>
              )}
              {/* Show associated MR if exists */}
              {workspace.merge_requests
                .filter(mr => mr.branch_name === activeBranch.name)
                .map((mr) => (
                  <div key={`${mr.project}-${mr.iid}`} className="mt-2 pt-2 border-t border-green-700/30">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-zinc-400">Merge Request:</span>
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-mono">
                          !{mr.iid}
                        </Badge>
                        {mr.status && (
                          <Badge
                            variant="outline"
                            className={`text-[10px] px-1.5 py-0 ${
                              mr.status === "open"
                                ? "text-blue-400 border-blue-600/50"
                                : mr.status === "merged"
                                ? "text-emerald-400 border-emerald-600/50"
                                : "text-zinc-500 border-zinc-600/50"
                            }`}
                          >
                            {mr.status}
                          </Badge>
                        )}
                      </div>
                      {mr.url && (
                        <a
                          href={mr.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-zinc-500 hover:text-zinc-300 transition-colors"
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Other Branches */}
        {inactiveBranches.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <GitBranch className="h-4 w-4 text-zinc-400" />
              <h3 className="text-sm font-medium text-zinc-300">Other Branches</h3>
            </div>
            <div className="space-y-2">
              {inactiveBranches.map((branch) => (
                <div key={branch.name} className="bg-zinc-800/30 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <code className="text-sm text-zinc-300 font-mono truncate flex-1">{branch.name}</code>
                    {branch.worktree_path && (
                      <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-zinc-500 shrink-0">
                        worktree
                      </Badge>
                    )}
                  </div>
                  {branch.worktree_path && (
                    <div className="flex items-center gap-2 text-xs text-zinc-500">
                      <Folder className="h-3.5 w-3.5" />
                      <code className="flex-1 truncate">{branch.worktree_path}</code>
                    </div>
                  )}
                  {/* Show associated MR if exists */}
                  {workspace.merge_requests
                    .filter(mr => mr.branch_name === branch.name)
                    .map((mr) => (
                      <div key={`${mr.project}-${mr.iid}`} className="mt-2 pt-2 border-t border-zinc-700/30">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-zinc-500">MR:</span>
                            <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-mono">
                              !{mr.iid}
                            </Badge>
                            {mr.status && (
                              <Badge
                                variant="outline"
                                className={`text-[10px] px-1.5 py-0 ${
                                  mr.status === "open"
                                    ? "text-blue-400 border-blue-600/50"
                                    : mr.status === "merged"
                                    ? "text-emerald-400 border-emerald-600/50"
                                    : "text-zinc-500 border-zinc-600/50"
                                }`}
                              >
                                {mr.status}
                              </Badge>
                            )}
                          </div>
                          {mr.url && (
                            <a
                              href={mr.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-zinc-500 hover:text-zinc-300 transition-colors"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Orphaned MRs (no matching branch) */}
        {workspace.merge_requests
          .filter(mr => !workspace.branches.some(b => b.name === mr.branch_name))
          .length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <GitBranch className="h-4 w-4 text-blue-400" />
              <h3 className="text-sm font-medium text-zinc-300">Merge Requests</h3>
            </div>
            <div className="space-y-2">
              {workspace.merge_requests
                .filter(mr => !workspace.branches.some(b => b.name === mr.branch_name))
                .map((mr) => (
                  <div key={`${mr.project}-${mr.iid}`} className="bg-blue-500/5 border border-blue-700/50 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-mono text-blue-400 border-blue-600/50">
                          !{mr.iid}
                        </Badge>
                        {mr.status && (
                          <Badge
                            variant="outline"
                            className={`text-[10px] px-1.5 py-0 ${
                              mr.status === "open"
                                ? "text-blue-400 border-blue-600/50"
                                : mr.status === "merged"
                                ? "text-emerald-400 border-emerald-600/50"
                                : "text-zinc-500 border-zinc-600/50"
                            }`}
                          >
                            {mr.status}
                          </Badge>
                        )}
                      </div>
                      {mr.url && (
                        <a
                          href={mr.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-zinc-500 hover:text-zinc-300 transition-colors"
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      )}
                    </div>
                    <code className="text-xs text-zinc-400 truncate block">{mr.branch_name}</code>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {workspace.branches.length === 0 && workspace.merge_requests.length === 0 && (
          <div className="text-center py-8">
            <p className="text-sm text-zinc-500">No branches or MRs in this workspace</p>
            <p className="text-xs text-zinc-600 mt-1">Branches will be automatically discovered from agents</p>
          </div>
        )}
      </div>
    </div>
  );
}
