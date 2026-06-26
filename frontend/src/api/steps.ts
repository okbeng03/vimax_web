import client from "./client";
import type { Step, StepListResponse } from "../types/step";

export async function fetchSteps(projectId: number): Promise<StepListResponse> {
  const { data } = await client.get(`/projects/${projectId}/steps`);
  return data;
}

export async function executeSteps(
  projectId: number,
  action: string,
  stepName?: string,
): Promise<{ project_id: number; status: string; current_step_name: string; message: string }> {
  const { data } = await client.post(`/projects/${projectId}/steps/execute`, {
    action,
    step_name: stepName || null,
  });
  return data;
}

export async function killSteps(projectId: number): Promise<{ status: string; message: string }> {
  const { data } = await client.post(`/projects/${projectId}/steps/kill`);
  return data;
}
