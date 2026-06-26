import client from "./client";
import type { GenerationResult, GenerationListResponse, RetryRequest, GachaRequest } from "../types/generation";

export async function fetchGenerations(projectId: number, params?: Record<string, unknown>): Promise<GenerationListResponse> {
  const { data } = await client.get(`/projects/${projectId}/generations`, { params });
  return data;
}

export async function confirmGeneration(projectId: number, generationId: number): Promise<void> {
  await client.post(`/projects/${projectId}/generations/${generationId}/confirm`);
}

export async function cancelGeneration(projectId: number, generationId: number): Promise<{ status: string; cached_path: string; was_confirmed?: boolean }> {
  const { data } = await client.post(`/projects/${projectId}/generations/${generationId}/cancel`);
  return data;
}

export async function recoverGeneration(projectId: number, generationId: number): Promise<{ status: string; file_path: string }> {
  const { data } = await client.post(`/projects/${projectId}/generations/${generationId}/recover`);
  return data;
}

export async function gachaGeneration(projectId: number, generationId: number, body: GachaRequest): Promise<{ status: string; step_name: string; gacha_type: string; scene: number; shot: number }> {
  const { data } = await client.post(`/projects/${projectId}/generations/${generationId}/gacha`, body);
  return data;
}

export async function retryGeneration(projectId: number, generationId: number, body: RetryRequest): Promise<{ new_generation_id: number; prompt_id: string }> {
  const { data } = await client.post(`/projects/${projectId}/generations/${generationId}/retry`, body);
  return data;
}
