---

description: "Task list for feature 002-schedule-mode"

---

# Tasks: 调度模式与调度管理

**Input**: Design documents from `/specs/002-schedule-mode/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.yaml, quickstart.md

**Tests**: 测试任务按 plan.md 宪章（测试标准）与 research.md 测试策略生成——核心解析/同步/约束/迁移逻辑包含单元与集成测试。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**兼容性约束（贯穿所有任务）**: 本功能为既有平台增量扩展。所有对既有文件的修改仅限"追加"，不得改动既有解析、执行状态机、结果落库逻辑；新增列用幂等迁移，默认关闭调度模式；非调度项目行为与现状完全一致。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/src/`, `frontend/src/`（本项目为前后端分离 Web 应用）

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 增量依赖准备（既有项目已初始化，仅补充本功能新增依赖）

- [X] T001 Add `httpx` dependency to backend/pyproject.toml（调度服务 HTTP 客户端所需）

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 所有用户故事共用的基础能力（配置、迁移、模型、客户端、路由骨架）

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Add `SCHEDULE_SERVICE_URL`（默认 `http://127.0.0.1:8001`）与 `SCHEDULE_API_KEY`（默认空）to backend/src/config.py，沿用 `VIMAX_` 前缀；缺省不报错
- [X] T003 Create idempotent migration module in backend/src/models/migration.py（启动时 `PRAGMA table_info(projects)` 检查后 `ALTER TABLE ADD COLUMN`，为 projects 表追加 schedule_mode/schedule_status/schedule_updated_at，均带默认值；不重建表、不影响既有数据）
- [X] T004 Create migration idempotency test in backend/tests/test_migration.py（旧数据保留、二次启动幂等）
- [X] T005 ~~Create `ScheduleSyncQueue` model~~ **设计变更（2026-08-20）**: 本地不落调度队列，任务/队列记录由调度器维护，该模型已删除（见 services/schedule_sync.py 直接提交）
- [X] T006 [P] Create schedule request/response schemas in backend/src/schemas/schedule.py（ScheduleProject/ScheduleTask/ScheduleResult/ProjectSchedule，见 contracts/api.yaml）
- [X] T007 Create schedule service HTTP client in backend/src/services/schedule_client.py（httpx.AsyncClient + `X-API-Key` Header；封装 health/tasks/results/projects/queue 全部端点，见 contracts/api.yaml (B) 节；401/网络异常映射明确错误类型）
- [X] T008 Register schedule router in backend/src/main.py and create router skeleton in backend/src/routers/schedule.py（仅追加注册，含 `GET /api/schedule/health` 透传调度服务健康检查）

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - 开启调度模式并受约束地切换执行模式 (Priority: P1) 🎯 MVP

**Goal**: 项目详情可开启/关闭调度模式；调度模式存在未结束调度任务时禁止切回执行模式；支持在项目详情取消调度（全部任务）。

**Independent Test**: 打开项目详情开启调度模式；产生未结束调度任务后尝试切换执行模式被拒绝并提示；取消调度后切换成功。非调度项目行为与改造前一致。

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T009 [P] [US1] Unit test for schedule mode switch constraint in backend/tests/test_project_schedule.py（未结束任务拒绝切换/完成后允许/关闭模式前置取消确认）

### Implementation for User Story 1

- [X] T010 [P] [US1] Extend `Project` model with schedule fields in backend/src/models/project.py（schedule_mode/schedule_status/schedule_updated_at，仅追加字段，不改既有字段与状态机）
- [X] T011 [P] [US1] Extend project schemas with schedule fields in backend/src/schemas/project.py（响应含 schedule_mode/schedule_status/pending_tasks/can_switch_to_execute，带默认值）
- [X] T012 [US1] Implement schedule mode service in backend/src/services/project_schedule.py（开启/关闭、切换约束判定：调度服务 stats.pending > 0 拒绝关闭；关闭前置检查与取消确认）
- [X] T013 [US1] Add schedule-mode endpoints in backend/src/routers/projects.py（仅追加 `PATCH /api/projects/{project_id}/schedule-mode` 与 `GET /api/projects/{project_id}/schedule-status`，不改既有端点）
- [X] T014 [US1] Add schedule mode toggle UI in frontend/src/pages/ProjectDetail/（调度模式开关、状态标识、切换执行模式被拒提示、取消调度确认入口；不影响既有执行/结果交互）

**Checkpoint**: User Story 1 fully functional and testable independently

---

## Phase 4: User Story 2 - 调度模式下自动同步调度任务并实时反馈状态 (Priority: P1)

**Goal**: 监听 vimax_main 日志中的 `[COMFYUI SCHEDULE]::` / `[COMFYUI SCHEDULE DETAIL]::` 记录，解析为与 generation_result 同构的调度事件，同步到调度服务（首次隐式建项目）；产生调度任务后项目状态"调度中"。

