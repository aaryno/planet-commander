"use client";

import { useCallback, useEffect, useState, Fragment } from "react";
import {
  BarChart2, Bot, CheckSquare, ExternalLink, GitBranch, GitPullRequest,
  Layout, MessageCircle, MoreVertical, Rocket, FileText, Book, Settings,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Agent, ProjectConfig } from "@/lib/api";
import { ProjectAgents } from "@/components/agents/ProjectAgents";
import { WorkspaceCard, type Workspace } from "@/components/workspace/WorkspaceCard";
import { JiraSummary } from "@/components/cards/JiraSummary";
import { OpenMRs } from "@/components/cards/OpenMRs";
import { WXDeployments } from "@/components/cards/WXDeployments";
import { DashboardGrid } from "@/components/layout/DashboardGrid";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { LayoutItem } from "react-grid-layout";
import { useUrlArrayParam } from "@/lib/use-url-state";
import { Panel, Group, Separator } from "react-resizable-panels";

const ICON_MAP: Record<string, React.ReactNode> = {
  "git-branch": <GitBranch className="h-3.5 w-3.5" />,
  "message-circle": <MessageCircle className="h-3.5 w-3.5" />,
  "bar-chart": <BarChart2 className="h-3.5 w-3.5" />,
  layout: <Layout className="h-3.5 w-3.5" />,
  "file-text": <FileText className="h-3.5 w-3.5" />,
  book: <Book className="h-3.5 w-3.5" />,
  "check-square": <CheckSquare className="h-3.5 w-3.5" />,
  "rocket": <Rocket className="h-3.5 w-3.5" />,
};

