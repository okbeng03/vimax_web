import client from "./client";
import type {
  ProjectListItem,
  ProjectDetail,
  ProjectCreateRequest,
  ProjectConfigUpdateRequest,
  ProjectListResponse,
  ProjectProgressResponse,
} from "../types/project";

export async function fetchProjects(params?: {
  status?: string;
  search?: string;
  page?: number;
  page_size?: number;
}): Promise<ProjectListResponse> {
  const { data } = await client.get("/projects", { params });
  return data;
}

export async function fetchProject(id: number): Promise<ProjectDetail> {
  const { data } = await client.get(`/projects/${id}`);
  return data;
}

export async function createProject(body: ProjectCreateRequest): Promise<{ id: number; name: string; working_dir: string; status: string; created_at: string }> {
  const { data } = await client.post("/projects", body);
  return data;
}

export async function updateProjectConfig(id: number, body: ProjectConfigUpdateRequest): Promise<void> {
  await client.put(`/projects/${id}/config`, body);
}

export async function deleteProject(id: number): Promise<void> {
  await client.delete(`/projects/${id}`);
}

export async function fetchRunningProject(): Promise<{
  is_running: boolean;
  project_id: number | null;
  project_name: string | null;
}> {
  const { data } = await client.get("/projects/running");
  return data;
}

export async function fetchProjectProgress(projectId: number): Promise<ProjectProgressResponse> {
  const { data } = await client.get(`/projects/${projectId}/progress`);
  return data;
}

export async function fetchProjectStdout(projectId: number): Promise<{ content: string }> {
  const { data } = await client.get(`/projects/${projectId}/stdout`);
  return data;
}