**Independent Test**: 开启调度模式后执行生成，日志出现调度记录 → 30s 内调度管理/调度服务可见任务；项目状态变"调度中"；缺 file_path 暂存补全；重复记录去重；调度服务不可用时事件不丢失、恢复后重试成功。

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T015 [P] [US2] Unit test for schedule log parser in backend/tests/test_schedule_log_parser.py（正则解析、DETAIL 拼接、缺 file_path 暂存、重复行去重）
- [X] T016 [P] [US2] Unit test for schedule sync in backend/tests/test_schedule_sync.py（字段映射 business_task_id=prompt_id/project_id=web id/workflow 从 path 读取、直接提交调度器成功/无效/失败三态断言）

### Implementation for User Story 2

- [X] T017 [US2] Implement schedule log parser in backend/src/services/schedule_log_parser.py（独立模块，解析 `[COMFYUI SCHEDULE]::` 与紧随 `[COMFYUI SCHEDULE DETAIL]:: file_path`，prompt_id 为键缓存拼接；不改既有 generation_parser）
- [X] T018 [US2] Implement schedule sync service in backend/src/services/schedule_sync.py（`submit_schedule_event` 监听到调度日志后**直接** POST /api/v1/tasks 提交调度器，不落本地队列；成功置 Project.schedule_status=scheduling；调度器不可用返回 error 由监听侧下次轮询重试，workflow 损坏返回 invalid 放弃）
- [X] T019 [US2] Add parallel schedule listener branch in backend/src/services/generation_monitor.py（仅并行追加调度监听调用，仅在项目开启调度模式时激活；不改既有解析/推送/落库逻辑）
- [X] T020 [US2] Show "调度中" status in frontend/src/pages/ProjectDetail/ and project list（项目详情/列表展示调度中状态与未结束任务数）

**Checkpoint**: User Story 2 fully functional and testable independently

---

## Phase 5: User Story 3 - 调度管理：浏览调度项目并按优先级管理 (Priority: P1)

**Goal**: 新增"调度管理"入口，透传调度服务 API：调度项目列表（按优先级排序、任务数量统计）、项目任务列表、置顶、取消。

**Independent Test**: 调度管理页显示按优先级排序的项目列表与任务数量；置顶后排序变化；取消后状态更新；展开项目可见任务列表。

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T021 [P] [US3] Integration test for schedule client pass-through in backend/tests/test_schedule_client.py（httpx MockTransport 模拟调度服务：X-API-Key 头、projects/tasks/priority/cancel 端点路径与参数、401/网络异常）

### Implementation for User Story 3

- [X] T022 [P] [US3] Create schedule API client in frontend/src/api/schedule.ts（listProjects/getTasks/setPriority/cancel/getResults/syncResults）
- [X] T023 [P] [US3] Create schedule type definitions in frontend/src/types/schedule.ts
- [X] T024 [US3] Add schedule management endpoints in backend/src/routers/schedule.py（`GET /api/schedule/projects`、`GET /api/schedule/projects/{id}/tasks`、`PATCH /api/schedule/projects/{id}/priority`、`POST /api/schedule/projects/{id}/cancel`，透传调度服务）
- [X] T025 [US3] Create ScheduleManagement page in frontend/src/pages/ScheduleManagement/（项目列表按优先级排序、任务数量统计、置顶按钮（priority=1）、取消按钮（确认影响范围）、展开任务列表）
- [X] T026 [US3] Add `/schedule` route in frontend/src/router.tsx（仅追加路由，不改既有路由）

**Checkpoint**: User Story 3 fully functional and testable independently

---

## Phase 6: User Story 4 - 获取调度结果并自动回传为生成结果 (Priority: P1)

**Goal**: 调度管理页"获取结果"：拉取已完成任务列表（成功/失败）→ 逐个任务结果 → ComfyUI view 拉取输出保存到项目目录 → 生成 generation_result；失败任务标记失败原因。

**Independent Test**: 点击"获取结果"→ 列表含成功/失败；成功任务输出保存到项目目录并在项目结果页可见可预览；失败任务标记原因、不生成伪造结果；prompt_id 去重不重复落库。

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T027 [P] [US4] Unit test for result pass-back mapping in backend/tests/test_schedule_sync.py（SUCCESS → ComfyUI view 拉取 → 保存 → GenerationResult 落库且字段对齐；FAILED → 标记原因不落成功结果；prompt_id 去重）

### Implementation for User Story 4

- [X] T028 [US4] Implement result pass-back service in backend/src/services/schedule_sync.py（`GET /api/v1/results?synced=false` → 逐个 `GET /api/v1/results/{business_task_id}?project_id=` → SUCCESS: ComfyUI view 拉取保存到 `{project.working_dir}/` → 复用既有 GenerationResult 落库（prompt_id 去重）；FAILED: 记录失败原因）
- [X] T029 [US4] Add result endpoints in backend/src/routers/schedule.py（`GET /api/schedule/results`、`POST /api/schedule/results/sync`）
- [X] T030 [US4] Add "获取结果" button and result display in frontend/src/pages/ScheduleManagement/（触发 syncResults、成功/失败结果展示）

