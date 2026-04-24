"use client";

import { useState } from "react";
import { WarningMonitor } from "@/components/warnings/WarningMonitor";
import { StandbyContextViewer } from "@/components/warnings/StandbyContextViewer";
import { EscalationTrends } from "@/components/warnings/EscalationTrends";
import { PredictionAccuracy } from "@/components/warnings/PredictionAccuracy";
import { TopAlerts } from "@/components/warnings/TopAlerts";
import { LearningDashboard } from "@/components/warnings/LearningDashboard";
import { AccuracyTrendChart } from "@/components/warnings/AccuracyTrendChart";
import { WarningEvent } from "@/lib/api";

export default function WarningsPage() {
  const [selectedWarning, setSelectedWarning] = useState<WarningEvent | null>(null);

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">Warning Monitor</h1>
        <p className="text-sm text-zinc-400 mt-1">
          Proactive incident response - Monitor warnings, predict escalations, pre-assemble mitigation plans
        </p>
      </div>

      {/* Warning Monitor Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Left: Warning List */}
        <div>
          <WarningMonitor
            activeOnly={true}
            onSelectWarning={setSelectedWarning}
          />
        </div>

        {/* Right: Standby Context Viewer */}
        <div>
          {selectedWarning ? (
            <StandbyContextViewer warning={selectedWarning} />
          ) : (
            <div className="bg-zinc-900 rounded-lg border border-zinc-800 p-8 text-center">
              <p className="text-zinc-500 text-sm">
                Select a warning to view standby context
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Metrics Section */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-zinc-100 mb-4">
          Escalation Metrics & Trends
        </h2>
        <p className="text-sm text-zinc-400 mb-4">
          Historical data and prediction accuracy for warning escalations
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Escalation Trends Chart */}
        <div>
          <EscalationTrends days={7} />
        </div>

        {/* Prediction Accuracy */}
        <div>
          <PredictionAccuracy days={30} />
        </div>

        {/* Top Alerts by Escalation Rate */}
        <div>
          <TopAlerts limit={10} />
        </div>
      </div>

      {/* Learning System Section */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-zinc-100 mb-4">
          Learning System
        </h2>
        <p className="text-sm text-zinc-400 mb-4">
          Model tuning and accuracy improvements based on feedback
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Accuracy Trend Over Time */}
        <div>
          <AccuracyTrendChart days={30} windowDays={7} />
        </div>

        {/* Alert Performance & Tuning */}
        <div>
          <LearningDashboard days={30} />
        </div>
      </div>
    </div>
  );
}
