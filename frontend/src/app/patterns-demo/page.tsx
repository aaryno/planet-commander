"use client";

import { SuggestedPatterns } from "@/components/patterns";

// Sample pattern data (from test results)
const samplePatterns = [
  {
    title: "G4c Sub 04 Api Availability Incident - Alert Correlation",
    pattern_type: "alert_correlation",
    confidence: 1.0,
    similarity_score: 0.75,
    combined_score: 0.82,
    matched_keywords: ["alert", "api", "availability"],
    relevance:
      "Keywords: alert, api, availability | Type: Alert Correlation | Systems: g4-api, grafana | High confidence",
    trigger: "Correlating alerts across multiple systems",
    approach: `1. Check Grafana dashboards for API error rate
2. Review error logs in Loki
3. Check database connection status
4. Verify pod health and resource limits
5. Correlate timing with deployment events`,
    source_artifact:
      "~/claude/projects/g4-notes/artifacts/20260108-1547-g4c-sub-04-api-availability-incident.md",
  },
  {
    title: "Cloud Logging Findings - Root Cause",
    pattern_type: "root_cause",
    confidence: 1.0,
    similarity_score: 0.4,
    combined_score: 0.64,
    matched_keywords: ["kubernetes", "oom"],
    relevance:
      "Keywords: kubernetes, oom | Type: Root Cause | Systems: grafana, kubernetes | High confidence",
    trigger: "Identifying root cause of production incident",
    approach: `1. Check pod memory limits and requests
2. Review memory usage metrics in Grafana
3. Identify memory leak patterns in application logs
4. Analyze OOMKilled events in pod status
5. Review cgroup memory statistics`,
    source_artifact:
      "~/claude/projects/wx-notes/artifacts/20251023-1355-comprehensive-analysis.md",
  },
  {
    title: "PagerDuty Incidents - Work Context Integration Complete",
    pattern_type: "integration",
    confidence: 1.0,
    similarity_score: 0.5,
    combined_score: 0.7,
    matched_keywords: ["pagerduty", "incidents"],
    relevance:
      "Keywords: pagerduty, incidents | Type: Integration | Systems: pagerduty, postgresql | High confidence",
    trigger: "Integrating new entity type with work context system",
    approach: `1. Update Context Resolver Service
   - Add entity import
   - Add field to ResolvedContext
   - Add fetching logic via EntityLink
2. Update Context API
   - Create response model
   - Add to ContextResponse
   - Update _build_context_response()
3. Update Frontend Types
4. Update ContextPanel Component
5. Test integration end-to-end`,
    source_artifact:
      "~/claude/artifacts/20260320-1730-pagerduty-context-integration-complete.md",
  },
  {
    title: "Cost Query Comparison - Cost Analysis",
    pattern_type: "cost_analysis",
    confidence: 0.8,
    similarity_score: 0.8,
    combined_score: 0.85,
    matched_keywords: ["cost", "bigquery", "query"],
    relevance:
      "Keywords: cost, bigquery, query | Type: Cost Analysis | Systems: bigquery, kubernetes",
    trigger: "Analyzing cost implications of technical decisions",
    approach: `1. Dry-run query to estimate data scanned
2. Calculate cost per TB scanned ($5/TB standard, $6.25/TB on-demand)
3. Compare alternative query approaches
4. Consider partitioning and clustering
5. Estimate monthly cost based on frequency
6. Document cost vs benefit trade-offs`,
    source_artifact:
      "~/claude/artifacts/20260109-1400-cost-query-comparison.md",
  },
  {
    title: "Fusion Podrunner Shutdown Analysis - Investigation",
    pattern_type: "investigation",
    confidence: 0.95,
    similarity_score: 0.4,
    combined_score: 0.64,
    matched_keywords: ["shutdown", "failures"],
    relevance:
      "Keywords: shutdown, failures | Type: Investigation | Systems: grafana, jira",
    trigger: "Investigating multi-system production issue",
    approach: `1. Gather task failure data from WX API
2. Check pod events in Kubernetes
3. Correlate with GCP spot instance preemption logs
4. Analyze timing patterns (batch submission vs failures)
5. Review scaling policy configuration
6. Calculate cost implications of spot vs regular instances`,
    source_artifact:
      "~/claude/projects/wx-notes/artifacts/20260109-1340-fusion-podrunner-shutdown-analysis.md",
  },
];

export default function PatternsDemoPage() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold mb-2">Pattern Suggestions Demo</h1>
          <p className="text-zinc-400">
            Example of how ECC surfaces relevant patterns from past investigations
          </p>
        </div>

        <div className="bg-zinc-900 rounded-lg p-4 border border-zinc-800">
          <div className="text-sm text-zinc-300 mb-2">
            <span className="font-semibold">User prompt:</span>
          </div>
          <div className="text-lg text-zinc-100 mb-4">
            "g4 api availability alert firing"
          </div>
          <div className="text-xs text-zinc-500">
            ECC automatically surfaces these patterns based on keyword matching,
            confidence scores, and recency:
          </div>
        </div>

        <SuggestedPatterns patterns={samplePatterns} />

        <div className="text-xs text-zinc-500 space-y-2">
          <div className="font-semibold text-zinc-400">How to use in your page:</div>
          <pre className="bg-zinc-900 p-3 rounded overflow-x-auto">
{`import { SuggestedPatterns } from "@/components/patterns";

// Get patterns from ECC hook result
const patterns = hookResult?.suggested_patterns || [];

// Display in your page
<SuggestedPatterns patterns={patterns} />`}
          </pre>
        </div>
      </div>
    </div>
  );
}
