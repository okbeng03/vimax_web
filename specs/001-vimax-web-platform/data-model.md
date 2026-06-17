# Data Model: ViMax Web 平台

**Feature**: 001-vimax-web-platform | **Date**: 2026-06-17

## Entity Relationship Diagram

```
User (1) ────< Project (N)
                  │
                  ├──< Step (N)
                  │      │
                  │      └──< GenerationResult (N)
                  │
                  ├──< OperationLog (N)
                  │
                  └── Template (1: 创建时选用的模板引用)

注: GenerationResult 和 OperationLog 也直接关联 User (created_by)
```

## Entities

### User (用户)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PK, AUTOINCREMENT | 主键 |
| username | VARCHAR(50) | UNIQUE, NOT NULL | 用户名 |
| display_name | VARCHAR(100) | NOT NULL | 显示名称 |
| created_at | DATETIME | NOT NULL, DEFAULT NOW | 创建时间 |

**Seed Data**: 预设用户 `id=1, username="muze", display_name="Muze"`

**Indexes**: `idx_user_username` ON (username)

---

### Project (项目)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PK, AUTOINCREMENT | 主键 |
| user_id | INTEGER | FK → User.id, NOT NULL | 所属用户 |
| name | VARCHAR(200) | NOT NULL | 项目名称 |
| creative_description | TEXT | NOT NULL | 创意描述 (idea) |
| working_dir | VARCHAR(500) | UNIQUE, NOT NULL | ViMax working_dir 绝对路径 |
| template_id | INTEGER | FK → Template.id, NULLABLE | 创建时使用的模板 |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'idle' | idle / running / completed / failed |
| current_step_name | VARCHAR(50) | NULLABLE | 当前执行步骤名 |
| created_at | DATETIME | NOT NULL, DEFAULT NOW | 创建时间 |
| updated_at | DATETIME | NOT NULL, DEFAULT NOW | 最后更新时间 |
| completed_at | DATETIME | NULLABLE | 完成时间 |

**State Machine**:
```
idle ──[start]──→ running ──[all_steps_complete]──→ completed
                     │
                     └──[fatal_error/kill]──→ failed ──[retry]──→ running
```

**Indexes**: `idx_project_user_status` ON (user_id, status), `idx_project_created` ON (created_at DESC)

---

### Step (执行步骤)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PK, AUTOINCREMENT | 主键 |
| project_id | INTEGER | FK → Project.id, NOT NULL | 所属项目 |
| name | VARCHAR(50) | NOT NULL | 步骤名称 (story/character/...) |
| step_order | INTEGER | NOT NULL | 流水线序号 |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending' | pending / running / fully_complete / partially_complete / failed |
| started_at | DATETIME | NULLABLE | 开始时间 |
| completed_at | DATETIME | NULLABLE | 完成时间 |
| duration_seconds | FLOAT | NULLABLE | 执行耗时 (秒) |
| output_files | TEXT | NULLABLE | JSON array: 输出文件相对路径列表 |
| retry_count | INTEGER | NOT NULL, DEFAULT 0 | 重试次数 |
| error_message | TEXT | NULLABLE | 失败原因 |

**Valid step names**: story, character, portrait, script, environment, environment_images, storyboard, shot_description, camera_tree, camera_frame, shot_video, shot_transition, scene_video, scene_transition

**State Machine**:
```
pending ──[start]──→ running ──[success+comfyui_ok]──→ fully_complete
                        │
                        ├──[success+comfyui_down]──→ partially_complete ──[re-run]──→ running
                        │
                        └──[error/kill]──→ failed ──[retry]──→ pending
```

**Completion Semantics**:
- `fully_complete`: 文本产出 + ComfyUI 图像/视频 全部生成成功
- `partially_complete`: 仅文本产出生成，ComfyUI 部分跳过。允许进入下一步，但下次从该步骤重新执行
- `failed`: ViMax 进程异常退出或用户手动 kill

**Indexes**: `idx_step_project_order` ON (project_id, step_order), UNIQUE(project_id, name)

---

### GenerationResult (ComfyUI 生成结果)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PK, AUTOINCREMENT | 主键 |
| step_id | INTEGER | FK → Step.id, NOT NULL | 所属步骤 |
| project_id | INTEGER | FK → Project.id, NOT NULL | 所属项目 (冗余便于查询) |
| user_id | INTEGER | FK → User.id, NOT NULL | 操作者 |
| file_path | VARCHAR(500) | NOT NULL | 输出文件路径 (相对 working_dir) |
| thumbnail_path | VARCHAR(500) | NULLABLE | 缩略图路径 |
| prompt_id | VARCHAR(100) | NOT NULL | ComfyUI prompt_id |
| generation_type | VARCHAR(20) | NOT NULL | first_frame / last_frame / video |
| error_message | TEXT | NULLABLE | 失败原因 |
| duration_seconds | FLOAT | NOT NULL | 生成耗时 (秒) |
| confirmed | BOOLEAN | NOT NULL, DEFAULT 0 | 是否已确认 |
| confirmed_at | DATETIME | NULLABLE | 确认时间 |
| created_at | DATETIME | NOT NULL, DEFAULT NOW | 创建时间 |

**Indexes**: `idx_result_step` ON (step_id), `idx_result_project_confirmed` ON (project_id, confirmed), `idx_result_prompt_id` ON (prompt_id)

**Workflow 获取方式**: workflow 定义（ui 版和 api 版）不存储在 GenerationResult 中，而是从 `{project.working_dir}/workflows/` 目录读取。通过 `prompt_id` 关联到具体的 workflow 文件。

---

### OperationLog (操作记录)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PK, AUTOINCREMENT | 主键 |
| project_id | INTEGER | FK → Project.id, NOT NULL | 所属项目 |
| user_id | INTEGER | FK → User.id, NOT NULL | 操作者 |
| operation_type | VARCHAR(30) | NOT NULL | edit_file / confirm_result / reject_result / regenerate_step |
| target_type | VARCHAR(50) | NOT NULL | 操作对象类型 (file / generation_result / step) |
| target_id | INTEGER | NULLABLE | 操作对象 ID |
| target_name | VARCHAR(200) | NOT NULL | 操作对象名称 |
| summary | TEXT | NOT NULL | 变更摘要 |
| details | TEXT | NULLABLE | JSON: 详细变更内容 |
| created_at | DATETIME | NOT NULL, DEFAULT NOW | 操作时间 |

**Indexes**: `idx_log_project_time` ON (project_id, created_at DESC), `idx_log_type` ON (operation_type)

---

### Template (项目模板)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PK, AUTOINCREMENT | 主键 |
| name | VARCHAR(100) | UNIQUE, NOT NULL | 模板名称 |
| display_name | VARCHAR(200) | NOT NULL | 显示名称 |
| description | TEXT | NOT NULL | 模板描述 |
| directory_name | VARCHAR(100) | NOT NULL | 模板目录名 (在 backend/src/templates/ 下) |
| is_builtin | BOOLEAN | NOT NULL, DEFAULT 1 | 是否内置模板 |
| created_at | DATETIME | NOT NULL, DEFAULT NOW | 创建时间 |

**Seed Data**: 3 个内置模板
| id | name | display_name | directory_name |
|----|------|-------------|----------------|
| 1 | standard | 标准视频 | standard |
| 2 | fast_preview | 快速预览 | fast_preview |
| 3 | high_quality | 高质量 | high_quality |

实际 YAML 和 config.py 内容存储在 `backend/src/templates/{directory_name}/` 文件系统中。
