import { useEffect, useRef, useCallback, useState } from "react";

interface StdoutMessage {
  type: "output" | "step_ready" | "status" | "error" | "clear";
  content?: string;
  step_name?: string;
  step_status?: string;
  project_status?: string;
  error_message?: string;
  message?: string;
}

/**
 * WebSocket hook with explicit enabled control.
 * WS is only opened when {enabled} is true AND projectId is valid.
 * When enabled becomes false, WS is immediately closed and isConnected reset.
 */
export function useWebSocket(projectId: number | null, enabled: boolean) {
  const wsRef = useRef<WebSocket | null>(null);
  const [messages, setMessages] = useState<StdoutMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);

  // Close helper — synchronous reset, avoids async onclose timing issues
  const closeWs = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  useEffect(() => {
    // Neither enabled nor valid projectId → ensure disconnected
    if (!enabled || !projectId) {
      closeWs();
      return;
    }

    // Open new WS
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws/projects/${projectId}/stdout`);
    wsRef.current = ws;

    ws.onopen = () => setIsConnected(true);
    ws.onclose = () => setIsConnected(false);
    ws.onerror = () => setIsConnected(false);
    ws.onmessage = (event) => {
      try {
        const msg: StdoutMessage = JSON.parse(event.data);
        if (msg.type === "clear") {
          setMessages([]);
          return;
        }
        setMessages((prev) => [...prev, msg]);
      } catch {
        // ignore non-JSON messages
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
      setIsConnected(false);
    };
  }, [projectId, enabled, closeWs]);

  const clear = useCallback(() => setMessages([]), []);

  return { messages, isConnected, clear };
}
