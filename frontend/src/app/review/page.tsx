"use client";

import { useState, useCallback, useEffect } from "react";
import { Panel, Group, Separator } from "react-resizable-panels";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";
import type { DetailedMR } from "@/lib/api";
import { MRListRail } from "@/components/review/MRListRail";
import { MRCenterPane } from "@/components/review/MRCenterPane";
import { MRAgentPane } from "@/components/review/MRAgentPane";
import { extractJiraKey } from "@/lib/utils";

export interface ReviewContext {
  selectedMr: DetailedMR | null;
  selectedMrId: string | null;
  selectedTab: "diff" | "comments" | "pipeline";
  selectedFile: string | null;
  jiraKey: string | null;
}

export default function ReviewPage() {
  const [ctx, setCtx] = useState<ReviewContext>({
    selectedMr: null,
    selectedMrId: null,
    selectedTab: "diff",
    selectedFile: null,
    jiraKey: null,
  });
  const [agentMaximized, setAgentMaximized] = useState(false);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);

  const fetcher = useCallback(() => api.mrs(), []);
  const { data, loading, refresh } = usePoll(fetcher, 120_000);
  const allMrs: DetailedMR[] = data?.mrs ?? [];

  const selectMr = useCallback((mr: DetailedMR) => {
    setCtx(prev => ({
      ...prev,
      selectedMr: mr,
      selectedMrId: `${mr.project}-${mr.iid}`,
      selectedTab: "diff",
      selectedFile: null,
      jiraKey: extractJiraKey(mr.title, mr.branch),
    }));
  }, []);

  const navigate = useCallback((direction: 1 | -1) => {
    if (!ctx.selectedMrId || allMrs.length === 0) return;
    const idx = allMrs.findIndex(mr => `${mr.project}-${mr.iid}` === ctx.selectedMrId);
    const next = allMrs[idx + direction];
    if (next) selectMr(next);
  }, [ctx.selectedMrId, allMrs, selectMr]);

  const setTab = useCallback((tab: "diff" | "comments" | "pipeline") => {
    setCtx(prev => ({ ...prev, selectedTab: tab }));
  }, []);

  const setFile = useCallback((file: string | null) => {
    setCtx(prev => ({ ...prev, selectedFile: file }));
  }, []);

  // Auto-select MR from URL param (?mr=project-iid) or first MR
  useEffect(() => {
    if (ctx.selectedMr || allMrs.length === 0) return;
    const params = new URLSearchParams(window.location.search);
    const mrParam = params.get("mr");
    if (mrParam) {
      const target = allMrs.find(mr => `${mr.project}-${mr.iid}` === mrParam);
      if (target) { selectMr(target); return; }
    }
    selectMr(allMrs[0]);
  }, [allMrs, ctx.selectedMr, selectMr]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "j") navigate(1);
      if (e.key === "k") navigate(-1);
      if (e.key === "Escape" && agentMaximized) setAgentMaximized(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [navigate, agentMaximized]);

  const handleAddToReview = useCallback((context: string) => {
    setPendingPrompt(context);
  }, []);

  // Send to Agent Multi-View
  const handleSendToMultiView = useCallback(() => {
    if (!ctx.selectedMr) return;
    // Store agent context in sessionStorage for AMV to pick up
    const existing = JSON.parse(sessionStorage.getItem("amv-agents") || "[]");
    const newAgent = {
      id: `review-${ctx.selectedMr.project}-${ctx.selectedMr.iid}`,
      title: `Review !${ctx.selectedMr.iid}: ${ctx.selectedMr.title}`,
      project: ctx.selectedMr.project,
      mrIid: ctx.selectedMr.iid,
      jiraKey: ctx.jiraKey,
      color: "#3b82f6",
      createdAt: new Date().toISOString(),
    };
    if (!existing.find((a: any) => a.id === newAgent.id)) {
      existing.push(newAgent);
      sessionStorage.setItem("amv-agents", JSON.stringify(existing));
    }
    window.open("/multiview", "_blank");
  }, [ctx.selectedMr, ctx.jiraKey]);

  return (
    <div className="h-full flex">
      {/* Left Rail */}
      {!agentMaximized && (
        <div className="w-72 shrink-0 border-r border-zinc-800 flex flex-col overflow-hidden">
          <MRListRail
            mrs={allMrs}
            loading={loading}
            selectedId={ctx.selectedMrId}
            onSelect={selectMr}
            onRefresh={refresh}
          />
        </div>
      )}

      {/* Center + Right with resizable divider */}
      <Group orientation="horizontal" className="flex-1">
        {!agentMaximized && (
          <>
            <Panel defaultSize={60} minSize={30}>
              <div className="h-full flex flex-col overflow-hidden">
                <MRCenterPane
                  mr={ctx.selectedMr}
                  jiraKey={ctx.jiraKey}
                  selectedTab={ctx.selectedTab}
                  onTabChange={setTab}
                  onFileSelect={setFile}
                  onNavigate={navigate}
                  onAddToReview={handleAddToReview}
                />
              </div>
            </Panel>
            <Separator className="w-1.5 bg-zinc-800 hover:bg-zinc-600 active:bg-blue-500 transition-colors cursor-col-resize" />
          </>
        )}
        <Panel defaultSize={agentMaximized ? 100 : 40} minSize={25}>
          <div className="h-full flex flex-col overflow-hidden">
            <MRAgentPane
              mr={ctx.selectedMr}
              jiraKey={ctx.jiraKey}
              selectedFile={ctx.selectedFile}
              selectedTab={ctx.selectedTab}
              maximized={agentMaximized}
              onToggleMaximize={() => setAgentMaximized(!agentMaximized)}
              onSendToMultiView={handleSendToMultiView}
              pendingPrompt={pendingPrompt}
              onPromptConsumed={() => setPendingPrompt(null)}
            />
          </div>
        </Panel>
      </Group>
    </div>
  );
}
