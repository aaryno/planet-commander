import { useCallback } from "react";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { GoogleDriveDocCard } from "./GoogleDriveDocCard";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, RefreshCw } from "lucide-react";

interface PostmortemsSectionProps {
  project?: string;
  limit?: number;
}

export function PostmortemsSection({ project, limit = 20 }: PostmortemsSectionProps) {
  const fetcher = useCallback(() => {
    return api.googleDrivePostmortems(project, limit);
  }, [project, limit]);

  const { data, loading, error, refresh } = usePoll(fetcher, 600_000); // 10 min

  const stickyHeader = (
    <div className="flex justify-between items-center text-xs">
      <span className="text-zinc-500">
        {data?.total || 0} postmortem{data?.total !== 1 ? "s" : ""}
        {project && ` for ${project}`}
      </span>
      <div className="flex items-center gap-2">
        {data && data.documents.filter((d) => d.age_days < 90).length > 0 && (
          <Badge variant="outline" className="text-xs text-blue-400 border-blue-500/30">
            {data.documents.filter((d) => d.age_days < 90).length} recent
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
      title={project ? `${project.toUpperCase()} Postmortems` : "Recent Postmortems"}
      icon={<AlertCircle className="w-5 h-5" />}
      menuItems={menuItems}
      stickyHeader={stickyHeader}
    >
      {loading && <p className="text-xs text-zinc-500">Loading postmortems...</p>}
      {error && <p className="text-xs text-red-400">Error loading postmortems</p>}
      {!loading && data && data.documents.length === 0 && (
        <p className="text-xs text-zinc-500">No postmortems found</p>
      )}
      {data && data.documents.length > 0 && (
        <div className="space-y-3">
          {data.documents.map((doc) => (
            <GoogleDriveDocCard key={doc.id} doc={doc} />
          ))}
        </div>
      )}
    </ScrollableCard>
  );
}
