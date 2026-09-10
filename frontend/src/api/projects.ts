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

export async function fetchProjectScheduleStatus(
  projectId: number,
): Promise<{ project_id: number; schedule_mode: boolean; schedule_status: string; schedule_updated_at: string | null }> {
  const { data } = await client.get(`/projects/${projectId}/schedule-status`);
  return data;
}

export async function setProjectScheduleMode(
  projectId: number,
  schedule_mode: boolean,
): Promise<{ project_id: number; schedule_mode: boolean; schedule_status: string; schedule_updated_at: string | null }> {
  const { data } = await client.patch(`/projects/${projectId}/schedule-mode`, { schedule_mode });
  return data;
}

export async function fetchProjectStdout(projectId: number): Promise<{ content: string }> {
  const { data } = await client.get(`/projects/${projectId}/stdout`);
  return data;
}

export async function batchProcessVideo(projectId: number): Promise<{ message: string }> {
  const { data } = await client.post(`/projects/${projectId}/batch-process-video`);
  return data;
}

export async function collectDoubao(projectId: number): Promise<{ message: string }> {
  const { data } = await client.post(`/projects/${projectId}/collect-doubao`);
  return data;
}
