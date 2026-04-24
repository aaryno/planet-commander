"use client";

import { useEffect, useState } from "react";
import { ExternalLinks } from "@/components/shared/ExternalLinks";
import { Badge } from "@/components/ui/badge";
import { formatTimestampAgo } from "@/lib/time-utils";

interface DeploymentExpandedProps {
  tier: string;
  sha: string;
  argocdUrl?: string;
  commitUrl?: string;
  health?: string;
  syncStatus?: string;
  lastSyncedAt?: string;
}

const DEPLOY_MRS: Record<string, { iid: number; repo: string; label: string }> = {
  "prod-us": { iid: 807, repo: "wx/wx", label: "Production Deploy" },
  "dev-01": { iid: 1084, repo: "wx/wx", label: "Dev Deploy" },
  "loadtest-01": { iid: 1084, repo: "wx/wx", label: "LoadTest Deploy" },
  "staging-01": { iid: 1084, repo: "wx/wx", label: "Staging Deploy" },
};

function deployMrUrl(repo: string, iid: number): string {
  return `https://hello.planet.com/code/${repo}/-/merge_requests/${iid}`;
}

export function DeploymentExpanded({
  tier,
  sha,
  argocdUrl,
  commitUrl,
  health,
  syncStatus,
  lastSyncedAt,
}: DeploymentExpandedProps) {
  const [commitCount, setCommitCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchCommitCount() {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch(`/api/wx/deployments/commits-since/${sha}`);
        if (!res.ok) throw new Error(`${res.status}`);
        const data = await res.json();
        if (!cancelled) {
          setCommitCount(data.count ?? data.commits ?? 0);
        }
      } catch (err) {
        if (!cancelled) {
          setError("Failed to load");
          setCommitCount(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    if (sha) {
      fetchCommitCount();
    } else {
      setLoading(false);
    }

    return () => {
      cancelled = true;
    };
  }, [sha]);

  const deployMr = DEPLOY_MRS[tier];

  // Build external links
  const links: Array<{ label: string; url: string }> = [];
  if (argocdUrl) {
    links.push({ label: "ArgoCD", url: argocdUrl });
  }
  if (commitUrl) {
    links.push({ label: "Commit", url: commitUrl });
  }
  if (deployMr) {
    links.push({
      label: `Deploy MR !${deployMr.iid}`,
      url: deployMrUrl(deployMr.repo, deployMr.iid),
    });
  }

  return (
    <div className="space-y-2 text-xs">
      {/* Commits since deploy */}
      <div className="flex items-center gap-2 text-zinc-300">
        <span className="text-zinc-500">Commits since deploy:</span>
        {loading ? (
          <span className="inline-block h-3 w-16 rounded bg-zinc-700 animate-pulse" />
        ) : error ? (
          <span className="text-zinc-600">{error}</span>
        ) : (
          <span className="text-zinc-200 font-medium">
            {commitCount} on main
          </span>
        )}
      </div>

      {/* Deploy MR */}
      {deployMr && (
        <div className="flex items-center gap-2 text-zinc-300">
          <span className="text-zinc-500">Deploy MR:</span>
          <a
            href={deployMrUrl(deployMr.repo, deployMr.iid)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-400 hover:text-blue-300 transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            !{deployMr.iid}
          </a>
          <span className="text-zinc-400">{deployMr.label}</span>
        </div>
      )}

      {/* ArgoCD sync + Health status */}
      {(syncStatus || health) && (
        <div className="flex items-center gap-4 text-zinc-300">
          {syncStatus && (
            <div className="flex items-center gap-1.5">
              <span className="text-zinc-500">ArgoCD:</span>
              <Badge
                className={`text-[10px] px-1.5 py-0 ${
                  syncStatus === "Synced"
                    ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                    : "bg-amber-500/15 text-amber-400 border-amber-500/30"
                }`}
              >
                {syncStatus}
              </Badge>
            </div>
          )}
          {health && (
            <div className="flex items-center gap-1.5">
              <span className="text-zinc-500">Health:</span>
              <Badge
                className={`text-[10px] px-1.5 py-0 ${
                  health === "Healthy"
                    ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                    : health === "Degraded"
                      ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
                      : "bg-red-500/15 text-red-400 border-red-500/30"
                }`}
              >
                {health}
              </Badge>
            </div>
          )}
        </div>
      )}

      {/* Last sync time */}
      {lastSyncedAt && (
        <div className="text-zinc-500">
          Last sync: {formatTimestampAgo(lastSyncedAt)}
        </div>
      )}

      {/* External links row */}
      {links.length > 0 && (
        <div className="pt-1 border-t border-zinc-800/40">
          <ExternalLinks links={links} />
        </div>
      )}
    </div>
  );
}
