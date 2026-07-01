import { useMemo, useEffect, useState } from "react";
import { useWebSocket } from "./useWebSocket";
import { fetchProjectStdout } from "../api/projects";

/**
 * Stdout hook with explicit WS connectivity control.
 *
 * @param projectId   - current project id
 * @param wsEnabled   - whether to connect WebSocket (should be true ONLY when
 *                      vimax_runner confirms a subprocess is live for this project)
 * @param projectStatus - project.status from DB (for display logic)
 */
export function useStdout(projectId: number | null, wsEnabled: boolean, projectStatus?: string) {
  const { messages, isConnected, clear } = useWebSocket(projectId, wsEnabled);

  // When WS is NOT connected but project is active, fetch cached output once
  const [cachedContent, setCachedContent] = useState("");

  const isActive = projectStatus && projectStatus !== "idle";

  useEffect(() => {
    if (projectId && !wsEnabled && isActive) {
      fetchProjectStdout(projectId)
        .then((data) => setCachedContent(data.content))
        .catch(() => setCachedContent(""));
    } else if (!wsEnabled && !isActive) {
      setCachedContent("");
    }
  }, [projectId, wsEnabled, isActive]);

  const outputLines = useMemo(() => {
    if (wsEnabled) {
      return messages
        .filter((m) => m.type === "output" && m.content)
        .flatMap((m) => m.content!.split("\n"));
    }
    return cachedContent ? cachedContent.split("\n") : [];
  }, [messages, cachedContent, wsEnabled]);

  const finalStatus = useMemo(() => {
    if (wsEnabled) {
      const statusMessages = messages.filter((m) => m.type === "status");
      return statusMessages.length > 0 ? statusMessages[statusMessages.length - 1] : null;
    }
    // For non-running projects, derive finalStatus from projectStatus
    if (projectStatus === "completed" || projectStatus === "failed" || projectStatus === "success") {
      return { project_status: projectStatus };
    }
    return null;
  }, [messages, wsEnabled, projectStatus]);

  const stepReady = useMemo(() => {
    if (!wsEnabled) return null;
    const readyMessages = messages.filter((m) => m.type === "step_ready");
    return readyMessages.length > 0 ? readyMessages[readyMessages.length - 1] : null;
  }, [messages, wsEnabled]);

  return { outputLines, finalStatus, stepReady, isConnected, clear };
}
