# Data Model: 调度模式与调度管理

**Feature**: 002-schedule-mode | **Date**: 2026-08-20

> 基于 001 平台既有数据模型扩展。调度项目/任务/队列数据均以调度服务侧为准（Q4 澄清），本地仅扩展 `Project` 字段；监听到调度日志后**直接提交调度器**，不落本地队列。

## Entity Relationship Diagram

```
Project
      ├──< Step (N) ──< GenerationResult (N)   [既有，结果回传复用]
      │
      └── schedule_mode / schedule_status       [本功能扩展字段]

调度服务侧（外部，不透传存储）:
  ScheduleProject (1) ────< ScheduleTask (N)
   - 以调度服务 project_id 为准，保存 web project_id + name
   - 首次提交任务时隐式创建
```

## Entities

### Project (项目) — 扩展

新增字段（**启动时幂等迁移**：`PRAGMA table_info` 检查缺失列后 `ALTER TABLE ADD COLUMN`，均带默认值；不重建表、不影响既有行与既有状态机）：

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| schedule_mode | BOOLEAN | NOT NULL, DEFAULT false | 是否开启调度模式（默认关闭，非调度项目行为不变） |
| schedule_status | VARCHAR(20) | NOT NULL, DEFAULT 'idle' | 调度状态: idle（空闲/调度完成）/ scheduling（调度中） |
| schedule_updated_at | DATETIME | NULLABLE | 调度状态最后更新时间 |

**状态机（schedule_status）**:
```
idle ──[开启调度模式并同步产生调度任务]──→ scheduling
scheduling ──[调度任务全部结束（结果回传/取消/失败确认）]──→ idle
```

**模式切换约束（执行模式 ↔ 调度模式）**:
- 调度模式 → 执行模式：仅当调度服务 `stats.pending == 0`（即无未结束调度任务）时允许。
- 执行模式 → 调度模式：随时允许。

---

### GenerationResult (生成结果) — 既有，结果回传复用

无结构变更。结果回传时复用既有字段（file_path / storage_path / prompt_id / workflow_name / generation_type / duration_seconds），以 prompt_id 在项目内去重（既有 DB 逻辑）。

---

### 外部实体（调度服务侧，本地不落库）

- **ScheduleProject（调度项目）**: 调度服务 project_id 为准，保存 web project_id、name、priority(0~99)、paused、stats(total/pending/success/failed)。首次提交任务隐式创建。
- **ScheduleTask（调度任务）**: business_task_id（=本地 prompt_id）、status（QUEUED/RUNNING/SUCCESS/FAILED）、failure_reason、result_outputs、result_view、has_sync、retry_count。

> 调度管理页数据均通过透传调度服务 API 获取（`GET /api/v1/projects/{id}`、`GET /api/v1/queue`、`GET /api/v1/results`），本地不维护映射表。

## 数据流

1. **同步**（日志 → 调度服务）: `vimax_output.tmp` → `schedule_log_parser` 解析 `[COMFYUI SCHEDULE]::` + `[COMFYUI SCHEDULE DETAIL]::` → **直接** `POST /api/v1/tasks` 提交调度器（隐式建项目），并置 `Project.schedule_status=scheduling`。任务与队列记录由调度器维护，Web 通过调度服务 API（`/api/v1/projects/{id}`、`/api/v1/queue`、`/api/v1/results`）查询。调度器暂不可用时事件不丢失（进程内去重，下次轮询重试提交）。
2. **回传**（调度服务 → 本地）: 用户点击"获取结果" → `GET /api/v1/results?synced=false` → 逐个 `GET /api/v1/results/{business_task_id}?project_id=` → SUCCESS: ComfyUI view 拉取 → 保存 `{working_dir}/` → 落库 `GenerationResult`；FAILED: 标记失败。全部结束后 `schedule_status` 复查回 idle。
3. **取消/置顶**（透传）: 前端 → backend → 调度服务（`POST /projects/{id}/cancel` / `PATCH /projects/{id}/priority`）。
