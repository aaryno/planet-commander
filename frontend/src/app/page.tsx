"use client";

import { MessageSquare, GitPullRequest, CheckSquare, Activity, Phone, FileText, ScatterChart } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { SlackSummary } from "@/components/cards/SlackSummary";
import { OpenMRs } from "@/components/cards/OpenMRs";
import { JiraSummary } from "@/components/cards/JiraSummary";
import { WXDeployments } from "@/components/cards/WXDeployments";
import { DashboardGrid } from "@/components/layout/DashboardGrid";
import type { LayoutItem } from "react-grid-layout";

const DEFAULT_LAYOUT: LayoutItem[] = [
  { i: "slack",    x: 0, y: 0,  w: 6, h: 5, minW: 4, minH: 3 },
  { i: "mrs",      x: 6, y: 0,  w: 6, h: 5, minW: 4, minH: 3 },
  { i: "jira",     x: 0, y: 5,  w: 8, h: 8, minW: 4, minH: 4 },
  { i: "deploy",   x: 8, y: 5,  w: 4, h: 4, minW: 3, minH: 2 },
  { i: "traffic",  x: 8, y: 9,  w: 4, h: 4, minW: 3, minH: 2 },
  { i: "oncall",   x: 8, y: 13, w: 4, h: 4, minW: 3, minH: 2 },
  { i: "workload", x: 0, y: 13, w: 6, h: 5, minW: 4, minH: 3 },
  { i: "docs",     x: 6, y: 13, w: 6, h: 5, minW: 4, minH: 3 },
];

const CARDS: Record<string, React.ReactNode> = {
  slack: (
    <ScrollableCard title="Slack Summary" icon={<MessageSquare className="h-4 w-4" />}>
      <SlackSummary />
    </ScrollableCard>
  ),
  mrs: <OpenMRs />,
  jira: <JiraSummary />,
  deploy: <WXDeployments />,
  traffic: (
    <ScrollableCard
      title="Traffic Overview"
      icon={<Activity className="h-4 w-4" />}
      menuItems={[{ label: "Refresh" }, { label: "Configure" }]}
    >
      <div className="flex h-full items-center justify-center rounded-md border border-dashed border-zinc-700">
        <p className="text-sm text-zinc-500">Service traffic levels and patterns</p>
      </div>
    </ScrollableCard>
  ),
  oncall: (
    <ScrollableCard
      title="On-Call"
      icon={<Phone className="h-4 w-4" />}
      menuItems={[{ label: "Refresh" }, { label: "Configure" }]}
    >
      <div className="flex h-full items-center justify-center rounded-md border border-dashed border-zinc-700">
        <p className="text-sm text-zinc-500">Current rotation and recent incidents</p>
      </div>
    </ScrollableCard>
  ),
  workload: (
    <ScrollableCard
      title="Workload Scatter"
      icon={<ScatterChart className="h-4 w-4" />}
      menuItems={[{ label: "Refresh" }, { label: "Configure" }]}
    >
      <div className="flex h-full items-center justify-center rounded-md border border-dashed border-zinc-700">
        <p className="text-sm text-zinc-500">Queue size vs latency across workloads</p>
      </div>
    </ScrollableCard>
  ),
  docs: (
    <ScrollableCard
      title="Docs"
      icon={<FileText className="h-4 w-4" />}
      menuItems={[{ label: "Refresh" }, { label: "Configure" }]}
    >
      <div className="flex h-full items-center justify-center rounded-md border border-dashed border-zinc-700">
        <p className="text-sm text-zinc-500">Searchable docs from Google Drive and project files</p>
      </div>
    </ScrollableCard>
  ),
};

export default function DashboardPage() {
  return (
    <div className="space-y-4">
      <div className="px-2">
        <h1 className="text-2xl font-bold text-zinc-100">Dashboard</h1>
        <p className="text-sm text-zinc-500">Compute Platform overview &mdash; drag cards to rearrange, resize from corners</p>
      </div>
      <DashboardGrid page="main" cards={CARDS} defaultLayout={DEFAULT_LAYOUT} />
    </div>
  );
}
