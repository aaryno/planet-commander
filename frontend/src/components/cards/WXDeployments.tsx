"use client";

import { useCallback } from "react";
import { Rocket } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Badge } from "@/components/ui/badge";
import { usePoll } from "@/lib/polling";
import { api, WXDeploymentResponse } from "@/lib/api";
import { formatTimestampAgo } from "@/lib/time-utils";
import { ENV_COLORS } from "@/lib/status-colors";
import { ExpandableRow } from "@/components/shared/ExpandableRow";
import { DeploymentExpanded } from "@/components/expanded/DeploymentExpanded";

function formatBuildId(buildId: string): string {
  // Shorten commit SHA if it's a long hash
  if (buildId.length > 12 && /^[0-9a-f]+$/i.test(buildId)) {
    return buildId.substring(0, 8);
  }
  return buildId;
}

export function WXDeployments() {
  const fetcher = useCallback(() => api.wxDeployments(), []);
  const { data, loading, error, refresh } = usePoll<WXDeploymentResponse>(
    fetcher,
    120_000 // 2 minutes
  );

  return (
    <ScrollableCard
      title="WX Deployments"
      icon={<Rocket className="h-4 w-4" />}
      menuItems={[{ label: "Refresh", onClick: refresh }]}
    >
      {loading && <p className="text-xs text-zinc-500">Loading deployments...</p>}
      {error && <p className="text-xs text-red-400">Failed to load deployment info</p>}

      {data && (
        <div className="space-y-2">
          {data.environments.map((env) => (
            <ExpandableRow
              key={env.name}
              summary={
                <div className="space-y-1">
                  {/* Environment header */}
                  <div className="flex items-center gap-2">
                    <Badge className={`${ENV_COLORS[env.name] || "bg-zinc-700 text-zinc-300"} text-[10px] px-1.5 py-0`}>
                      {env.name.toUpperCase()}
                    </Badge>
                    {env.tier && (
                      <Badge
                        className={`text-[10px] px-1.5 py-0 ${
                          env.tier === "prod"
                            ? "bg-red-600/20 text-red-400 border-red-600/30"
                            : "bg-slate-600/20 text-slate-400 border-slate-600/30"
                        }`}
                      >
                        {env.tier === "prod" ? "PROD" : "STAGING"}
                      </Badge>
                    )}
                    <span className="text-xs text-zinc-400 font-mono">
                      {formatBuildId(env.build_id)}
                    </span>
                    {env.status && (
                      <span className="text-[10px]">
                        {env.status === "healthy" && (
                          <span className="text-emerald-400">●</span>
                        )}
                        {env.status === "degraded" && (
                          <span className="text-yellow-400">●</span>
                        )}
                        {env.status === "down" && (
                          <span className="text-red-400">●</span>
                        )}
                      </span>
                    )}
                    {env.deployed_at && (
                      <span className="text-[10px] text-zinc-600 ml-auto">
                        {formatTimestampAgo(env.deployed_at)}
                      </span>
                    )}
                  </div>
                </div>
              }
            >
              <DeploymentExpanded
                tier={env.name}
                sha={env.build_id}
                argocdUrl={env.argocd_url}
                commitUrl={env.commit_url}
                health={env.status === "healthy" ? "Healthy" : env.status === "degraded" ? "Degraded" : env.status === "down" ? "Down" : undefined}
                syncStatus={undefined}
                lastSyncedAt={undefined}
              />
            </ExpandableRow>
          ))}

          {data.environments.length === 0 && (
            <p className="text-xs text-zinc-500">No deployment information available</p>
          )}
        </div>
      )}
    </ScrollableCard>
  );
}
