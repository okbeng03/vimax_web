export type StepStatus =
  | "pending"
  | "running"
  | "fully_complete"
  | "partially_complete"
  | "failed";

export interface ComfyuiResultInStep {
  id: number;
  file_path: string;
  thumbnail_path: string | null;
  prompt_id: string;
  generation_type: "first_frame" | "last_frame" | "video";
  duration_seconds: number;
  confirmed: boolean;
}

export interface Step {
  id: number;
  name: string;
  step_order: number;
  status: StepStatus;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  output_files: string[];
  retry_count: number;
  error_message: string | null;
  comfyui_results: ComfyuiResultInStep[];
}

export interface StepListResponse {
  steps: Step[];
}
