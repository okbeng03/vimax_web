import client from "./client";
import type {
  ProjectSchedule,
  ScheduleProject,
  ScheduleResult,
  ScheduleResultSyncResponse,
  ScheduleCancelResponse,
  ScheduleTask,
  ScheduleHealth,
} from "../types/schedule";

export async function fetchScheduleHealth(): Promise<ScheduleHealth> {
  const { data } = await client.get("/schedule/health");
  return data;
}

export async function pauseScheduler(): Promise<Record<string, any>> {
  const { data } = await client.post("/schedule/scheduler/pause");
  return data;
}

export async function resumeScheduler(): Promise<Record<string, any>> {
  const { data } = await client.post("/schedule/scheduler/resume");
  return data;
}

export async function setProjectScheduleMode(
  projectId: number,
  schedule_mode: boolean,
): Promise<ProjectSchedule> {
  const { data } = await client.patch(`/projects/${projectId}/schedule-mode`, { schedule_mode });
  return data;
}

export async function fetchProjectScheduleStatus(projectId: number): Promise<ProjectSchedule> {
  const { data } = await client.get(`/projects/${projectId}/schedule-status`);
  return data;
}

export async function fetchScheduleProjects(): Promise<ScheduleProject[]> {
  const { data } = await client.get("/schedule/projects");
  return data;
}

export async function fetchScheduleProject(scheduleProjectId: string): Promise<ScheduleProject> {
  const { data } = await client.get(`/schedule/projects/${scheduleProjectId}`);
  return data;
}

export async function fetchScheduleProjectTasks(
  scheduleProjectId: string,
): Promise<ScheduleTask[]> {
  const { data } = await client.get(`/schedule/projects/${scheduleProjectId}/tasks`);
  return data;
}

export async function setScheduleProjectPriority(
  scheduleProjectId: string,
  priority: number,
): Promise<ScheduleProject> {
  const { data } = await client.patch(`/schedule/projects/${scheduleProjectId}/priority`, {
    priority,
  });
  return data;
}

export async function cancelScheduleProject(
  scheduleProjectId: string,
): Promise<ScheduleCancelResponse> {
  const { data } = await client.post(`/schedule/projects/${scheduleProjectId}/cancel`);
  return data;
}

export async function fetchScheduleResults(synced = false): Promise<ScheduleResult[]> {
  const { data } = await client.get("/schedule/results", { params: { synced } });
  return data;
}

// 同步接口为异步触发：前端只负责调用，后端后台串行执行，立即返回。
export async function syncScheduleResults(
  items: { task_id: string; project_id: number }[],
): Promise<ScheduleResultSyncResponse> {
  const { data } = await client.post("/schedule/results/sync", { items });
  return data;
}


