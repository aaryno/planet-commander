"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Agent } from "@/lib/api";
import { ChatView } from "@/components/agents/ChatView";

export default function AgentChatPage() {
  const params = useParams();
  const router = useRouter();
  const agentId = params.id as string;

  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchAgent = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.agentDetail(agentId);
      setAgent(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    fetchAgent();
  }, [fetchAgent]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-6 w-6 text-zinc-500 animate-spin" />
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-sm text-red-400">
          {error ? `Failed to load agent: ${error.message}` : "Agent not found"}
        </p>
        <Button
          variant="outline"
          size="sm"
          className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
          onClick={() => router.push("/agents")}
        >
          <ArrowLeft className="h-3.5 w-3.5 mr-2" />
          Back to Agents
        </Button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col -m-6">
      <ChatView
        agent={agent}
        className="h-full"
        source="agents"
        headerActions={
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-zinc-400 hover:text-zinc-200"
            onClick={() => router.push("/agents")}
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1" />
            <span className="text-xs">Back</span>
          </Button>
        }
      />
    </div>
  );
}
