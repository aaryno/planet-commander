"use client";

import { usePoll } from "@/lib/polling";
import { api, JobRunResponse } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Activity, CheckCircle2, XCircle, Clock, Play } from "lucide-react";
import { useCallback, useState } from "react";

export function BackgroundJobsCard() {
  const [triggeringJob, setTriggeringJob] = useState<string | null>(null);

  const { data: jobData, loading, error, refresh } = usePoll<{ runs: JobRunResponse[]; total: number }>(
    () => api.backgroundJobRuns(20),
    60_000 // 1 minute
  );

  const jobs = jobData?.runs || [];

  const handleTrigger = useCallback(async (jobName: string) => {
    setTriggeringJob(jobName);
    try {
      await api.triggerBackgroundJob(jobName);
      // Wait a moment then refresh to show the new run
      setTimeout(refresh, 1000);
    } catch (err) {
      console.error("Failed to trigger job:", err);
    } finally {
      setTriggeringJob(null);
    }
  }, [refresh]);

  const statusIcon = {
    running: Clock,
    success: CheckCircle2,
    failed: XCircle,
  };

  const statusColor = {
    running: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    success: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    failed: "bg-red-500/20 text-red-400 border-red-500/30",
  };

  // Group jobs by name to show trigger buttons
  const uniqueJobNames = Array.from(new Set(jobs.map(j => j.job_name)));

  const menuItems = [
    { label: "Refresh", onClick: refresh },
  ];

  return (
    <ScrollableCard
      title="Background Jobs"
      icon={<Activity className="w-4 h-4" />}
      menuItems={menuItems}
      stickyHeader={
        uniqueJobNames.length > 0 ? (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-zinc-500">Trigger manually:</span>
            {uniqueJobNames.map((jobName) => (
              <Button
                key={jobName}
                size="sm"
                variant="outline"
                onClick={() => handleTrigger(jobName)}
                disabled={triggeringJob === jobName}
                className="h-6 text-[10px] px-2"
              >
                <Play className="w-3 h-3 mr-1" />
                {jobName}
              </Button>
            ))}
          </div>
        ) : undefined
      }
    >
      {loading && !jobs.length && (
        <div className="flex items-center justify-center py-8">
          <p className="text-xs text-zinc-500">Loading job history...</p>
        </div>
      )}

      {error && (
        <div className="p-4 rounded border border-red-800 bg-red-900/20">
          <p className="text-xs text-red-400">Failed to load job history</p>
        </div>
      )}

      {jobs.length === 0 && !loading && (
        <div className="text-center py-8">
          <p className="text-sm text-zinc-500">No jobs run yet</p>
          <p className="text-xs text-zinc-600 mt-1">
            Background jobs will appear here once they start running
          </p>
        </div>
      )}

      {jobs.length > 0 && (
        <div className="space-y-2">
          {jobs.map((job) => {
            const StatusIcon = statusIcon[job.status];

            return (
              <div
                key={job.id}
                className="p-3 rounded border border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800/50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-mono text-zinc-200">
                        {job.job_name}
                      </span>
                      <Badge
                        variant="outline"
                        className={`${statusColor[job.status]} text-[10px] px-1.5 py-0 flex items-center gap-1`}
                      >
                        <StatusIcon className="w-3 h-3" />
                        {job.status}
                      </Badge>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-zinc-500">
                      <span>
                        {new Date(job.started_at).toLocaleString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </span>
                      {job.duration_seconds !== null && (
                        <span>{job.duration_seconds.toFixed(1)}s</span>
                      )}
                      {job.records_processed > 0 && (
                        <span className="text-emerald-400">
                          {job.records_processed} records
                        </span>
                      )}
                    </div>

                    {job.error_message && (
                      <div className="mt-2 p-2 rounded bg-red-900/20 border border-red-800/30">
                        <p className="text-xs text-red-400 font-mono break-all">
                          {job.error_message}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </ScrollableCard>
  );
}
