"use client";

import { useCallback, ReactNode } from "react";
import {
  MoreVertical,
  GitBranch,
  MessageCircle,
  BarChart2,
  Layout,
  FileText,
  Book,
  Bot,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { ProjectAgents } from "@/components/agents/ProjectAgents";
import { usePoll } from "@/lib/polling";
import { gitlabUrl, slackChannelUrl, grafanaUrl } from "@/lib/urls";
import { api, TemporalKeyHealth, TemporalUnanswered, TemporalMRsResponse } from "@/lib/api";

import { NeedsAttentionBanner } from "@/components/temporal/NeedsAttentionBanner";
import { KeyHealth } from "@/components/temporal/KeyHealth";
import { UnansweredSlack } from "@/components/temporal/UnansweredSlack";
import { SlackSentimentCard } from "@/components/temporal/SlackSentiment";
import { TemporalJira } from "@/components/temporal/TemporalJira";
import { TemporalMRs } from "@/components/temporal/TemporalMRs";
import { PerformanceMetrics } from "@/components/temporal/PerformanceMetrics";
import { UsageMetrics } from "@/components/temporal/UsageMetrics";
import { TemporalUsers } from "@/components/temporal/TemporalUsers";

const ICON_MAP: Record<string, ReactNode> = {
  "git-branch": <GitBranch className="h-3.5 w-3.5" />,
  "message-circle": <MessageCircle className="h-3.5 w-3.5" />,
  "bar-chart": <BarChart2 className="h-3.5 w-3.5" />,
  layout: <Layout className="h-3.5 w-3.5" />,
  "file-text": <FileText className="h-3.5 w-3.5" />,
  book: <Book className="h-3.5 w-3.5" />,
};

const LINKS: Record<string, Array<{ label: string; url: string; icon: string }>> = {
  git: [
    { label: "temporalio-cloud", url: gitlabUrl("temporal/temporalio-cloud"), icon: "git-branch" },
  ],
  slack: [
    { label: "#temporal-users", url: slackChannelUrl("temporal-users"), icon: "message-circle" },
    { label: "#temporal-dev", url: slackChannelUrl("temporal-dev"), icon: "message-circle" },
  ],
  grafana: [
    { label: "Platform Health", url: grafanaUrl("d/77b0bb16-2f51-4ecb-bf9d-06be203a6725"), icon: "bar-chart" },
    { label: "Platform Ops", url: grafanaUrl("d/temporal-platform-ops-v1"), icon: "bar-chart" },
    { label: "Tenant Health", url: grafanaUrl("d/temporal-tenant-health-v1"), icon: "bar-chart" },
  ],
  docs: [
    { label: "Admin Guide", url: "#", icon: "file-text" },
    { label: "User Guide", url: "#", icon: "book" },
  ],
};

export default function TemporalCommandCenter() {
  // Fetch data for the Needs Attention banner
  const keysFetcher = useCallback(() => api.temporalKeys(), []);
  const slackFetcher = useCallback(() => api.temporalSlackUnanswered(7), []);
  const mrsFetcher = useCallback(() => api.temporalMRs(), []);

  const { data: keysData } = usePoll<TemporalKeyHealth>(keysFetcher, 3600_000);
  const { data: slackData } = usePoll<TemporalUnanswered>(slackFetcher, 300_000);
  const { data: mrsData } = usePoll<TemporalMRsResponse>(mrsFetcher, 120_000);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-emerald-400">
            TEMPORAL COMMAND CENTER
          </h1>
          <p className="text-sm text-zinc-500">
            Temporal Cloud &middot; Account: efdqq
          </p>
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="border-zinc-700 text-zinc-300 hover:bg-zinc-800">
              <MoreVertical className="mr-2 h-4 w-4" /> Links
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-64 bg-zinc-900 border-zinc-700">
            {Object.entries(LINKS).map(([category, items]) => (
              <div key={category}>
                <DropdownMenuLabel className="text-xs uppercase text-zinc-500">
                  {category}
                </DropdownMenuLabel>
                {items.map((item, i) => (
                  <DropdownMenuItem key={i} asChild className="text-zinc-300 focus:bg-zinc-800">
                    <a href={item.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2">
                      {ICON_MAP[item.icon] || null}
                      {item.label}
                    </a>
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator className="bg-zinc-800" />
              </div>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Needs Attention Banner */}
      <NeedsAttentionBanner keys={keysData} slack={slackData} mrs={mrsData} />

      {/* Row 1: Slack + JIRA */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="space-y-4">
          <UnansweredSlack />
          <SlackSentimentCard />
        </div>
        <TemporalJira />
      </div>

      {/* Row 2: Performance + Usage */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PerformanceMetrics />
        <UsageMetrics />
      </div>

      {/* Row 3: MRs + Key Health */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TemporalMRs />
        <KeyHealth />
      </div>

      {/* Row 4: Users & Teams */}
      <TemporalUsers />

      {/* Agents section */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
        <div className="flex items-center gap-2 mb-3">
          <Bot className="h-4 w-4 text-zinc-400" />
          <h2 className="text-sm font-medium text-zinc-200">Agents</h2>
        </div>
        <ProjectAgents project="temporal" />
      </div>
    </div>
  );
}
