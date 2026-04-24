"use client";

import { useState, useCallback } from "react";
import {  FileText, MessageSquare, GitBranch, Rocket, LayoutGrid } from "lucide-react";
import type { WorkspaceDetail, Agent } from "@/lib/api";
import { OverviewTab } from "./tabs/OverviewTab";
import { JiraTab } from "./tabs/JiraTab";
import { ChatsTab } from "./tabs/ChatsTab";
import { CodeTab } from "./tabs/CodeTab";
import { DeploymentsTab } from "./tabs/DeploymentsTab";

export type TabId = "overview" | "jira" | "chats" | "code" | "deployments";

interface Tab {
  id: TabId;
  label: string;
  icon: React.ReactNode;
  count?: number;
}

interface WorkspaceTabsProps {
  workspace: WorkspaceDetail;
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  onUpdate?: (workspace: WorkspaceDetail) => void;
  onOpenAgent?: (agent: Agent) => void;
}

export function WorkspaceTabs({
  workspace,
  activeTab,
  onTabChange,
  onUpdate,
  onOpenAgent,
}: WorkspaceTabsProps) {
  const tabs: Tab[] = [
    {
      id: "overview",
      label: "Overview",
      icon: <LayoutGrid className="h-3.5 w-3.5" />,
    },
    {
      id: "jira",
      label: "JIRA",
      icon: <FileText className="h-3.5 w-3.5" />,
      count: workspace.jira_tickets.length,
    },
    {
      id: "chats",
      label: "Chats",
      icon: <MessageSquare className="h-3.5 w-3.5" />,
      count: workspace.agents.length,
    },
    {
      id: "code",
      label: "Code",
      icon: <GitBranch className="h-3.5 w-3.5" />,
      count: workspace.branches.length + workspace.merge_requests.length,
    },
    {
      id: "deployments",
      label: "Deployments",
      icon: <Rocket className="h-3.5 w-3.5" />,
      count: workspace.deployments.length,
    },
  ];

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Tab Navigation */}
      <div className="flex items-center gap-1 px-3 py-2 border-b border-zinc-800 bg-zinc-900/50 shrink-0">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`
              flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors
              ${
                activeTab === tab.id
                  ? "bg-zinc-800 text-zinc-200"
                  : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"
              }
            `}
          >
            {tab.icon}
            <span>{tab.label}</span>
            {tab.count !== undefined && tab.count > 0 && (
              <span className="text-[10px] text-zinc-500">({tab.count})</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === "overview" && (
          <OverviewTab
            workspace={workspace}
            onUpdate={onUpdate}
            onOpenAgent={onOpenAgent}
            onTabChange={onTabChange}
          />
        )}
        {activeTab === "jira" && (
          <JiraTab
            workspace={workspace}
            onUpdate={onUpdate}
          />
        )}
        {activeTab === "chats" && (
          <ChatsTab
            workspace={workspace}
            onUpdate={onUpdate}
            onOpenAgent={onOpenAgent}
          />
        )}
        {activeTab === "code" && (
          <CodeTab
            workspace={workspace}
            onUpdate={onUpdate}
          />
        )}
        {activeTab === "deployments" && (
          <DeploymentsTab
            workspace={workspace}
            onUpdate={onUpdate}
          />
        )}
      </div>
    </div>
  );
}
