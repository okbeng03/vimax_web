import client from "./client";

export interface FileItem {
  name: string;
  type: "file" | "directory";
  size: number | null;
  modified_at: number;
  children_count: number | null;
}

export async function fetchFileTree(projectId: number, path?: string): Promise<{ current_path: string; files: FileItem[] }> {
  const { data } = await client.get(`/projects/${projectId}/files`, { params: { path } });
  return data;
}

export async function fetchFileContent(projectId: number, path: string): Promise<{ path: string; content: string; size: number; modified_at: number }> {
  const { data } = await client.get(`/projects/${projectId}/files/content`, { params: { path } });
  return data;
}

export async function updateFileContent(projectId: number, path: string, content: string): Promise<void> {
  await client.put(`/projects/${projectId}/files/content`, { path, content });
}

/** Build a direct URL for media files (images / audio / video) */
export function getMediaUrl(projectId: number, path: string): string {
  return `/api/projects/${projectId}/files/media?path=${encodeURIComponent(path)}`;
}

/** Move a file to caches/ — soft-delete */
export async function deleteFile(projectId: number, path: string): Promise<{ path: string; cache_path: string; status: string }> {
  const { data } = await client.delete(`/projects/${projectId}/files`, { params: { path } });
  return data;
}
