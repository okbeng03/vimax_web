export interface GenerationResult {
  id: number;
  step_name: string | null;
  workflow_name: string | null;
  file_path: string;
  relative_path: string;
  storage_path: string;
  original_relative_path: string;
  thumbnail_path: string | null;
  prompt_id: string;
  generation_type: "first_frame" | "last_frame" | "video" | "image" | "audio";
  duration_seconds: number;
  confirmed: boolean;
  cancelled: boolean;
  error_message?: string;
  created_at: string;
  scene: number | null;
  shot: number | null;
}

export interface GenerationListResponse {
  generations: GenerationResult[];
  total: number;
  total_pages: number;
  unconfirmed_count: number;
}

export interface GenerationFilter {
  confirmed?: boolean;
  step_name?: string;
  page?: number;
  page_size?: number;
  sort_by?: "created_at" | "scene" | "shot" | "scene_shot";
  sort_order?: "asc" | "desc";
}

export interface RetryRequest {
  modified_params: Record<string, unknown>;
}

export interface GachaRequest {
  gacha_type: "last_frame" | "first_frame" | "video";
  scene: number;
  shot: number;
}
