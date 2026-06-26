import client from "./client";
import type { GlobalStats, ProjectStats } from "../types/statistics";

export async function fetchGlobalStats(): Promise<GlobalStats> {
  const { data } = await client.get("/statistics/overview");
  return data;
}

export async function fetchProjectStats(projectId: number): Promise<ProjectStats> {
  const { data } = await client.get(`/projects/${projectId}/statistics`);
  return data;
}
