"use client";

import { ReactNode, useCallback, useState } from "react";
import { MoreVertical, GitBranch, MessageCircle, BarChart2, Layout, FileText, Book, Bot } from "lucide-react";
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
import { ChatSidebar } from "@/components/agents/ChatSidebar";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { DashboardGrid } from "@/components/layout/DashboardGrid";
import { api } from "@/lib/api";
import type { Agent } from "@/lib/api";
import type { LayoutItem } from "react-grid-layout";
import { useUrlNullableParam, useUrlBoolParam } from "@/lib/use-url-state";
import { PROJECT_COLORS } from "@/lib/status-colors";

const ICON_MAP: Record<string, ReactNode> = {
  "git-branch": <GitBranch className="h-3.5 w-3.5" />,
  "message-circle": <MessageCircle className="h-3.5 w-3.5" />,
  "bar-chart": <BarChart2 className="h-3.5 w-3.5" />,
  layout: <Layout className="h-3.5 w-3.5" />,
  "file-text": <FileText className="h-3.5 w-3.5" />,
  book: <Book className="h-3.5 w-3.5" />,
  "check-square": <Layout className="h-3.5 w-3.5" />,
};

const PROJECT_DESCRIPTIONS: Record<string, string> = {
  wx: "Work Exchange - Task orchestration platform",
  g4: "G4 - Satellite imagery processing pipeline",
  jobs: "Jobs - Compute job management platform",
  temporal: "Temporal - Workflow orchestration service",
};

const DEFAULT_LAYOUT: LayoutItem[] = [
  { i: "agents",  x: 0, y: 0, w: 12, h: 5, minW: 4, minH: 3 },
  { i: "metrics", x: 0, y: 5, w: 12, h: 4, minW: 4, minH: 2 },
];

interface ProjectPageProps {
  project: string;
  children?: ReactNode;
  /** Extra cards to add to the grid */
  extraCards?: Record<string, React.ReactNode>;
  /** Override default layout */
  layout?: LayoutItem[];
}

const STUB_LINKS: Record<string, Record<string, Array<{ label: string; url: string; icon: string }>>> = {
  wx: {
    git: [
      { label: "wx (monorepo)", url: "https://hello.planet.com/code/wx/wx", icon: "git-branch" },
      { label: "eso-golang", url: "https://hello.planet.com/code/wx/eso-golang", icon: "git-branch" },
    ],
    slack: [{ label: "#wx-users", url: "#", icon: "message-circle" }],
    grafana: [
      { label: "WX Tasks", url: "#", icon: "bar-chart" },
      { label: "WX Workers", url: "#", icon: "bar-chart" },
    ],
    jira: [{ label: "WX Board", url: "#", icon: "layout" }],
    docs: [
      { label: "WX Architecture", url: "#", icon: "file-text" },
      { label: "WX Runbook", url: "#", icon: "book" },
    ],
  },
  g4: {
    git: [
      { label: "g4 (main)", url: "https://hello.planet.com/code/product/g4-wk/g4", icon: "git-branch" },
      { label: "g4-task", url: "https://hello.planet.com/code/product/g4-wk/g4-task", icon: "git-branch" },
    ],
    slack: [{ label: "#g4-users", url: "#", icon: "message-circle" }],
    grafana: [
      { label: "G4 Cluster Overview", url: "#", icon: "bar-chart" },
      { label: "G4 Tasks", url: "#", icon: "bar-chart" },
    ],
    jira: [{ label: "G4 Board", url: "#", icon: "layout" }],
    docs: [{ label: "G4 Architecture", url: "#", icon: "file-text" }],
  },
  jobs: {
    git: [{ label: "jobs", url: "#", icon: "git-branch" }],
    slack: [{ label: "#jobs-users", url: "#", icon: "message-circle" }],
    grafana: [
      { label: "Jobs 3E", url: "#", icon: "bar-chart" },
      { label: "Jobs Alerts", url: "#", icon: "bar-chart" },
    ],
    jira: [{ label: "Jobs Board", url: "#", icon: "layout" }],
    docs: [{ label: "Jobs Architecture", url: "#", icon: "file-text" }],
  },
  temporal: {
    git: [{ label: "temporalio-cloud", url: "#", icon: "git-branch" }],
    slack: [{ label: "#temporal", url: "#", icon: "message-circle" }],
    grafana: [{ label: "Temporal Metrics", url: "#", icon: "bar-chart" }],
    jira: [{ label: "Temporal Board", url: "#", icon: "layout" }],
    docs: [{ label: "Temporal Operations", url: "#", icon: "file-text" }],
  },
};

