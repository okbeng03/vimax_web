import { useState, useCallback } from "react";
import * as filesApi from "../api/files";

export function useFileEditor(projectId: number | null) {
  const [content, setContent] = useState("");
  const [currentPath, setCurrentPath] = useState("");
  const [loading, setLoading] = useState(false);

  const loadFile = useCallback(async (path: string) => {
    if (!projectId) return;
    setLoading(true);
    try {
      const data = await filesApi.fetchFileContent(projectId, path);
      setContent(data.content);
      setCurrentPath(path);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const saveFile = useCallback(async () => {
    if (!projectId || !currentPath) return;
    await filesApi.updateFileContent(projectId, currentPath, content);
  }, [projectId, currentPath, content]);

  return { content, setContent, currentPath, loading, loadFile, saveFile };
}
