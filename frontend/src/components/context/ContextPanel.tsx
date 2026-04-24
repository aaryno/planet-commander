"use client";

import { useCallback, useState } from "react";
import { usePoll } from "@/lib/polling";
import { api, ContextResponse } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ContextHeader } from "./ContextHeader";
import { RelationshipList } from "./RelationshipList";
import { V2DocsPanel } from "./V2DocsPanel";
import { PagerDutyIncidentCard } from "@/components/pagerduty/PagerDutyIncidentCard";
import { AlertDefinitionCard } from "@/components/grafana/AlertDefinitionCard";
import { ArtifactCard } from "@/components/artifacts/ArtifactCard";
import { GitLabMRCard } from "@/components/gitlab/GitLabMRCard";
import { CTABar, ReadinessRadar, ChangeRiskGauge, FindingsList } from "@/components/audit";
import { FileText, Link as LinkIcon, MessageSquare, RefreshCw, AlertCircle, BellRing, Archive, GitMerge, BookOpen, Shield } from "lucide-react";

interface ContextPanelProps {
  contextId?: string;
  jiraKey?: string;
  chatId?: string;
  branchId?: string;
  worktreeId?: string;
  onClose?: () => void;
}

export function ContextPanel({
  contextId,
  jiraKey,
  chatId,
  branchId,
  worktreeId,
  onClose,
}: ContextPanelProps) {
  const [activeTab, setActiveTab] = useState("overview");

  // Fetch context based on which prop is provided
  const fetcher = useCallback(async () => {
    if (contextId) return api.contextById(contextId);
    if (jiraKey) return api.contextByJiraKey(jiraKey);
    if (chatId) return api.contextByChatId(chatId);
    if (branchId) return api.contextByBranchId(branchId);
    if (worktreeId) return api.contextByWorktreeId(worktreeId);
    throw new Error("No context identifier provided");
  }, [contextId, jiraKey, chatId, branchId, worktreeId]);

  const { data: context, loading, error, refresh } = usePoll<ContextResponse>(
    fetcher,
    300_000 // 5 minutes
  );

  const menuItems = [
    { label: "Refresh", onClick: refresh },
    ...(onClose ? [{ label: "Close", onClick: onClose }] : []),
  ];

  return (
    <ScrollableCard
      title={context?.title || "Loading Context..."}
      icon={<FileText className="w-4 h-4" />}
      menuItems={menuItems}
      stickyHeader={
        context ? (
          <ContextHeader
            context={context}
            onTitleUpdate={(newTitle) => {
              // TODO: Implement title update API
              console.log("Update title:", newTitle);
            }}
          />
        ) : undefined
      }
    >
      {loading && !context && (
        <div className="flex items-center justify-center py-8">
          <RefreshCw className="w-4 h-4 animate-spin mr-2" />
          <span className="text-sm text-zinc-400">Loading context...</span>
        </div>
      )}

      {error && (
        <div className="p-4 rounded border border-red-800 bg-red-900/20">
          <p className="text-sm text-red-400">Failed to load context</p>
          <p className="text-xs text-red-500 mt-1">{error.message}</p>
          <Button variant="outline" size="sm" onClick={refresh} className="mt-2">
            Retry
          </Button>
        </div>
      )}

      {context && (
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="w-full bg-zinc-900 border-b border-zinc-800">
            <TabsTrigger value="overview" className="flex-1">
              <FileText className="w-3 h-3 mr-1" />
              Overview
            </TabsTrigger>
            {context.v2_docs && (
              <TabsTrigger value="context-docs" className="flex-1">
                <BookOpen className="w-3 h-3 mr-1" />
                Context ({context.v2_docs.layers.length})
              </TabsTrigger>
            )}
            <TabsTrigger value="entities" className="flex-1">
              <LinkIcon className="w-3 h-3 mr-1" />
              Linked Entities ({context.links.length})
            </TabsTrigger>
            <TabsTrigger value="pagerduty" className="flex-1">
              <AlertCircle className="w-3 h-3 mr-1" />
              Incidents ({context.pagerduty_incidents.length})
            </TabsTrigger>
            <TabsTrigger value="alerts" className="flex-1">
              <BellRing className="w-3 h-3 mr-1" />
              Alerts ({context.grafana_alerts.length})
            </TabsTrigger>
            <TabsTrigger value="artifacts" className="flex-1">
              <Archive className="w-3 h-3 mr-1" />
              Artifacts ({context.artifacts.length})
            </TabsTrigger>
            <TabsTrigger value="mrs" className="flex-1">
              <GitMerge className="w-3 h-3 mr-1" />
              MRs ({context.merge_requests.length})
            </TabsTrigger>
            {context.audit_runs.length > 0 && (
              <TabsTrigger value="audit" className="flex-1">
                <Shield className="w-3 h-3 mr-1" />
                Audit
                {context.findings_summary && context.findings_summary.total > 0 && (
                  <Badge variant="secondary" className="ml-1 text-[10px] px-1 py-0">
                    {context.findings_summary.total}
                  </Badge>
                )}
              </TabsTrigger>
            )}
            <TabsTrigger value="chats" className="flex-1">
              <MessageSquare className="w-3 h-3 mr-1" />
              Chats ({context.chats.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-4 space-y-4">
            {/* Summary */}
            {context.summary_text && (
              <div className="p-3 rounded border border-zinc-800 bg-zinc-900/50">
                <h3 className="text-xs font-semibold text-zinc-400 mb-2">Summary</h3>
                <p className="text-sm text-zinc-200">{context.summary_text}</p>
              </div>
            )}

            {/* JIRA Issues */}
            {context.jira_issues.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-zinc-400">JIRA Issues</h3>
                {context.jira_issues.map((issue) => (
                  <div
                    key={issue.id}
                    className="p-3 rounded border border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800/50 transition-colors"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <a
                            href={issue.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm font-mono text-blue-400 hover:text-blue-300"
                          >
                            {issue.external_key}
                          </a>
                          <Badge variant="outline">{issue.status}</Badge>
                          {issue.priority && (
                            <Badge variant="secondary">{issue.priority}</Badge>
                          )}
                        </div>
                        <p className="text-sm text-zinc-200 mt-1 truncate">
                          {issue.title}
                        </p>
                        {issue.assignee && (
                          <p className="text-xs text-zinc-500 mt-1">
                            Assignee: {issue.assignee}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Branches */}
            {context.branches.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-zinc-400">Git Branches</h3>
                {context.branches.map((branch) => (
                  <div
                    key={branch.id}
                    className="p-3 rounded border border-zinc-800 bg-zinc-900/50"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono text-zinc-200 truncate">
                            {branch.branch_name}
                          </span>
                          <Badge variant="outline">{branch.status}</Badge>
                          {branch.has_open_pr && (
                            <Badge variant="secondary">PR Open</Badge>
                          )}
                        </div>
                        <p className="text-xs text-zinc-500 mt-1">
                          {branch.repo}
                          {branch.ahead_count !== null &&
                            ` • ${branch.ahead_count} ahead, ${branch.behind_count} behind`}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Worktrees */}
            {context.worktrees.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-zinc-400">Worktrees</h3>
                {context.worktrees.map((wt) => (
                  <div
                    key={wt.id}
                    className="p-3 rounded border border-zinc-800 bg-zinc-900/50"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono text-zinc-200 truncate">
                            {wt.path}
                          </span>
                          <Badge variant={wt.status === "clean" ? "outline" : "destructive"}>
                            {wt.status}
                          </Badge>
                          {wt.is_active && (
                            <Badge variant="secondary">Active</Badge>
                          )}
                        </div>
                        <p className="text-xs text-zinc-500 mt-1">
                          {wt.repo}
                          {wt.has_uncommitted_changes && " • Uncommitted changes"}
                          {wt.has_untracked_files && " • Untracked files"}
                          {wt.is_rebasing && " • Rebasing"}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* PagerDuty Incidents */}
            {context.pagerduty_incidents.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-zinc-400">PagerDuty Incidents</h3>
                {context.pagerduty_incidents.map((incident) => (
                  <PagerDutyIncidentCard key={incident.id} incident={incident} />
                ))}
              </div>
            )}

            {/* Grafana Alerts */}
            {context.grafana_alerts.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-zinc-400">Grafana Alerts</h3>
                {context.grafana_alerts.map((alert) => (
                  <AlertDefinitionCard key={alert.id} alert={alert} />
                ))}
              </div>
            )}

            {/* Artifacts */}
            {context.artifacts.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-zinc-400">Artifacts</h3>
                {context.artifacts.map((artifact) => (
                  <ArtifactCard key={artifact.id} artifact={artifact} />
                ))}
              </div>
            )}

            {/* Merge Requests */}
            {context.merge_requests.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-zinc-400">Merge Requests</h3>
                {context.merge_requests.map((mr) => (
                  <GitLabMRCard key={mr.id} mr={mr as any} />
                ))}
              </div>
            )}

            {/* Audit Summary */}
            {context.audit_runs.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-zinc-400">Audit Summary</h3>
                <div className="p-3 rounded border border-zinc-800 bg-zinc-900/50">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="outline" className="text-xs">
                      {context.audit_runs.length} run{context.audit_runs.length !== 1 ? "s" : ""}
                    </Badge>
                    {context.findings_summary && (
                      <>
                        {context.findings_summary.errors > 0 && (
                          <Badge className="text-xs border-0 bg-red-500/20 text-red-400">
                            {context.findings_summary.errors} error{context.findings_summary.errors !== 1 ? "s" : ""}
                          </Badge>
                        )}
                        {context.findings_summary.warnings > 0 && (
                          <Badge className="text-xs border-0 bg-amber-500/20 text-amber-400">
                            {context.findings_summary.warnings} warning{context.findings_summary.warnings !== 1 ? "s" : ""}
                          </Badge>
                        )}
                        {context.findings_summary.blocking > 0 && (
                          <Badge className="text-xs border-0 bg-red-500/20 text-red-400">
                            {context.findings_summary.blocking} blocking
                          </Badge>
                        )}
                      </>
                    )}
                    {context.audit_runs[0] && (
                      <Badge
                        variant="outline"
                        className={`text-xs ${
                          context.audit_runs[0].verdict === "approved"
                            ? "text-emerald-400 border-emerald-500/30"
                            : context.audit_runs[0].verdict === "blocked"
                              ? "text-red-400 border-red-500/30"
                              : "text-amber-400 border-amber-500/30"
                        }`}
                      >
                        {context.audit_runs[0].verdict}
                      </Badge>
                    )}
                  </div>
                </div>
              </div>
            )}
          </TabsContent>

          {/* v2 Context Docs Tab */}
          {context.v2_docs && (
            <TabsContent value="context-docs" className="mt-4">
              <V2DocsPanel v2Docs={context.v2_docs} />
            </TabsContent>
          )}

          <TabsContent value="entities" className="mt-4">
            <RelationshipList
              context={context}
              onLinkCreate={(request) => {
                // TODO: Implement link creation
                console.log("Create link:", request);
              }}
              onLinkConfirm={(linkId) => {
                // TODO: Implement link confirmation
                console.log("Confirm link:", linkId);
              }}
              onLinkReject={(linkId) => {
                // TODO: Implement link rejection
                console.log("Reject link:", linkId);
              }}
            />
          </TabsContent>

          <TabsContent value="pagerduty" className="mt-4 space-y-2">
            {context.pagerduty_incidents.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center py-8">
                No PagerDuty incidents linked to this context
              </p>
            ) : (
              context.pagerduty_incidents.map((incident) => (
                <PagerDutyIncidentCard key={incident.id} incident={incident} />
              ))
            )}
          </TabsContent>

          <TabsContent value="alerts" className="mt-4 space-y-2">
            {context.grafana_alerts.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center py-8">
                No Grafana alerts linked to this context
              </p>
            ) : (
              context.grafana_alerts.map((alert) => (
                <AlertDefinitionCard key={alert.id} alert={alert} />
              ))
            )}
          </TabsContent>

          <TabsContent value="artifacts" className="mt-4 space-y-2">
            {context.artifacts.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center py-8">
                No artifacts linked to this context
              </p>
            ) : (
              context.artifacts.map((artifact) => (
                <ArtifactCard key={artifact.id} artifact={artifact} />
              ))
            )}
          </TabsContent>

          <TabsContent value="mrs" className="mt-4 space-y-2">
            {context.merge_requests.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center py-8">
                No merge requests linked to this context
              </p>
            ) : (
              context.merge_requests.map((mr) => (
                <GitLabMRCard key={mr.id} mr={mr as any} />
              ))
            )}
          </TabsContent>

          {context.audit_runs.length > 0 && (
            <TabsContent value="audit" className="mt-4 space-y-4">
              {/* CTA Bar - from latest audit run's findings */}
              {context.findings_summary && (
                <CTABar
                  cta={{
                    label: context.findings_summary.blocking > 0
                      ? `${context.findings_summary.blocking} Blocking`
                      : context.findings_summary.total === 0
                        ? "All Clear"
                        : `${context.findings_summary.total} Finding${context.findings_summary.total !== 1 ? "s" : ""}`,
                    action: context.findings_summary.blocking > 0
                      ? "guide-me"
                      : context.findings_summary.auto_fixable > 0
                        ? "fix-it"
                        : context.findings_summary.total === 0
                          ? "ready"
                          : "re-analyze",
                    subtext: context.findings_summary.auto_fixable > 0
                      ? `${context.findings_summary.auto_fixable} auto-fixable`
                      : context.findings_summary.total === 0
                        ? "No findings"
                        : `${context.findings_summary.errors} errors, ${context.findings_summary.warnings} warnings`,
                    style: context.findings_summary.blocking > 0
                      ? "primary-amber"
                      : context.findings_summary.total === 0
                        ? "primary-green"
                        : context.findings_summary.auto_fixable > 0
                          ? "primary-blue"
                          : "primary-default",
                    secondary_actions: [
                      { label: "Re-analyze", action: "re-analyze" },
                    ],
                  }}
                  onAction={(action) => {
                    console.log("Audit CTA action:", action);
                  }}
                />
              )}

              {/* Readiness Radar - if any run has dimension_scores */}
              {context.audit_runs.some((r) => r.dimension_scores) && (() => {
                const runWithScores = context.audit_runs.find((r) => r.dimension_scores);
                return runWithScores?.dimension_scores ? (
                  <ReadinessRadar dimensionScores={runWithScores.dimension_scores} />
                ) : null;
              })()}

              {/* Change Risk Gauge - if any run has risk_score */}
              {context.audit_runs.some((r) => r.risk_score !== null) && (() => {
                const runWithRisk = context.audit_runs.find((r) => r.risk_score !== null);
                return runWithRisk && runWithRisk.risk_score !== null ? (
                  <ChangeRiskGauge
                    score={runWithRisk.risk_score}
                    level={
                      runWithRisk.risk_score >= 0.7
                        ? "high"
                        : runWithRisk.risk_score >= 0.4
                          ? "medium"
                          : "low"
                    }
                    factors={[]}
                  />
                ) : null;
              })()}

              {/* Findings List */}
              {context.findings_summary && context.findings_summary.total > 0 ? (
                <FindingsList
                  findings={[]}
                  title="Findings"
                  embedded
                />
              ) : (
                <p className="text-sm text-zinc-500 text-center py-4">
                  No findings from audit runs
                </p>
              )}

              {/* Audit Run history */}
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-zinc-400">Audit Runs</h3>
                {context.audit_runs.map((run) => (
                  <div
                    key={run.id}
                    className="p-3 rounded border border-zinc-800 bg-zinc-900/50"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Shield className="w-3 h-3 text-zinc-400" />
                        <span className="text-sm text-zinc-200">{run.family}</span>
                        <Badge
                          variant="outline"
                          className={`text-xs ${
                            run.verdict === "approved"
                              ? "text-emerald-400 border-emerald-500/30"
                              : run.verdict === "blocked"
                                ? "text-red-400 border-red-500/30"
                                : "text-amber-400 border-amber-500/30"
                          }`}
                        >
                          {run.verdict}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-zinc-500">
                        <span>{run.finding_count} finding{run.finding_count !== 1 ? "s" : ""}</span>
                        {run.blocking_count > 0 && (
                          <Badge className="text-[10px] border-0 bg-red-500/20 text-red-400 px-1 py-0">
                            {run.blocking_count} blocking
                          </Badge>
                        )}
                        <span>{new Date(run.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </TabsContent>
          )}

          <TabsContent value="chats" className="mt-4 space-y-2">
            {context.chats.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center py-8">
                No chats linked to this context
              </p>
            ) : (
              context.chats.map((chat) => (
                <div
                  key={chat.id}
                  className="p-3 rounded border border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800/50 transition-colors cursor-pointer"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-zinc-200">
                          {chat.title || "Untitled Chat"}
                        </span>
                        <Badge variant="outline">{chat.status}</Badge>
                        {chat.project && (
                          <Badge variant="secondary">{chat.project}</Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
                        <span>{chat.message_count} messages</span>
                        {chat.jira_key && (
                          <span className="font-mono">{chat.jira_key}</span>
                        )}
                        {chat.last_active_at && (
                          <span>
                            Last active:{" "}
                            {new Date(chat.last_active_at).toLocaleString()}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </TabsContent>
        </Tabs>
      )}
    </ScrollableCard>
  );
}