**Checkpoint**: User Story 4 fully functional and testable independently

---

## Phase 7: User Story 5 - 调度任务粒度的取消操作 (Priority: P2)

**Goal**: 项目调度任务列表中可取消单个排队任务；已完成/失败任务不可取消。

**Independent Test**: 任务列表中取消排队任务（确认后映射项目级取消），该任务状态更新为取消、其余任务不受影响；已完成/失败任务无取消入口或提示不可取消。

### Implementation for User Story 5

- [X] T031 [US5] Add per-task cancel interaction in frontend/src/pages/ScheduleManagement/（任务列表行内取消按钮 → 确认对话框明确"将取消该项目下全部排队任务" → 调用项目级 cancel 端点；仅对 QUEUED 任务展示）
- [X] T032 [US5] Disable cancel for finished tasks in frontend/src/pages/ScheduleManagement/（RUNNING/SUCCESS/FAILED 任务不提供取消或提示不可取消，满足 FR-022）

**Checkpoint**: User Story 5 fully functional and testable independently

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 影响多个用户故事的收尾与横切能力

- [ ] T033 [P] Run quickstart.md validation（按 specs/002-schedule-mode/quickstart.md 全流程冒烟：配置、开启调度模式、执行、同步、获取结果）— 依赖真实调度服务 + ComfyUI 环境，需人工执行
- [X] T034 [P] Add audit logging for schedule operations in backend/src/services/schedule_sync.py and routers（开启/关闭调度模式、置顶、取消、获取结果，纳入既有操作记录体系，FR-024）
- [ ] T035 [P] Add frontend ScheduleManagement test in frontend/tests/ScheduleManagement.test.tsx（列表渲染/置顶/取消/获取结果交互）— 前端当前无 vitest/jest/@testing-library 测试设施
- [X] T036 Polish error messaging for scheduler unavailable / missing API_KEY（backend 明确错误码与提示文案统一，调度服务不可用时 10s 内提示且事件不丢失——进程内去重，下次轮询重试提交）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - US1、US2、US3 可并行（各依赖 Foundational）
  - US4 建议在 US3 后（复用 ScheduleManagement 页与结果展示；后端服务可并行开发）
  - US5 依赖 US3（任务列表 UI 与 cancel 端点）
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: 依赖 Foundational（migration/config/client）— 独立可测
- **US2 (P1)**: 依赖 Foundational（config/client/queue 模型）— 独立可测；需 US1 的调度模式开关作为运行前提（联调时依赖）
- **US3 (P1)**: 依赖 Foundational（client）— 独立可测
- **US4 (P1)**: 依赖 Foundational + US3（列表/结果 UI 在 ScheduleManagement 页）— 后端回传服务可独立
- **US5 (P2)**: 依赖 US3（任务列表 + cancel 端点）

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup/Foundational tasks marked [P] can run in parallel
- Once Foundational completes, US1/US2/US3 can start in parallel
- US4 后端服务（T028）可与 US3 前端并行
- Tests within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different developers

---

## Parallel Example: Foundational Phase

```bash
# Launch together:
Task: "Add schedule config to backend/src/config.py"
Task: "Create idempotent migration module in backend/src/models/migration.py"
Task: "Create schedule schemas in backend/src/schemas/schedule.py"
Task: "Create schedule service HTTP client in backend/src/services/schedule_client.py"
```

## Parallel Example: User Story 1

```bash
# Launch all together:
Task: "Extend Project model in backend/src/models/project.py"
Task: "Extend project schemas in backend/src/schemas/project.py"
Task: "Unit test for schedule mode switch constraint in backend/tests/test_project_schedule.py"
```

## Parallel Example: User Story 3

```bash
# Launch all together:
Task: "Create schedule API client in frontend/src/api/schedule.ts"
Task: "Create schedule types in frontend/src/types/schedule.ts"
Task: "Integration test for schedule client in backend/tests/test_schedule_client.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1（调度模式开关 + 切换约束 + 项目详情取消调度）
4. **STOP and VALIDATE**: Test User Story 1 independently（含"非调度项目行为不变"回归）
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo（调度任务自动同步上线）
4. Add User Story 3 → Test independently → Deploy/Demo（调度管理入口）
5. Add User Story 4 → Test independently → Deploy/Demo（结果回传闭环）
6. Add User Story 5 → Test independently → Deploy/Demo（任务级取消）
7. Final: Polish & Cross-cutting（审计/错误提示/前端测试）

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1
   - Developer B: User Story 2
   - Developer C: User Story 3
3. Developer A completes US1 → join US4 (backend) or US5
4. Stories complete and integrate independently（联调：US2 需 US1 的调度模式开关）

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- **增量约束**：所有既有文件改动仅追加，不破坏既有解析/执行/落库逻辑；迁移幂等；调度默认关闭
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