function buildCards(
  project: ProjectConfig,
  onJiraClick: (key: string) => void,
  onAgentClick: (agent: Agent) => void,
  onAgentHide: (id: string) => void,
): { cards: Record<string, React.ReactNode>; layout: LayoutItem[] } {
  const cards: Record<string, React.ReactNode> = {};
  const layout: LayoutItem[] = [];
  let row = 0;

  if (project.jira_project_keys.length > 0) {
    cards.jira = (
      <JiraSummary
        hideProjectFilter={true}
        onTicketClick={onJiraClick}
        urlPrefix={`${project.key}.jira`}
        jiraProjectKeys={project.jira_project_keys}
      />
    );
    layout.push({ i: "jira", x: 0, y: row, w: 6, h: 6, minW: 4, minH: 3 });
  }

  if (project.repositories.length > 0) {
    cards.mrs = <OpenMRs hideProjectFilter={true} hideProjectColumn={true} projectKey={project.key} />;
    layout.push({ i: "mrs", x: 6, y: row, w: 6, h: 6, minW: 4, minH: 3 });
    if (!cards.jira) {
      const last = layout[layout.length - 1];
      last.x = 0;
      last.w = 12;
    }
  }

  if (cards.jira || cards.mrs) row += 6;

  cards.agents = (
    <ProjectAgents
      project={project.key}
      onAgentClick={onAgentClick}
      onHide={onAgentHide}
    />
  );
  layout.push({ i: "agents", x: 0, y: row, w: 6, h: 5, minW: 3, minH: 3 });

  const rightCards: { key: string; node: React.ReactNode }[] = [];

  if (project.deployment_config) {
    rightCards.push({ key: "deploy", node: <WXDeployments /> });
  }

  if (project.grafana_dashboards.length > 0) {
    rightCards.push({
      key: "monitoring",
      node: (
        <ScrollableCard title="Monitoring" icon={<BarChart2 className="h-4 w-4" />}>
          <div className="space-y-2 p-2">
            {project.grafana_dashboards.map((d, i) => (
              <a
                key={i}
                href={d.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-zinc-800 text-sm text-zinc-300"
              >
                <BarChart2 className="h-3.5 w-3.5 text-zinc-500" />
                {d.name}
                <ExternalLink className="h-3 w-3 text-zinc-600 ml-auto" />
              </a>
            ))}
          </div>
        </ScrollableCard>
      ),
    });
  }

  if (rightCards.length > 0) {
    for (const rc of rightCards) {
      cards[rc.key] = rc.node;
      layout.push({ i: rc.key, x: 6, y: row, w: 6, h: 5, minW: 3, minH: 3 });
      row += 5;
    }
  } else {
    const agentsLayout = layout.find(l => l.i === "agents");
    if (agentsLayout) { agentsLayout.w = 12; }
  }

  return { cards, layout };
}

function ProjectLinks({ project }: { project: ProjectConfig }) {
  const categorized: Record<string, typeof project.links> = {};
  for (const link of project.links) {
    const cat = link.category || "other";
    (categorized[cat] ??= []).push(link);
  }

  if (Object.keys(categorized).length === 0) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="border-zinc-700 text-zinc-300 hover:bg-zinc-800">
          <MoreVertical className="mr-2 h-4 w-4" /> Links
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64 bg-zinc-900 border-zinc-700">
        {Object.entries(categorized).map(([category, items]) => (
          <div key={category}>
            <DropdownMenuLabel className="text-xs uppercase text-zinc-500">{category}</DropdownMenuLabel>
            {items.map((item, i) => (
              <DropdownMenuItem key={i} asChild className="text-zinc-300 focus:bg-zinc-800">
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2">
                  {ICON_MAP[item.icon || ""] || null}
                  {item.label}
                </a>
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator className="bg-zinc-800" />
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

interface ProjectDashboardProps {
  projectKey: string;
}

export function ProjectDashboard({ projectKey }: ProjectDashboardProps) {
  const [project, setProject] = useState<ProjectConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openWorkspaceIds, setOpenWorkspaceIds] = useUrlArrayParam("open", []);
  const [openWorkspaces, setOpenWorkspaces] = useState<Workspace[]>([]);

  useEffect(() => {
    api.getProject(projectKey)
      .then(setProject)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [projectKey]);

  useEffect(() => {
    setOpenWorkspaces(prev => {
      if (openWorkspaceIds.length === 0) return prev.length === 0 ? prev : [];
      return prev.filter(w => openWorkspaceIds.includes(w.id));
    });
  }, [openWorkspaceIds]);

  const handleCloseWorkspace = useCallback((workspaceId: string) => {
    setOpenWorkspaceIds(openWorkspaceIds.filter(id => id !== workspaceId));
    setOpenWorkspaces(prev => prev.filter(w => w.id !== workspaceId));
  }, [openWorkspaceIds, setOpenWorkspaceIds]);

  const handleAgentClick = useCallback((agent: Agent) => {
    setOpenWorkspaces(prev => {
      if (prev.some(w => w.id === agent.id)) return prev;
      const next = [...prev, { type: "agent" as const, agent, id: agent.id }];
      setOpenWorkspaceIds(next.map(w => w.id));
      return next;
    });
  }, [setOpenWorkspaceIds]);

  const handleJiraClick = useCallback((jiraKey: string) => {
    if (!project) return;
    const id = `jira-${jiraKey}`;
    setOpenWorkspaces(prev => {
      if (prev.some(w => w.id === id)) return prev;
      const next = [...prev, { type: "jira" as const, jiraKey, project: project.key, id }];
      setOpenWorkspaceIds(next.map(w => w.id));
      return next;
    });
  }, [project, setOpenWorkspaceIds]);

  const handleAgentHide = useCallback(async (id: string) => {
    await api.agentHide(id);
    handleCloseWorkspace(id);
  }, [handleCloseWorkspace]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-zinc-500">
        Loading project...
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-2">
        <p className="text-red-400">{error || "Project not found"}</p>
        <Link href="/">
          <Button variant="outline" size="sm" className="border-zinc-700 text-zinc-300">
            Back to Dashboard
          </Button>
        </Link>
      </div>
    );
  }

  const { cards, layout } = buildCards(project, handleJiraClick, handleAgentClick, handleAgentHide);

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between px-6 py-3">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: project.color }}>
            {project.name}
          </h1>
          {project.description && (
            <p className="text-sm text-zinc-500">{project.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <ProjectLinks project={project} />
          <Link href={`/projects/${project.key}/settings`}>
            <Button variant="ghost" size="sm" className="text-zinc-500 hover:text-zinc-300">
              <Settings className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      </div>

      {/* Content: grid + workspace sidebar */}
      <Group orientation="horizontal" className="flex-1">
        <Panel defaultSize={openWorkspaces.length > 0 ? 60 : 100} minSize={30}>
          <div className="h-full w-full overflow-auto">
            <DashboardGrid page={project.key} cards={cards} defaultLayout={layout} />
          </div>
        </Panel>

        {openWorkspaces.length > 0 && (
          <>
            <Separator className="w-2 bg-zinc-800 hover:bg-zinc-600 transition-colors cursor-col-resize" />
            <Panel defaultSize={40} minSize={25}>
              <div className="h-full py-6 pr-6">
                <Group orientation="vertical">
                  {openWorkspaces.map((workspace, index) => (
                    <Fragment key={workspace.id}>
                      <Panel defaultSize={100 / openWorkspaces.length} minSize={15}>
                        <div className={`h-full ${index < openWorkspaces.length - 1 ? 'pb-3' : ''}`}>
                          <WorkspaceCard
                            workspace={workspace}
                            onClose={() => handleCloseWorkspace(workspace.id)}
                            onHide={handleAgentHide}
                            onOpenAgent={handleAgentClick}
                          />
                        </div>
                      </Panel>
                      {index < openWorkspaces.length - 1 && (
                        <Separator className="h-0.5 bg-transparent hover:bg-zinc-600 transition-colors cursor-row-resize my-3" />
                      )}
                    </Fragment>
                  ))}
                </Group>
              </div>
            </Panel>
          </>
        )}
      </Group>
    </div>
  );
}
