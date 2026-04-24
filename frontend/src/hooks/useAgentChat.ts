"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export interface ChatMessage {
  role: "user" | "assistant";
  timestamp: string;
  content?: string;
  summary?: string;
  tool_calls?: Array<{ name: string; input_preview: string }>;
  tool_call_count?: number;
  has_thinking?: boolean;
  thinking?: string;
  model?: string;
}

interface WebSocketMessage {
  type: "response" | "error" | "status";
  content?: string;
  message?: string;
  status?: string;
}

export function useAgentChat(agentId: string, enabled: boolean = true) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Connect to WebSocket
  useEffect(() => {
    if (!enabled) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.hostname}:9000/api/agents/${agentId}/ws`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("WebSocket connected");
      setIsConnected(true);
      setError(null);
    };

    ws.onmessage = (event) => {
      try {
        const data: WebSocketMessage = JSON.parse(event.data);

        if (data.type === "response" && data.content) {
          // Full assistant response text for this turn
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            // If last message is from assistant (same turn), replace it
            if (last && last.role === "assistant" && last.content) {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...last,
                content: last.content + "\n\n" + data.content,
              };
              return updated;
            } else {
              return [
                ...prev,
                {
                  role: "assistant",
                  timestamp: new Date().toISOString(),
                  content: data.content,
                },
              ];
            }
          });
        } else if (data.type === "status") {
          if (data.status === "processing") {
            setIsProcessing(true);
          } else if (data.status === "idle") {
            setIsProcessing(false);
          }
        } else if (data.type === "error") {
          setError(data.message || "Unknown error");
          setIsProcessing(false);
        }
      } catch (err) {
        console.error("Failed to parse WebSocket message:", err);
      }
    };

    ws.onerror = () => {
      setError("Connection error");
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
      setIsConnected(false);
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [agentId, enabled]);

  // Send message via WebSocket
  const sendMessage = useCallback(
    (message: string, source?: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        setError("Not connected to agent");
        return false;
      }

      // Add user message optimistically
      setMessages((prev) => [
        ...prev,
        {
          role: "user",
          timestamp: new Date().toISOString(),
          content: message,
        },
      ]);

      // Send to WebSocket
      wsRef.current.send(
        JSON.stringify({
          type: "message",
          content: message,
          source,
        })
      );

      return true;
    },
    []
  );

  return {
    messages,
    isConnected,
    isProcessing,
    error,
    sendMessage,
  };
}
