import type { Agent } from "./api";

export interface AMVWindow {
  id: string;
  agentId?: string;
  color: string;
  createdAt: string;
}

const COLORS = ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444", "#06b6d4", "#ec4899"];

export function addAgentToAMV(agent: Agent): AMVWindow {
  const existing: AMVWindow[] = JSON.parse(sessionStorage.getItem("amv-agents") || "[]");

  // Don't add duplicates
  const found = existing.find(w => w.agentId === agent.id);
  if (found) return found;

  const newWindow: AMVWindow = {
    id: `amv-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    agentId: agent.id,
    color: COLORS[existing.length % COLORS.length],
    createdAt: new Date().toISOString(),
  };

  existing.push(newWindow);
  sessionStorage.setItem("amv-agents", JSON.stringify(existing));
  return newWindow;
}
