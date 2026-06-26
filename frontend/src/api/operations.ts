import client from "./client";

export interface OperationLog {
  id: number;
  operation_type: string;
  target_type: string;
  target_id: number | null;
  target_name: string;
  summary: string;
  details: string | null;
  user_name: string | null;
  created_at: string;
}

export async function fetchOperations(projectId: number, params?: { type?: string; page?: number; page_size?: number }): Promise<{ operations: OperationLog[]; total: number }> {
  const { data } = await client.get(`/projects/${projectId}/operations`, { params });
  return data;
}
