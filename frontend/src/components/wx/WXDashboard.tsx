"use client";

import { useCallback, useState, useEffect, Fragment } from "react";
import { CheckSquare, GitPullRequest, Rocket } from "lucide-react";
import { api } from "@/lib/api";
import { ProjectAgents } from "@/components/agents/ProjectAgents";
import { WorkspaceCard, type Workspace } from "@/components/workspace/WorkspaceCard";
import { JiraSummary } from "@/components/cards/JiraSummary";
import { OpenMRs } from "@/components/cards/OpenMRs";
import { WXDeployments } from "@/components/cards/WXDeployments";
import { DashboardGrid } from "@/components/layout/DashboardGrid";
import type { LayoutItem } from "react-grid-layout";
import type { Agent } from "@/lib/api";
import { useUrlArrayParam } from "@/lib/use-url-state";
import { Panel, Group, Separator } from "react-resizable-panels";

const DEFAULT_LAYOUT: LayoutItem[] = [
  { i: "jira",    x: 0, y: 0, w: 6, h: 6, minW: 4, minH: 3 },
  { i: "mrs",     x: 6, y: 0, w: 6, h: 6, minW: 4, minH: 3 },
  { i: "agents",  x: 0, y: 6, w: 6, h: 5, minW: 3, minH: 3 },
  { i: "deploy",  x: 6, y: 6, w: 6, h: 5, minW: 3, minH: 3 },
];

export function WXDashboard() {
  const [openWorkspaceIds, setOpenWorkspaceIds] = useUrlArrayParam("open", []);
  const [openWorkspaces, setOpenWorkspaces] = useState<Workspace[]>([]);

  // Sync openWorkspaces when openWorkspaceIds changes — remove workspaces
  // whose IDs were removed from the URL. Never ADD workspaces here (that's
  // done by the click handlers which create the workspace objects).
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
    const id = `jira-${jiraKey}`;
    setOpenWorkspaces(prev => {
      if (prev.some(w => w.id === id)) return prev;
      const next = [...prev, { type: "jira" as const, jiraKey, project: "wx", id }];
      setOpenWorkspaceIds(next.map(w => w.id));
      return next;
    });
  }, [setOpenWorkspaceIds]);

  const handleAgentHide = useCallback(async (id: string) => {
    await api.agentHide(id);
    handleCloseWorkspace(id);
  }, [handleCloseWorkspace]);

  const cards: Record<string, React.ReactNode> = {
    jira: <JiraSummary hideProjectFilter={true} onTicketClick={handleJiraClick} urlPrefix="wx.jira" />,
    mrs: <OpenMRs hideProjectFilter={true} hideProjectColumn={true} />,
    agents: (
      <ProjectAgents project="wx" onAgentClick={handleAgentClick} onHide={handleAgentHide} />
    ),
    deploy: <WXDeployments />,
  };

  return (
    <div className="h-full flex flex-col">
      <Group orientation="horizontal" className="flex-1">
        <Panel defaultSize={openWorkspaces.length > 0 ? 60 : 100} minSize={30}>
          <div className="h-full w-full overflow-auto">
            <DashboardGrid page="wx" cards={cards} defaultLayout={DEFAULT_LAYOUT} />
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
