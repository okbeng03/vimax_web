export interface ProjectSchedule {
  project_id: number;
  schedule_mode: boolean;
  schedule_status: "idle" | "syncing" | "synced" | "failed";
  schedule_updated_at: string | null;
}

export interface ScheduleTask {
  business_task_id: string;
  project_id: string;
  project_name: string | null;
  workflow_name: string | null;
  status: "QUEUED" | "RUNNING" | "SUCCESS" | "FAILED" | "CANCELED" | string;
  priority: number;
  type: string | null;
  retry_count: number;
  failure_reason: string | null;
  result_ready_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/** 调度器 ProjectStats: total / pending / success / failed */
export interface ScheduleStats {
  total: number;
  pending: number;
  success: number;
  failed: number;
}

export interface ScheduleProject {
  project_id: string;
  name: string;
  priority: number;
  paused: boolean;
  stats: ScheduleStats;
}

export interface ScheduleResult {
  business_task_id: string;
  project_id: string | null;
  project_name: string | null;
  status: string | null;
  failure_reason: string | null;
  synced: boolean;
  file_path: string | null;
  workflow_name: string | null;
  result_ready_at: string | null;
  created_at: string | null;
}

export interface ScheduleResultSyncResponse {
  /** 是否已触发后台同步 */
  started: boolean;
  /** 本次触发的任务数 */
  count: number;
}

export interface ScheduleCancelResponse {
  cancelled: boolean;
}

export interface ScheduleHealth {
  status: string;
  service_url: string;
}
