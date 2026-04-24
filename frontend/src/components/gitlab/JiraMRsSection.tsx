import { useCallback } from "react";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { GitLabMRCard } from "./GitLabMRCard";
import { Badge } from "@/components/ui/badge";
import { GitMerge, RefreshCw } from "lucide-react";

interface JiraMRsSectionProps {
  jiraKey: string;
  limit?: number;
}

export function JiraMRsSection({ jiraKey, limit = 20 }: JiraMRsSectionProps) {
  const fetcher = useCallback(() => {
    return api.gitlabMRByJira(jiraKey);
  }, [jiraKey]);

  const { data, loading, error, refresh } = usePoll(fetcher, 600_000); // 10 min

  const stickyHeader = (
    <div className="flex justify-between items-center text-xs">
      <span className="text-zinc-500">
        {data?.total || 0} MR{data?.total !== 1 ? "s" : ""} for {jiraKey}
      </span>
      <div className="flex items-center gap-2">
        {data && data.mrs.filter((mr) => mr.is_open).length > 0 && (
          <Badge variant="outline" className="text-xs text-blue-400 border-blue-500/30">
            {data.mrs.filter((mr) => mr.is_open).length} open
          </Badge>
        )}
        {data && data.mrs.filter((mr) => mr.is_merged).length > 0 && (
          <Badge variant="outline" className="text-xs text-emerald-400 border-emerald-500/30">
            {data.mrs.filter((mr) => mr.is_merged).length} merged
          </Badge>
        )}
      </div>
    </div>
  );

  const menuItems = [
    {
      label: "Refresh",
      onClick: refresh,
      icon: <RefreshCw className="w-3 h-3" />,
    },
  ];

  return (
    <ScrollableCard
      title={`MRs for ${jiraKey}`}
      icon={<GitMerge className="w-5 h-5" />}
      menuItems={menuItems}
      stickyHeader={stickyHeader}
    >
      {loading && <p className="text-xs text-zinc-500">Loading merge requests...</p>}
      {error && <p className="text-xs text-red-400">Error loading merge requests</p>}
      {!loading && data && data.mrs.length === 0 && (
        <p className="text-xs text-zinc-500">No merge requests found for this JIRA ticket</p>
      )}
      {data && data.mrs.length > 0 && (
        <div className="space-y-3">
          {data.mrs.slice(0, limit).map((mr) => (
            <GitLabMRCard key={mr.id} mr={mr} />
          ))}
        </div>
      )}
    </ScrollableCard>
  );
}
