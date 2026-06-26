export interface ProjectListItem {
  id: number;
  name: string;
  creative_description: string;
  working_dir: string;
  status: "idle" | "running" | "completed" | "failed";
  template_name: string;
  current_step_name: string | null;
  step_summary: { total: number; completed: number; failed: number };
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail {
  id: number;
  name: string;
  creative_description: string;
  working_dir: string;
  status: "idle" | "running" | "completed" | "failed";
  template_id: number;
  current_step_name: string | null;
  config: {
    yaml_content: string;
    config_py_content: string;
  };
  unconfirmed_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreateRequest {
  name: string;
  creative_description: string;
  template_id: number;
  working_dir_root: string;
}

export interface ProjectConfigUpdateRequest {
  yaml_content: string;
  config_py_content: string;
}

export interface ProjectListResponse {
  projects: ProjectListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProgressStep {
  name: string;
  label: string;
  order: number;
  status: "new" | "running" | "success" | "failed" | "pending";
}

export interface ProjectProgressResponse {
  steps: ProgressStep[];
  current_step_order: number | null;
}
