"use client";

import { Rocket, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { WorkspaceDetail } from "@/lib/api";
import { formatTimestampAgo } from "@/lib/time-utils";

interface DeploymentsTabProps {
  workspace: WorkspaceDetail;
  onUpdate?: (workspace: WorkspaceDetail) => void;
}

export function DeploymentsTab({ workspace }: DeploymentsTabProps) {
  const runningDeployments = workspace.deployments.filter(d => d.status === "running");
  const otherDeployments = workspace.deployments.filter(d => d.status !== "running");

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="space-y-4">
        {/* Running Deployments */}
        {runningDeployments.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Rocket className="h-4 w-4 text-emerald-400" />
              <h3 className="text-sm font-medium text-zinc-300">Running</h3>
            </div>
            <div className="space-y-2">
              {runningDeployments.map((deployment) => (
                <div
                  key={`${deployment.environment}-${deployment.namespace}`}
                  className="bg-emerald-500/5 border border-emerald-700/50 rounded-lg p-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-emerald-400 border-emerald-600/50">
                          {deployment.status || "running"}
                        </Badge>
                        <span className="text-sm text-zinc-300 font-medium">{deployment.environment}</span>
                        {deployment.namespace && deployment.namespace !== "" && (
                          <span className="text-xs text-zinc-500">/{deployment.namespace}</span>
                        )}
                      </div>
                      {deployment.version && (
                        <div className="flex items-center gap-2 text-xs text-zinc-400 mb-1">
                          <span className="text-zinc-600">Version:</span>
                          <code className="font-mono">{deployment.version}</code>
                        </div>
                      )}
                      <div className="flex items-center gap-3 text-xs text-zinc-500">
                        <span>Updated {formatTimestampAgo(deployment.updated_at)}</span>
                      </div>
                    </div>
                    {deployment.url && (
                      <a
                        href={deployment.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-zinc-500 hover:text-zinc-300 transition-colors shrink-0"
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

        {/* Other Deployments */}
        {otherDeployments.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Rocket className="h-4 w-4 text-zinc-400" />
              <h3 className="text-sm font-medium text-zinc-300">Other</h3>
            </div>
            <div className="space-y-2">
              {otherDeployments.map((deployment) => (
                <div
                  key={`${deployment.environment}-${deployment.namespace}`}
                  className={`rounded-lg p-3 border ${
                    deployment.status === "pending"
                      ? "bg-blue-500/5 border-blue-700/50"
                      : deployment.status === "failed"
                      ? "bg-red-500/5 border-red-700/50"
                      : "bg-zinc-800/30 border-zinc-700"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge
                          variant="outline"
                          className={`text-[10px] px-1.5 py-0 ${
                            deployment.status === "pending"
                              ? "text-blue-400 border-blue-600/50"
                              : deployment.status === "failed"
                              ? "text-red-400 border-red-600/50"
                              : "text-zinc-500 border-zinc-600/50"
                          }`}
                        >
                          {deployment.status || "unknown"}
                        </Badge>
                        <span className="text-sm text-zinc-300 font-medium">{deployment.environment}</span>
                        {deployment.namespace && deployment.namespace !== "" && (
                          <span className="text-xs text-zinc-500">/{deployment.namespace}</span>
                        )}
                      </div>
                      {deployment.version && (
                        <div className="flex items-center gap-2 text-xs text-zinc-400 mb-1">
                          <span className="text-zinc-600">Version:</span>
                          <code className="font-mono">{deployment.version}</code>
                        </div>
                      )}
                      <div className="flex items-center gap-3 text-xs text-zinc-500">
                        <span>Updated {formatTimestampAgo(deployment.updated_at)}</span>
                      </div>
                    </div>
                    {deployment.url && (
                      <a
                        href={deployment.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-zinc-500 hover:text-zinc-300 transition-colors shrink-0"
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

        {/* Empty State */}
        {workspace.deployments.length === 0 && (
          <div className="text-center py-8">
            <p className="text-sm text-zinc-500">No deployments in this workspace</p>
            <p className="text-xs text-zinc-600 mt-1">Deployments can be added manually or discovered from MRs</p>
          </div>
        )}
      </div>
    </div>
  );
}