export function ProjectPage({ project, children, extraCards, layout }: ProjectPageProps) {
  const links = STUB_LINKS[project] || {};
  const color = PROJECT_COLORS[project] || "text-zinc-400";
  const description = PROJECT_DESCRIPTIONS[project] || project;

  const [sidebarAgentId, setSidebarAgentId] = useUrlNullableParam("agent");
  const [sidebarDocked, setSidebarDocked] = useUrlBoolParam("docked");
  const [sidebarAgent, setSidebarAgent] = useState<Agent | null>(null);
  const sidebarOpen = sidebarAgentId !== null;

  const handleAgentClick = useCallback((agent: Agent) => {
    setSidebarAgent(agent);
    setSidebarAgentId(agent.id);
  }, [setSidebarAgentId]);

  const handleSidebarClose = useCallback((open: boolean) => {
    if (!open) setSidebarAgentId(null);
  }, [setSidebarAgentId]);

  const handleHide = useCallback(async (id: string) => {
    try {
      await api.agentHide(id);
      if (sidebarAgent?.id === id) setSidebarAgentId(null);
    } catch { /* ignore */ }
  }, [sidebarAgent, setSidebarAgentId]);

  const handleUnhide = useCallback(async (id: string) => {
    try { await api.agentUnhide(id); } catch { /* ignore */ }
  }, []);

  const baseCards: Record<string, React.ReactNode> = {
    agents: (
      <ScrollableCard title="Agents" icon={<Bot className="h-4 w-4" />}>
        <ProjectAgents
          project={project}
          onAgentClick={handleAgentClick}
          onHide={handleHide}
          onUnhide={handleUnhide}
        />
      </ScrollableCard>
    ),
    metrics: (
      <ScrollableCard title="Metrics" icon={<BarChart2 className="h-4 w-4" />}>
        <div className="flex h-full items-center justify-center rounded-md border border-dashed border-zinc-700">
          <p className="text-sm text-zinc-500">Grafana metrics integration coming soon</p>
        </div>
      </ScrollableCard>
    ),
    ...extraCards,
  };

  const gridLayout = layout || DEFAULT_LAYOUT;

  return (
    <>
      <div className={`space-y-4 transition-all duration-300 ${sidebarDocked && sidebarOpen ? "mr-[600px]" : ""}`}>
        <div className="flex items-center justify-between px-2">
          <div>
            <h1 className={`text-2xl font-bold ${color}`}>{project.toUpperCase()}</h1>
            <p className="text-sm text-zinc-500">{description}</p>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="border-zinc-700 text-zinc-300 hover:bg-zinc-800">
                <MoreVertical className="mr-2 h-4 w-4" /> Links
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-64 bg-zinc-900 border-zinc-700">
              {Object.entries(links).map(([category, items]) => (
                <div key={category}>
                  <DropdownMenuLabel className="text-xs uppercase text-zinc-500">{category}</DropdownMenuLabel>
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

        <DashboardGrid page={project} cards={baseCards} defaultLayout={gridLayout} />
        {children}
      </div>

      <ChatSidebar
        agent={sidebarAgent}
        open={sidebarOpen}
        docked={sidebarDocked}
        onOpenChange={handleSidebarClose}
        onDockedChange={setSidebarDocked}
        onHide={handleHide}
      />
    </>
  );
}
