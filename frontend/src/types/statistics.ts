export interface StepStat {
  name: string;
  duration: number;
  status: string;
  error_message?: string | null;
  retry_count?: number;
}

export interface StepOverview {
  total: number;
  completed: number;
  failed: number;
  running: number;
  pending: number;
  success_rate: number;
}

export interface GenerationTypeStat {
  type: string;
  count: number;
}

export interface GenerationStepStat {
  step_name: string;
  total: number;
  success: number;
  failed: number;
}

export interface DurationBucket {
  range: string;
  count: number;
}

export interface AvgDurationByType {
  type: string;
  avg_duration: number;
}

export interface StepLogRetryStat {
  step_name: string;
  db_retry_count: number;
  log_retry_count: number;
  confirm_count: number;
  reject_count: number;
}

export interface StepLogRetrySummary {
  total_log_retries: number;
  avg_log_retries_per_step: number;
  max_log_retries_per_step: number;
  max_log_retry_step: string;
  total_db_retries: number;
  total_confirms: number;
  total_rejects: number;
  steps_with_retries: number;
  total_steps: number;
}

export interface ProjectStats {
  scene_count: number;
  file_counts: Record<string, number>;
  total_file_size_mb: number;
  total_duration_seconds: number;
  step_overview: StepOverview;
  steps: StepStat[];
  operation_summary: Record<string, number>;
  generation_stats: {
    total: number;
    success: number;
    failed: number;
    success_rate: number;
  };
  generations_by_type: GenerationTypeStat[];
  generations_by_step: GenerationStepStat[];
  duration_buckets: DurationBucket[];
  avg_duration_by_type: AvgDurationByType[];
  step_log_retries: StepLogRetryStat[];
  step_log_retry_summary: StepLogRetrySummary | null;
}

export interface GlobalStats {
  total_projects: number;
  completed_projects: number;
  failed_projects: number;
  running_projects: number;
  success_rate: number;
  total_generations: number;
  avg_generation_duration: number;
  failure_reasons: Record<string, number>;
  trend: {
    daily: TrendPoint[];
    weekly: TrendPoint[];
  };
}

export interface TrendPoint {
  date: string;
  total: number;
  success: number;
  failed: number;
}
